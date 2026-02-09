"""
Author: Ryan Nash
Date: 30 January 2026
Revised: 08 February 2026
Project: Tasty Truths

Description:
    This module serves as the main application entry point for the Tasty Truths
    web platform. It initializes the Flask application, configures extensions,
    registers blueprints, and defines core application behavior. The app
    coordinates routing between recipe, blog, and utility components, manages
    database connections, and provides shared configuration used across the site.
"""

from datetime import timedelta
import json
import argparse
import random
from sqlalchemy import func
from flask import Flask, request, jsonify, redirect, url_for, redirect, render_template, flash, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
from argon2 import PasswordHasher
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
import os
from services.db import db
from services.models import Recipe, RecipeSlugHistory, BlogPost, User, Ingredient
from services.forms import RecipeForm, BlogPostForm
from services.ingredients import ALLOWED_NUTRIENT_SORT_KEYS, build_ingredient_sort
from services.ingredient_index import load_ingredients_index, match_ingredient_id, search_suggestions
from services.nutrition import compute_recipe_macros, ensure_ingredient_exists_in_assets, load_ingredient_index
from services.filtering import filter_ingredients_by_dietary_tags
from utilities.seed_demo import seed_demo_data

ph = PasswordHasher()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

class AdminOverrideUser(UserMixin):
    def __init__(self, user_id: str = "admin-override"):
        self.id = user_id
        self.username = user_id

def create_app(admin_override: bool = False, config_overrides=None, seed_demo: bool = True):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    # --- security & session config ---
    app.config.update(
        SECRET_KEY="replace-me",  # set via env in prod
        SQLALCHEMY_DATABASE_URI="sqlite:///site.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=False,     # True behind HTTPS
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_TIME_LIMIT=None,        # CSRF token lifetime (optional)
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2MB file upload limit
    )
    if config_overrides:
        app.config.update(config_overrides)
    app.config["ADMIN_OVERRIDE"] = bool(admin_override)

    # --- init extensions in the right order ---
    db.init_app(app)
    Migrate(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    def _enable_admin_override():
        # DEVELOPMENT ONLY — NEVER ENABLE IN PRODUCTION
        print("DEVELOPMENT ONLY — NEVER ENABLE IN PRODUCTION: admin override enabled")

        @app.before_request
        def _admin_override_user():
            # DEVELOPMENT ONLY — NEVER ENABLE IN PRODUCTION
            g._login_user = AdminOverrideUser()
    
    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Seed demo data if the sentinel record does not exist."""
        seeded = seed_demo_data()
        if seeded:
            print("Seeded demo data.")
        else:
            print("Demo data already present.")
    
    @app.route("/")
    def index():
        recipes = Recipe.query.all()
        featured_recipe = None
        if recipes:
            recipe = random.choice(recipes)
            snippet = (recipe.description or "").strip()
            if not snippet:
                snippet = (recipe.instructions or "").strip()
            if not snippet:
                snippet = (recipe.content or "").strip()

            if snippet:
                max_length = 160
                if len(snippet) > max_length:
                    snippet = f"{snippet[: max_length - 3].rstrip()}..."

            image_url = None
            if recipe.image_filename:
                image_url = url_for("static", filename=recipe.image_filename)

            featured_recipe = {
                "title": recipe.title,
                "snippet": snippet,
                "image_url": image_url,
                "url": url_for("recipe_detail", id_slug=f"{recipe.id}-{recipe.slug}"),
            }

        featured_blog = None
        blog_query = BlogPost.query
        if hasattr(BlogPost, "is_published"):
            blog_query = blog_query.filter_by(is_published=True)
        elif hasattr(BlogPost, "published"):
            blog_query = blog_query.filter_by(published=True)
        elif hasattr(BlogPost, "status"):
            blog_query = blog_query.filter(BlogPost.status == "published")

        post = blog_query.order_by(func.random()).first()
        if post:
            author_name = None
            if post.author:
                full_name = " ".join(
                    part for part in [post.author.first_name, post.author.last_name] if part
                )
                author_name = full_name or post.author.username

            excerpt = (post.content or "").strip()
            if not excerpt:
                excerpt = (post.summary or "").strip()

            if excerpt:
                max_length = 200
                if len(excerpt) > max_length:
                    excerpt = f"{excerpt[: max_length - 3].rstrip()}..."

            published_date = None
            published_iso = None
            if post.created_at:
                published_date = post.created_at.strftime("%b %d, %Y")
                published_iso = post.created_at.date().isoformat()

            featured_blog = {
                "title": post.title,
                "author_name": author_name,
                "published_date": published_date,
                "published_iso": published_iso,
                "excerpt": excerpt,
                "url": url_for("blog_post", slug=post.slug),
            }

        return render_template(
            "index.html",
            featured_recipe=featured_recipe,
            featured_blog=featured_blog,
        )
    
    @app.route("/about")
    def about_us():
        return render_template("about_us.html")

    @app.route("/recipes")
    def recipes():
        # Fetch featured recipes (first 3 or random)
        featured_recipes = Recipe.query.order_by(Recipe.created_at.desc()).limit(3).all()
        return render_template("recipes.html", featured_recipes=featured_recipes)

    @app.route("/blog")
    def blog():
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
        return render_template("blog.html", posts=posts)

    @app.get("/blogs/random")
    def random_blog():
        """Redirect to a random blog post without loading all posts into memory."""
        total = db.session.query(func.count(BlogPost.id)).scalar()
        if not total:
            flash("No blog posts yet — check back soon!", "info")
            return redirect(url_for("index"))

        # COUNT + OFFSET keeps selection in SQL; works on SQLite/Postgres/MySQL
        random_index = random.randint(0, total - 1)
        post = BlogPost.query.order_by(BlogPost.id).offset(random_index).first()
        if not post:
            flash("No blog posts yet — check back soon!", "info")
            return redirect(url_for("index"))

        return redirect(url_for("blog_post", slug=post.slug))

    @app.route("/blog/new", methods=["GET", "POST"])
    @login_required
    def blog_new():
        form = BlogPostForm()
        if form.validate_on_submit():
            post = BlogPost(
                user_id=current_user.id,
                title=form.title.data,
                summary=form.summary.data,
                content=form.content.data,
            )
            try:
                db.session.add(post)
                db.session.commit()
                flash("Blog post published.", "success")
                return redirect(url_for("blog_post", slug=post.slug))
            except SQLAlchemyError as exc:
                db.session.rollback()
                print(f"ERROR saving blog post: {exc}")
                flash("An error occurred while saving the blog post.", "error")

        return render_template("blog_new.html", form=form)

    @app.route("/blog/<slug>")
    def blog_post(slug: str):
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post:
            return render_template("404.html"), 404
        return render_template("blog_post.html", post=post)

    @app.route("/blog/<slug>/edit", methods=["GET", "POST"])
    @login_required
    def blog_edit(slug: str):
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post:
            return render_template("404.html"), 404
        if post.user_id != current_user.id:
            flash("You do not have permission to edit this post.", "error")
            return redirect(url_for("blog_post", slug=post.slug))

        form = BlogPostForm(obj=post)
        if form.validate_on_submit():
            post.title = form.title.data
            post.summary = form.summary.data
            post.content = form.content.data
            try:
                db.session.commit()
                flash("Blog post updated.", "success")
                return redirect(url_for("blog_post", slug=post.slug))
            except SQLAlchemyError as exc:
                db.session.rollback()
                print(f"ERROR updating blog post: {exc}")
                flash("An error occurred while updating the blog post.", "error")

        return render_template("blog_edit.html", form=form, post=post)

    @app.post("/blog/<slug>/delete")
    @login_required
    def blog_delete(slug: str):
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post:
            return render_template("404.html"), 404
        if post.user_id != current_user.id:
            flash("You do not have permission to delete this post.", "error")
            return redirect(url_for("blog_post", slug=post.slug))

        try:
            db.session.delete(post)
            db.session.commit()
            flash("Blog post deleted.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR deleting blog post: {exc}")
            flash("An error occurred while deleting the blog post.", "error")
            return redirect(url_for("blog_post", slug=post.slug))

        return redirect(url_for("blog"))

    @app.route("/contact")
    def contact():
        return render_template("contact.html")
    
    @app.route("/recipes/create", methods=["GET", "POST"])
    @login_required
    def create_recipe_page():
        """Display and handle the recipe creation form (requires login)"""
        form = RecipeForm()
        
        if form.validate_on_submit():
            # Handle image upload if provided
            image_filename = None
            if form.image.data:
                file = form.image.data
                filename = secure_filename(file.filename)
                # Add timestamp to filename to ensure uniqueness
                import uuid
                filename = f"{uuid.uuid4().hex}_{filename}"
                
                # Create uploads directory if it doesn't exist
                upload_dir = os.path.join(app.static_folder, "uploads", "recipes")
                os.makedirs(upload_dir, exist_ok=True)
                
                file.save(os.path.join(upload_dir, filename))
                image_filename = f"uploads/recipes/{filename}"
            
            ingredient_names = request.form.getlist("ingredient_name[]")
            ingredient_ids = request.form.getlist("ingredient_id[]")
            ingredient_qtys = request.form.getlist("ingredient_quantity[]")
            ingredient_units = request.form.getlist("ingredient_unit[]")

            ingredients_payload = []
            if ingredient_names:
                index = load_ingredients_index()
                for idx, raw_name in enumerate(ingredient_names):
                    name_raw = (raw_name or "").strip()
                    if not name_raw:
                        continue
                    raw_id = ingredient_ids[idx] if idx < len(ingredient_ids) else ""
                    ingredient_id = (raw_id or "").strip() or None
                    if not ingredient_id:
                        matched = match_ingredient_id(name_raw, index)
                        if matched:
                            ingredient_id = matched
                        else:
                            ingredient_id = ensure_ingredient_exists_in_assets(name_raw)
                    quantity = ingredient_qtys[idx] if idx < len(ingredient_qtys) else None
                    unit = ingredient_units[idx] if idx < len(ingredient_units) else None
                    ingredients_payload.append(
                        {
                            "name": name_raw,
                            "name_raw": name_raw,
                            "ingredient_id": ingredient_id,
                            "quantity": quantity,
                            "unit": unit,
                        }
                    )

            if ingredients_payload:
                ingredients_normalized = json.dumps(ingredients_payload)
            else:
                # Normalize ingredients: split by newline, strip whitespace, filter empty lines
                ingredients_text = form.ingredients.data or ""
                ingredients_list = [
                    line.strip() 
                    for line in ingredients_text.split("\n") 
                    if line.strip()
                ]
                ingredients_normalized = "\n".join(ingredients_list)
            
            # Create recipe
            recipe = Recipe(
                title=form.title.data,
                instructions=form.instructions.data,
                ingredients=ingredients_normalized,
                image_filename=image_filename,
                prep_time_minutes=form.prep_time_minutes.data,
                cook_time_minutes=form.cook_time_minutes.data,
                estimated_cost=form.estimated_cost.data,
                author_id=current_user.id if current_user.is_authenticated else None,
            )
            
            try:
                db.session.add(recipe)
                db.session.commit()
                flash("Recipe created successfully!", "success")
                return redirect(url_for("recipe_detail", id_slug=f"{recipe.id}-{recipe.slug}"))
            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"ERROR saving recipe: {e}")
                flash("An error occurred while saving the recipe. Please try again.", "error")
        
        return render_template("create_recipe.html", form=form)

    @csrf.exempt
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            try:
                username = (request.form.get("username") or "").strip()
                password = request.form.get("password") or ""
                confirm  = request.form.get("confirmPassword") or ""
                email = (request.form.get("email") or "").strip()
                first_name = (request.form.get("firstName") or "").strip()
                last_name = (request.form.get("lastName") or "").strip()
                dob = request.form.get("dob") or None
                gender = request.form.get("gender") or None

                # Basic validation
                if not username or not password:
                    flash("Missing username or password", "error")
                    return render_template("signup.html"), 400

                if password != confirm:
                    flash("Passwords do not match.", "error")
                    return render_template("signup.html"), 400

                # Check if username already exists
                if User.query.filter_by(username=username).first():
                    flash("That username is already taken. Please choose another.", "error")
                    return render_template("signup.html"), 409
                    
                # Check if email already exists
                if email and User.query.filter_by(email=email).first():
                    flash("Email already registered", "error")
                    return render_template("signup.html"), 409

                # Create the user with all fields
                u = User(
                    username=username,
                    email=email or None,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    gender=gender or None
                )
                
                # Handle date of birth
                if dob:
                    from datetime import datetime as dt
                    try:
                        u.date_of_birth = dt.strptime(dob, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                
                u.set_password(password, ph)
                db.session.add(u)
                db.session.commit()
                
                flash("Account created successfully! Please log in.", "success")
                return redirect(url_for("login"))
            
            except Exception as e:
                db.session.rollback()
                print(f"ERROR during signup: {e}")
                import traceback
                traceback.print_exc()
                flash("An error occurred during signup. Please try again.", "error")
                return render_template("signup.html"), 500

        return render_template("signup.html")

    
    # ---- login manager user loader ----
    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ---- util: JSON & basic validation ----
    def _json():
        return request.get_json(force=True) or {}

    # ---- public: CSRF token for JS (double submit header pattern) ----
    @app.get("/api/auth/csrf-token")
    def csrf_token():
        # Frontend should read this and send it back in header:
        # X-CSRFToken: <value> on POST/PUT/PATCH/DELETE
        return jsonify({"csrfToken": generate_csrf()})

    # ---- auth: register/login/logout/me ----
    @csrf.exempt
    @app.post("/api/auth/register")
    def register():
        data = _json()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"error": "username and password required"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "username already registered"}), 409

        u = User(username=username)
        u.set_password(password, ph)
        db.session.add(u)
        db.session.commit()
        return jsonify({"ok": True})

    @csrf.exempt
    @app.post("/api/auth/login")
    def api_login():
        data = _json()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password, ph):
            return jsonify({"error": "invalid credentials"}), 401

        login_user(user, remember=False, duration=timedelta(hours=8))
        return jsonify({"ok": True})
    
    @csrf.exempt
    @app.route("/login", methods=["GET", "POST"])
    def login():
        # Already logged in? send them home
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            user = User.query.filter_by(username=username).first()
            # NOTE: pass ph here, same as api_login
            if not user or not user.check_password(password, ph):
                flash("Incorrect username or password. Please try again.", "error")
                return render_template("login.html"), 401

            login_user(user, remember=False, duration=timedelta(hours=8))
            return redirect(url_for("index"))

        # GET: just show the form
        return render_template("login.html")

    @app.get("/api/auth/me")
    def me():
        if current_user.is_authenticated:
            return jsonify({"id": current_user.id, "username": current_user.username})
        return jsonify({"id": None, "username": None})

    # ---- RECIPES (unchanged behavior, plus auth on create) ----

    # Create a recipe (JSON: {title, content})
    @csrf.exempt
    @app.post("/api/recipes")
    @login_required
    def create_recipe():
        # Try to parse JSON safely
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        content = data.get("content") or ""

        if not title:
            return jsonify({"error": "title is required"}), 400

        r = Recipe(title=title, content=content)
        db.session.add(r)

        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            # TEMP: print error so you see it in the Flask console
            print("ERROR saving recipe:", e)
            return jsonify({"error": "server error saving recipe", "detail": str(e)}), 500

        return jsonify({"id": r.id, "slug": r.slug, "title": r.title}), 201

    # Canonical detail URL: /recipes/<id>-<slug>
    @app.get("/recipes/<id_slug>")
    def recipe_detail(id_slug: str):
        try:
            rid_str, _, tail = id_slug.partition("-")
            rid = int(rid_str)
        except Exception:
            flash("Recipe not found.", "error")
            return redirect(url_for("recipes"))

        r = db.session.get(Recipe, rid)
        if not r:
            # check old slugs -> redirect
            old = RecipeSlugHistory.query.filter_by(old_slug=tail or id_slug).first()
            if old:
                canonical = f"{old.recipe_id}-{db.session.get(Recipe, old.recipe_id).slug}"
                return redirect(url_for("recipe_detail", id_slug=canonical), code=301)
            flash("Recipe not found.", "error")
            return redirect(url_for("recipes"))

        canonical = f"{r.id}-{r.slug}"
        if id_slug != canonical:
            return redirect(url_for("recipe_detail", id_slug=canonical), code=301)

        def _format_amount(quantity, unit):
            qty = "" if quantity is None else str(quantity).strip()
            uom = "" if unit is None else str(unit).strip()
            if qty and uom:
                return f"{qty} {uom}"
            if qty:
                return qty
            if uom:
                return uom
            return ""

        def _normalize_ingredients(raw):
            if not raw:
                return []

            data = raw
            if isinstance(raw, str):
                text = raw.strip()
                if not text:
                    return []
                if text.startswith("[") or text.startswith("{"):
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        data = text.splitlines()
                else:
                    data = text.splitlines()

            if isinstance(data, dict):
                data = data.get("ingredients") or data.get("items") or []

            if not isinstance(data, list):
                data = [data]

            normalized = []
            for item in data:
                if item is None:
                    continue
                if isinstance(item, str):
                    name = item.strip()
                    if name:
                        normalized.append(
                            {"name": name, "amount": "", "quantity": None, "unit": None}
                        )
                    continue
                if isinstance(item, dict):
                    name = (
                        item.get("name_raw")
                        or item.get("name")
                        or item.get("ingredient")
                        or item.get("title")
                        or ""
                    )
                    name = str(name).strip() if name is not None else ""
                    quantity = item.get("quantity") or item.get("qty") or item.get("amount")
                    unit = item.get("unit") or item.get("units")
                    amount = _format_amount(quantity, unit)
                    if not name and amount:
                        name = amount
                        amount = ""
                    if name:
                        normalized.append(
                            {
                                "name": name,
                                "amount": amount,
                                "quantity": quantity,
                                "unit": unit,
                                "ingredient_id": item.get("ingredient_id") or item.get("id"),
                            }
                        )
                    continue

                name = str(item).strip()
                if name:
                    normalized.append(
                        {"name": name, "amount": "", "quantity": None, "unit": None}
                    )

            return normalized

        def _attach_dietary_tags(ingredients_list):
            if not ingredients_list:
                return ingredients_list
            names = [
                str(item.get("name") or "").strip().lower()
                for item in ingredients_list
                if isinstance(item, dict) and item.get("name")
            ]
            if not names:
                return ingredients_list
            unique_names = sorted({name for name in names if name})
            if not unique_names:
                return ingredients_list
            matches = (
                Ingredient.query.filter(func.lower(Ingredient.name).in_(unique_names))
                .all()
            )
            tag_map = {
                m.name.strip().lower(): [tag.name for tag in m.dietary_tags]
                for m in matches
            }
            for item in ingredients_list:
                if not isinstance(item, dict):
                    continue
                existing = item.get("dietary_tags")
                if existing:
                    continue
                name = str(item.get("name") or "").strip().lower()
                if not name:
                    continue
                tags = tag_map.get(name)
                if tags:
                    item["dietary_tags"] = tags
            return ingredients_list

        ingredients_list = _normalize_ingredients(r.ingredients)
        ingredients_list = _attach_dietary_tags(ingredients_list)
        full_ingredients = list(ingredients_list)

        raw_tags = (request.args.get("tags") or "").strip()
        selected_tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        mode = (request.args.get("mode") or "or").strip()
        filtered_ingredients = filter_ingredients_by_dietary_tags(
            ingredients_list, selected_tags, mode
        )
        filters_applied = bool(selected_tags)
        empty_filter_message = None
        if filters_applied and not filtered_ingredients:
            empty_filter_message = (
                "No ingredients match your selected dietary filters."
            )
        ingredients_list = filtered_ingredients if filters_applied else ingredients_list

        try:
            ingredient_index = load_ingredient_index()
        except Exception as exc:
            print(f"WARNING: Unable to load ingredient nutrition assets: {exc}")
            ingredient_index = {"by_name": {}, "by_id": {}}
        nutrition_totals, nutrition_incomplete = compute_recipe_macros(
            full_ingredients, ingredient_index
        )
        nutrition_note = None
        if nutrition_incomplete and all(
            value == 0.0 for value in nutrition_totals.values()
        ):
            nutrition_note = "Nutrition estimates incomplete (some ingredients missing data)."

        return render_template(
            "recipe_detail.html",
            recipe=r,
            ingredients=ingredients_list,
            nutrition=nutrition_totals,
            nutrition_note=nutrition_note,
            ingredient_filters_applied=filters_applied,
            ingredient_filter_message=empty_filter_message,
            ingredient_filter_clear_url=url_for(
                "recipe_detail", id_slug=f"{r.id}-{r.slug}"
            ),
        )

    @app.get("/recipes/random")
    def random_recipe():
        """Redirect to a random recipe without loading all rows into memory."""
        total = db.session.query(func.count(Recipe.id)).scalar()
        if not total:
            flash("No recipes yet — share one to get started!", "info")
            return redirect(url_for("index"))

        # COUNT + OFFSET keeps selection in SQL for scalability
        random_index = random.randint(0, total - 1)
        recipe = Recipe.query.order_by(Recipe.id).offset(random_index).first()
        if not recipe:
            flash("No recipes yet — share one to get started!", "info")
            return redirect(url_for("index"))

        return redirect(url_for("recipe_detail", id_slug=f"{recipe.id}-{recipe.slug}"))

    # Simple list
    @app.get("/api/recipes")
    def list_recipes():
        rows = Recipe.query.order_by(Recipe.created_at.desc()).all()
        return jsonify([{"id": r.id, "title": r.title, "slug": r.slug} for r in rows])

    @app.get("/api/ingredients/suggest")
    def suggest_ingredients():
        query = (request.args.get("q") or "").strip()
        try:
            limit = int(request.args.get("limit") or 8)
        except ValueError:
            limit = 8
        limit = max(1, min(limit, 20))
        results = search_suggestions(query, limit=limit)
        return jsonify(results)

    @app.get("/api/ingredients")
    def list_ingredients():
        """List ingredients with optional nutrient sorting (missing values sort to bottom)."""
        sort_key = (request.args.get("sort_key") or "").strip() or None
        sort_dir = (request.args.get("sort_dir") or "desc").strip().lower()

        if sort_dir not in ("asc", "desc"):
            return jsonify({"error": "sort_dir must be 'asc' or 'desc'"}), 400

        if sort_key and sort_key not in ALLOWED_NUTRIENT_SORT_KEYS:
            allowed = sorted(ALLOWED_NUTRIENT_SORT_KEYS.keys())
            return (
                jsonify(
                    {
                        "error": f"invalid sort_key '{sort_key}'",
                        "allowed_keys": allowed,
                    }
                ),
                400,
            )

        query = Ingredient.query
        query = build_ingredient_sort(query, sort_key, sort_dir)
        rows = query.all()
        return jsonify(
            [
                {
                    "id": row.id,
                    "name": row.name,
                    "nutrition_per_100g": row.nutrition_per_100g,
                }
                for row in rows
            ]
        )

    @app.get("/api/whoami")
    def whoami():
        if current_user.is_authenticated:
            return {
                "authenticated": True,
                "id": current_user.id,
                "username": current_user.username,
            }
        else:
            return {"authenticated": False}, 200
    
    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404
    
    with app.app_context():
        db.create_all()
        if seed_demo and (
            app.debug or app.testing or app.config.get("ENV") in ("development", "testing")
        ):
            seed_demo_data()

    if app.config.get("ADMIN_OVERRIDE"):
        _enable_admin_override()

    return app

def _parse_args():
    parser = argparse.ArgumentParser(description="Run the Tasty Truths Flask app.")
    parser.add_argument(
        "-A",
        "--admin-override",
        action="store_true",
        help="Enable DEVELOPMENT-ONLY admin override mode.",
    )
    return parser.parse_args()

def _run_dev_server():
    args = _parse_args()
    app = create_app(admin_override=args.admin_override)
    app.run(debug=True, host="0.0.0.0", port=5500)

if __name__ == "__main__":
    _run_dev_server()
else:
    app = create_app()
