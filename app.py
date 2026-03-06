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
import sys
from functools import wraps
from urllib.parse import urlparse
from sqlalchemy import func
from flask import Flask, request, jsonify, redirect, url_for, redirect, render_template, flash, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
from argon2 import PasswordHasher
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
import os
from services.db import db
from services.friendships import (
    FriendshipError,
    add_friendship,
    are_friends,
    create_friend_request,
    get_friend_ids,
    get_friend_count,
    get_friends_for_user,
    get_relationship_summary,
    remove_friendship,
    respond_to_friend_request,
)
from services.models import BlogPost, FriendRequest, Ingredient, Recipe, RecipeSlugHistory, User
from services.forms import RecipeForm, BlogPostForm, SignupForm, ProfileEditForm
from services.ingredients import ALLOWED_NUTRIENT_SORT_KEYS, build_ingredient_sort
from services.ingredient_index import load_ingredients_index, match_ingredient_id, search_suggestions
from services.nutrition import (
    compute_recipe_macros,
    ensure_ingredient_exists_in_assets,
    load_ingredient_index,
    INGREDIENT_ALIASES,
    normalize_ingredient_name,
)
from services.filtering import filter_ingredients_by_dietary_tags
from utilities.seed_demo import seed_demo_data
from utilities.images import save_profile_picture, delete_profile_picture

ph = PasswordHasher()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


# ---- role helpers & decorators ----

ALLOWED_ROLES = {"normal", "moderator", "admin"}


def is_admin(user) -> bool:
    return bool(user) and getattr(user, "role", "normal") == "admin"


def is_staff(user) -> bool:
    role = getattr(user, "role", "normal") or "normal"
    return role in {"moderator", "admin"}


def _forbidden_response(message: str = "You do not have permission to perform this action."):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        return jsonify({"error": "forbidden"}), 403
    flash(message, "error")
    return (render_template("403.html"), 403) if hasattr(sys.modules.get(__name__), "render_template") else (message, 403)


def require_admin(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not is_admin(current_user):
            return _forbidden_response()
        return view_func(*args, **kwargs)

    return wrapped


def require_staff(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not is_staff(current_user):
            return _forbidden_response()
        return view_func(*args, **kwargs)

    return wrapped

COMMON_DIETARY_RESTRICTIONS = [
    "vegan",
    "vegetarian",
    "gluten-free",
    "dairy-free",
    "nut-free",
    "halal",
    "kosher",
    "pescatarian",
]

DEFAULT_PROFILE_IMAGE = "default.png"
PROFILE_PICS_SUBDIR = "uploads/profile_pics"
ALLOWED_PROFILE_PIC_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

class AdminOverrideUser(UserMixin):
    OVERRIDE_USERNAME = "__admin_override__"
    OVERRIDE_DEFAULTS = {
        "email": None,
        "role": "admin",
        "bio": "Development-only admin override account.",
        "experience": "Admin override account with full user capabilities for local development.",
        "experiences": ["Development testing", "Admin override"],
        "dietary_restrictions": [],
        "profile_image": DEFAULT_PROFILE_IMAGE,
    }

    def __init__(self, proxied_user: User):
        object.__setattr__(self, "_proxied_user", proxied_user)

    @classmethod
    def get_or_create_user(cls) -> User:
        user = User.query.filter_by(username=cls.OVERRIDE_USERNAME).first()
        if user is not None:
            changed = False
            for field, default_value in cls.OVERRIDE_DEFAULTS.items():
                current_value = getattr(user, field, None)
                if current_value in (None, ""):
                    setattr(user, field, list(default_value) if isinstance(default_value, list) else default_value)
                    changed = True
            if (user.role or "normal") != "admin":
                user.role = "admin"
                changed = True
            if changed:
                db.session.commit()
            return user

        user = User(username=cls.OVERRIDE_USERNAME, **cls.OVERRIDE_DEFAULTS)
        user.set_password("admin-override")
        db.session.add(user)
        db.session.commit()
        return user

    def __getattr__(self, name):
        return getattr(self._proxied_user, name)

    def __setattr__(self, name, value):
        if name == "_proxied_user":
            object.__setattr__(self, name, value)
            return
        setattr(self._proxied_user, name, value)

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
        UPLOAD_FOLDER=os.path.join("static", "uploads", "profile_pics"),
        UPLOAD_FOLDER_PROFILE_PICS=None,
        PROFILE_PIC_UPLOAD_DIR=os.path.join("static", "uploads", "profile_pics"),
        PROFILE_PIC_ALLOWED_EXTS=ALLOWED_PROFILE_PIC_EXTENSIONS,
        PROFILE_PIC_MAX_W=6000,
        PROFILE_PIC_MAX_H=6000,
        PROFILE_PIC_MAX_PIXELS=20_000_000,
        PROFILE_PIC_OUTPUT_SIZE=(256, 256),
        PROFILE_PIC_OUTPUT_FORMAT="WEBP",
        PROFILE_PIC_OUTPUT_QUALITY=80,
        ALLOWED_PROFILE_PIC_EXTENSIONS=ALLOWED_PROFILE_PIC_EXTENSIONS,
        DEFAULT_PROFILE_IMAGE=DEFAULT_PROFILE_IMAGE,
        PROFILE_PICS_SUBDIR=PROFILE_PICS_SUBDIR,
        # Keep attributes available after commit for request/test flows that
        # access ids outside the original app context.
        SQLALCHEMY_SESSION_OPTIONS={"expire_on_commit": False},
    )
    if config_overrides:
        app.config.update(config_overrides)
    if not app.config.get("UPLOAD_FOLDER_PROFILE_PICS"):
        configured_upload = (
            app.config.get("PROFILE_PIC_UPLOAD_DIR")
            or app.config.get("UPLOAD_FOLDER")
            or os.path.join(
            "static", *app.config["PROFILE_PICS_SUBDIR"].split("/")
        )
        )
        if os.path.isabs(configured_upload):
            app.config["UPLOAD_FOLDER_PROFILE_PICS"] = configured_upload
        else:
            app.config["UPLOAD_FOLDER_PROFILE_PICS"] = os.path.join(
                app.root_path, configured_upload
            )
    os.makedirs(app.config["UPLOAD_FOLDER_PROFILE_PICS"], exist_ok=True)
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
            g._login_user = AdminOverrideUser(
                proxied_user=AdminOverrideUser.get_or_create_user()
            )
    
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

    @app.cli.command("nutrition-check")
    def nutrition_check_command():
        """Self-check: compute nutrition for all recipes and print a summary table."""
        try:
            ingredient_index = load_ingredient_index()
        except Exception as exc:
            print(f"ERROR: Unable to load ingredients asset: {exc}")
            sys.exit(1)

        recipes = Recipe.query.order_by(Recipe.id).all()
        if not recipes:
            print("No recipes in database.")
            sys.exit(0)

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

        all_zero = True
        print("recipe_title | calories | protein_g | fat_g | carbs_g | missing_ingredient_count | skipped_unknown_unit_count | incomplete_count | missing_conversion_count | missing_nutrition_count | zero_nutrition_count")
        for recipe in recipes:
            ingredients = _normalize_ingredients(recipe.ingredients)
            totals, incomplete, stats = compute_recipe_macros(
                ingredients,
                ingredient_index,
                collect_stats=True,
                debug=app.debug,
                recipe_name=recipe.title,
            )
            from collections import Counter
            issue_counts = Counter(line.get("issue") for line in stats.get("lines", []) if line.get("issue"))
            if any(value != 0.0 for value in totals.values()):
                all_zero = False
            print(
                f"{recipe.title} | {round(totals['calories_kcal'], 1)} | {round(totals['protein_g'], 2)} | "
                f"{round(totals['fat_g'], 2)} | {round(totals['carbs_g'], 2)} | "
                f"{stats.get('missing_ingredients', 0)} | {stats.get('skipped_unknown_units', 0)} | "
                f"{issue_counts.get('incomplete', 0)} | {issue_counts.get('missing_conversion', 0)} | "
                f"{issue_counts.get('missing_nutrition', 0)} | {issue_counts.get('zero_nutrition', 0)}"
            )

            # Print first few offending lines
            problematic = [line for line in stats.get("lines", []) if line.get("issue")]
            for line in problematic[:10]:
                print(
                    f"  - {line.get('raw_name')} qty={line.get('raw_quantity')} unit={line.get('raw_unit')} "
                    f"lookup={line.get('normalized_key')} matched={line.get('matched_id')} "
                    f"status={line.get('status')} grams={line.get('grams')} issue={line.get('issue')}"
                )

        if all_zero:
            print("All recipes have zero macro totals — nutrition likely not wired correctly.")
            sys.exit(1)

        # Duplicate audit: incomplete entries whose names match alias keys
        alias_keys = set(INGREDIENT_ALIASES.keys())
        dupes = []
        for entry in ingredient_index.get("raw", []):
            if not isinstance(entry, dict):
                continue
            if entry.get("status") != "incomplete":
                continue
            name_key = normalize_ingredient_name(entry.get("name"))
            if name_key in alias_keys:
                dupes.append(entry.get("name"))
        if dupes:
            print("WARNING: Incomplete duplicates matching aliases:", ", ".join(sorted(set(dupes))))

        sys.exit(0)
    
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

        try:
            ingredient_index = load_ingredient_index()
        except Exception as exc:
            print(f"WARNING: Unable to load ingredient nutrition assets: {exc}")
            ingredient_index = {"by_name": {}, "by_id": {}, "by_alias": {}}

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
                        normalized.append({"name": name, "amount": "", "quantity": None, "unit": None})
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
                    amount = f"{quantity} {unit}".strip() if quantity or unit else ""
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
                    normalized.append({"name": name, "amount": "", "quantity": None, "unit": None})
            return normalized

        for recipe in featured_recipes:
            ingredients = _normalize_ingredients(recipe.ingredients)
            totals, _, _ = compute_recipe_macros(
                ingredients,
                ingredient_index,
                collect_stats=True,
                debug=app.debug,
                recipe_name=recipe.title,
            )
            recipe.nutrition_totals = totals

        return render_template(
            "recipes.html",
            featured_recipes=featured_recipes,
            viewer_friend_ids=_current_user_friend_ids(),
        )

    @app.route("/blog")
    def blog():
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
        return render_template(
            "blog.html",
            posts=posts,
            viewer_friend_ids=_current_user_friend_ids(),
        )

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
        return render_template(
            "blog_post.html",
            post=post,
            viewer_friend_ids=_current_user_friend_ids(),
        )

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
    @require_staff
    def blog_delete(slug: str):
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post:
            return render_template("404.html"), 404
        if not is_staff(current_user) and post.user_id != current_user.id:
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

    def _profile_pic_url(filename: str) -> str:
        clean_name = (filename or "").strip()
        if clean_name != os.path.basename(clean_name):
            clean_name = app.config["DEFAULT_PROFILE_IMAGE"]
        return url_for(
            "static",
            filename=f"{app.config['PROFILE_PICS_SUBDIR']}/{clean_name}",
        )

    def _avatar_url_for_user(user: User) -> str:
        profile_image = (getattr(user, "profile_image", "") or "").strip()
        if not profile_image:
            profile_image = app.config["DEFAULT_PROFILE_IMAGE"]
        return _profile_pic_url(profile_image)

    def _display_recipe_title(recipe: Recipe) -> str:
        raw_title = (getattr(recipe, "title", "") or "").strip()
        author = getattr(recipe, "author", None)
        author_username = (getattr(author, "username", "") or "").strip()
        suffix = f" ({author_username})" if author_username else ""
        if suffix and raw_title.endswith(suffix):
            return raw_title[: -len(suffix)].rstrip()
        return raw_title

    def _bio_snippet_for_user(user: User, max_length: int = 120) -> str:
        snippet = (getattr(user, "bio", "") or "").strip()
        if not snippet:
            return ""
        if len(snippet) <= max_length:
            return snippet
        return f"{snippet[: max_length - 3].rstrip()}..."

    @app.context_processor
    def inject_template_helpers():
        return {
            "avatar_url_for_user": _avatar_url_for_user,
            "display_recipe_title": _display_recipe_title,
            "profile_pic_url": _profile_pic_url,
        }

    def _build_friend_cards(users) -> list[dict]:
        return [
            {
                "user": friend,
                "avatar_url": _avatar_url_for_user(friend),
                "bio_snippet": _bio_snippet_for_user(friend),
            }
            for friend in (users or [])
        ]

    def _current_user_friend_ids() -> set[int]:
        if not current_user.is_authenticated:
            return set()
        cached = getattr(g, "_current_user_friend_ids", None)
        if cached is None:
            cached = get_friend_ids(current_user.id)
            g._current_user_friend_ids = cached
        return cached

    def _safe_redirect_target(target_url: str | None, fallback_url: str):
        if not target_url:
            return redirect(fallback_url)
        normalized = target_url.strip()
        if not normalized or normalized.startswith("//"):
            return redirect(fallback_url)
        parsed = urlparse(normalized)
        if parsed.scheme or parsed.netloc:
            if parsed.netloc != request.host:
                return redirect(fallback_url)
            path = parsed.path or "/"
            if not path.startswith("/"):
                return redirect(fallback_url)
            if parsed.query:
                path = f"{path}?{parsed.query}"
            return redirect(path)
        if normalized.startswith("/"):
            return redirect(normalized)
        return redirect(fallback_url)

    def _redirect_back(fallback_url: str):
        target = (
            (request.form.get("next") or "").strip()
            or (request.args.get("next") or "").strip()
            or (request.referrer or "").strip()
        )
        return _safe_redirect_target(target, fallback_url)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(_exc):
        flash("Image too large. Maximum upload size is 2MB.", "error")
        endpoint = request.endpoint or ""
        if endpoint == "signup":
            return redirect(url_for("signup"))
        if endpoint in {
            "edit_public_profile",
            "update_profile_picture",
            "update_profile_bio_public",
            "update_profile_experience",
            "update_profile_dietary",
            "update_my_profile_picture",
            "update_my_profile_bio",
            "update_my_profile_experience",
            "update_my_profile_dietary",
        }:
            username = (request.view_args or {}).get("username")
            if username:
                return redirect(url_for("public_profile", username=username))
            return redirect(url_for("profile_page"))
        return ("Request entity too large", 413)

    def _resolve_profile_user(username: str):
        normalized_username = (username or "").strip().lower()
        if not normalized_username:
            return None

        profile_user = User.query.filter(
            func.lower(User.username) == normalized_username
        ).first()
        return profile_user

    def require_profile_owner(username: str):
        profile_user = _resolve_profile_user(username)
        if profile_user is None:
            return None, (render_template("404.html"), 404)
        if not current_user.is_authenticated:
            return None, login_manager.unauthorized()
        if current_user.id != profile_user.id:
            return None, _forbidden_response()
        return profile_user, None

    @app.post("/friends/add/<username>")
    @login_required
    def add_friend(username: str):
        target_user = _resolve_profile_user(username)
        if target_user is None:
            flash("User not found.", "error")
            return _redirect_back(url_for("friends_page"))
        if target_user.id == current_user.id:
            flash("You cannot add yourself as a friend.", "error")
            return _redirect_back(url_for("public_profile", username=current_user.username))

        try:
            add_friendship(current_user, target_user)
            db.session.commit()
            if hasattr(g, "_current_user_friend_ids"):
                g._current_user_friend_ids = None
            flash(f"You are now friends with {target_user.username}.", "success")
        except FriendshipError as exc:
            db.session.rollback()
            flash(exc.message, "error")
        except IntegrityError:
            db.session.rollback()
            flash("That friendship already exists.", "info")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR adding friend: {exc}")
            flash("Unable to add friend right now.", "error")

        return _redirect_back(url_for("public_profile", username=target_user.username))

    @app.post("/friends/remove/<username>")
    @login_required
    def remove_friend(username: str):
        target_user = _resolve_profile_user(username)
        if target_user is None:
            flash("User not found.", "error")
            return _redirect_back(url_for("friends_page"))

        try:
            removed = remove_friendship(current_user, target_user)
            db.session.commit()
            if hasattr(g, "_current_user_friend_ids"):
                g._current_user_friend_ids = None
            if removed:
                flash(f"Removed {target_user.username} from your friends.", "success")
            else:
                flash(f"You were not friends with {target_user.username}.", "info")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR removing friend: {exc}")
            flash("Unable to remove friend right now.", "error")

        return _redirect_back(url_for("public_profile", username=target_user.username))

    @app.get("/friends")
    @login_required
    def friends_page():
        friends = get_friends_for_user(current_user.id)
        return render_template(
            "friends.html",
            page_title="My Friends",
            page_user=current_user,
            friend_cards=_build_friend_cards(friends),
            friend_count=len(friends),
            viewer_friend_ids=_current_user_friend_ids(),
            is_own_friends_page=True,
        )

    @app.get("/profile/<username>/friends")
    def profile_friends(username: str):
        profile_user = _resolve_profile_user(username)
        if profile_user is None:
            return render_template("404.html"), 404

        viewer_friend_ids = _current_user_friend_ids()
        friends = get_friends_for_user(profile_user.id)
        return render_template(
            "friends.html",
            page_title=f"{profile_user.username}'s Friends",
            page_user=profile_user,
            friend_cards=_build_friend_cards(friends),
            friend_count=len(friends),
            viewer_friend_ids=viewer_friend_ids,
            is_own_friends_page=current_user.is_authenticated and current_user.id == profile_user.id,
        )

    @app.get("/profile/<username>")
    def public_profile(username: str):
        profile_user = _resolve_profile_user(username)
        if profile_user is None:
            return render_template("404.html"), 404

        recent_blog_posts = (
            BlogPost.query.filter_by(user_id=profile_user.id)
            .order_by(BlogPost.created_at.desc())
            .limit(5)
            .all()
        )

        experience_text = (profile_user.experience or "").strip()
        if not experience_text:
            legacy_experiences = profile_user.experiences or []
            if isinstance(legacy_experiences, str):
                try:
                    legacy_experiences = json.loads(legacy_experiences)
                except json.JSONDecodeError:
                    legacy_experiences = [
                        line.strip() for line in legacy_experiences.splitlines() if line.strip()
                    ]
            if isinstance(legacy_experiences, list):
                normalized_legacy = [
                    str(item).strip() for item in legacy_experiences if str(item).strip()
                ]
                if normalized_legacy:
                    experience_text = "\n".join(normalized_legacy)

        dietary_restrictions = [
            str(item).strip()
            for item in (profile_user.dietary_restrictions or [])
            if str(item).strip()
        ]

        avatar_url = _avatar_url_for_user(profile_user)
        is_owner = current_user.is_authenticated and current_user.id == profile_user.id
        profile_friends = get_friends_for_user(profile_user.id)
        viewer_friend_ids = _current_user_friend_ids()

        return render_template(
            "profile_public.html",
            profile_user=profile_user,
            experience_text=experience_text,
            dietary_restrictions=dietary_restrictions,
            common_dietary_restrictions=COMMON_DIETARY_RESTRICTIONS,
            avatar_url=avatar_url,
            is_owner=is_owner,
            friend_count=len(profile_friends),
            friend_cards=_build_friend_cards(profile_friends),
            viewer_friend_ids=viewer_friend_ids,
            recent_blog_posts=recent_blog_posts,
        )

    @app.post("/profile/<username>/picture")
    @login_required
    def update_profile_picture(username: str):
        profile_user, unauthorized_response = require_profile_owner(username)
        if unauthorized_response is not None:
            return unauthorized_response

        uploaded_file = request.files.get("profile_picture")
        if not uploaded_file or not (uploaded_file.filename or "").strip():
            flash("Please choose a profile picture to upload.", "error")
            return redirect(url_for("public_profile", username=profile_user.username))

        old_profile_image = (profile_user.profile_image or "").strip()
        new_profile_image = None
        try:
            new_profile_image = save_profile_picture(uploaded_file)
            profile_user.profile_image = new_profile_image
            db.session.commit()
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("public_profile", username=profile_user.username))
        except SQLAlchemyError as exc:
            db.session.rollback()
            if new_profile_image:
                delete_profile_picture(new_profile_image)
            print(f"ERROR saving profile picture: {exc}")
            flash("Unable to save profile picture right now.", "error")
            return redirect(url_for("public_profile", username=profile_user.username))

        if old_profile_image and old_profile_image != new_profile_image:
            delete_profile_picture(old_profile_image)

        flash("Profile picture updated.", "success")
        return redirect(url_for("public_profile", username=profile_user.username))

    @app.post("/profile/<username>/bio")
    @login_required
    def update_profile_bio_public(username: str):
        profile_user, unauthorized_response = require_profile_owner(username)
        if unauthorized_response is not None:
            return unauthorized_response

        bio = (request.form.get("bio") or "").strip()
        if len(bio) > 500:
            flash("Bio is too long (max 500 characters).", "error")
            return redirect(url_for("public_profile", username=profile_user.username))

        profile_user.bio = bio
        try:
            db.session.commit()
            flash("Bio updated.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving bio: {exc}")
            flash("Unable to save bio right now.", "error")
        return redirect(url_for("public_profile", username=profile_user.username))

    @app.post("/profile/<username>/experience")
    @login_required
    def update_profile_experience(username: str):
        profile_user, unauthorized_response = require_profile_owner(username)
        if unauthorized_response is not None:
            return unauthorized_response

        experience = (request.form.get("experience") or "").strip()
        if len(experience) > 1500:
            flash("Experience is too long (max 1500 characters).", "error")
            return redirect(url_for("public_profile", username=profile_user.username))

        profile_user.experience = experience
        try:
            db.session.commit()
            flash("Experience updated.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving experience: {exc}")
            flash("Unable to save experience right now.", "error")
        return redirect(url_for("public_profile", username=profile_user.username))

    @app.post("/profile/<username>/dietary")
    @login_required
    def update_profile_dietary(username: str):
        profile_user, unauthorized_response = require_profile_owner(username)
        if unauthorized_response is not None:
            return unauthorized_response

        values = [str(item).strip().lower() for item in request.form.getlist("dietary_restrictions")]
        custom_restriction = (request.form.get("custom_restriction") or "").strip()

        if custom_restriction:
            normalized_custom = " ".join(custom_restriction.lower().split())
            if not normalized_custom:
                flash("Custom dietary restriction cannot be empty.", "error")
                return redirect(url_for("public_profile", username=profile_user.username))
            if len(normalized_custom) > User.MAX_DIETARY_RESTRICTION_LENGTH:
                flash(
                    f"Custom dietary restriction must be {User.MAX_DIETARY_RESTRICTION_LENGTH} characters or fewer.",
                    "error",
                )
                return redirect(url_for("public_profile", username=profile_user.username))
            if any(not (ch.isalnum() or ch in {" ", "-"}) for ch in normalized_custom):
                flash(
                    "Custom dietary restriction can only include letters, numbers, spaces, and hyphens.",
                    "error",
                )
                return redirect(url_for("public_profile", username=profile_user.username))
            values.append(normalized_custom)

        normalized = []
        seen = set()
        for value in values:
            cleaned = " ".join((value or "").strip().lower().split())
            if not cleaned:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)

        if len(normalized) > User.MAX_DIETARY_RESTRICTIONS:
            flash(
                f"You can save up to {User.MAX_DIETARY_RESTRICTIONS} dietary restrictions.",
                "error",
            )
            return redirect(url_for("public_profile", username=profile_user.username))

        profile_user.dietary_restrictions = normalized
        try:
            db.session.commit()
            flash("Dietary restrictions updated.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving dietary restrictions: {exc}")
            flash("Unable to save dietary restrictions right now.", "error")
        return redirect(url_for("public_profile", username=profile_user.username))

    @app.get("/profile/<username>/blogs")
    def profile_blogs(username: str):
        normalized_username = (username or "").strip().lower()
        if not normalized_username:
            return render_template("404.html"), 404

        profile_user = User.query.filter(
            func.lower(User.username) == normalized_username
        ).first()
        if not profile_user:
            return render_template("404.html"), 404

        posts = (
            BlogPost.query.filter_by(user_id=profile_user.id)
            .order_by(BlogPost.created_at.desc())
            .all()
        )
        return render_template(
            "profile_blogs.html",
            profile_user=profile_user,
            posts=posts,
            viewer_friend_ids=_current_user_friend_ids(),
        )

    @app.route("/profile/<username>/edit", methods=["GET", "POST"])
    @login_required
    def edit_public_profile(username: str):
        requested_username = (username or "").strip().lower()
        current_username = (current_user.username or "").strip().lower()
        if requested_username != current_username:
            return _forbidden_response()

        profile_user = User.query.filter(
            func.lower(User.username) == requested_username
        ).first()
        if not profile_user:
            return render_template("404.html"), 404

        def _normalize_experiences_for_storage(text_value: str):
            max_items = 20
            max_item_length = 120
            lines = [line.strip() for line in (text_value or "").splitlines() if line.strip()]
            deduped = []
            seen = set()
            for line in lines:
                normalized = " ".join(line.split())
                if not normalized:
                    continue
                if len(normalized) > max_item_length:
                    return None, f"Each experience must be {max_item_length} characters or fewer."
                lowered = normalized.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                deduped.append(normalized)
            if len(deduped) > max_items:
                return None, f"You can list up to {max_items} experiences."
            return deduped, None

        form = ProfileEditForm()
        if form.validate_on_submit():
            bio = (form.bio.data or "").strip()
            experiences_text = form.experiences_text.data or ""
            uploaded_file = form.profile_picture.data
            new_profile_image = None
            old_profile_image = (profile_user.profile_image or "").strip()

            experiences, experiences_error = _normalize_experiences_for_storage(experiences_text)
            if experiences_error:
                form.experiences_text.errors.append(experiences_error)
                avatar_url = _avatar_url_for_user(profile_user)
                return (
                    render_template(
                        "profile_edit.html",
                        profile_user=profile_user,
                        experiences_text=experiences_text,
                        avatar_url=avatar_url,
                        form=form,
                    ),
                    400,
                )

            if uploaded_file and uploaded_file.filename:
                try:
                    # Server-side validation + normalization to WEBP avatar happens here.
                    new_profile_image = save_profile_picture(uploaded_file)
                except ValueError as exc:
                    form.profile_picture.errors.append(str(exc))
                    avatar_url = _avatar_url_for_user(profile_user)
                    return (
                        render_template(
                            "profile_edit.html",
                            profile_user=profile_user,
                            experiences_text=experiences_text,
                            avatar_url=avatar_url,
                            form=form,
                        ),
                        400,
                    )

            profile_user.bio = bio
            if new_profile_image:
                profile_user.profile_image = new_profile_image
            elif not (profile_user.profile_image or "").strip():
                profile_user.profile_image = app.config["DEFAULT_PROFILE_IMAGE"]
            profile_user.experiences = experiences
            try:
                db.session.commit()
                if new_profile_image and old_profile_image != new_profile_image:
                    delete_profile_picture(old_profile_image)
                flash(
                    "Profile picture updated." if new_profile_image else "Profile updated.",
                    "success",
                )
            except SQLAlchemyError as exc:
                db.session.rollback()
                if new_profile_image:
                    delete_profile_picture(new_profile_image)
                print(f"ERROR saving profile: {exc}")
                flash("Unable to save profile right now.", "error")
                return redirect(url_for("edit_public_profile", username=profile_user.username))

            return redirect(url_for("public_profile", username=profile_user.username))

        if request.method == "POST":
            avatar_url = _avatar_url_for_user(profile_user)
            return (
                render_template(
                    "profile_edit.html",
                    profile_user=profile_user,
                    experiences_text=form.experiences_text.data or "",
                    avatar_url=avatar_url,
                    form=form,
                ),
                400,
            )

        existing_experiences = profile_user.experiences
        if not isinstance(existing_experiences, list):
            existing_experiences = []
        experiences_text = "\n".join(
            str(item).strip() for item in existing_experiences if str(item).strip()
        )
        form.bio.data = profile_user.bio or ""
        form.experiences_text.data = experiences_text
        return render_template(
            "profile_edit.html",
            profile_user=profile_user,
            experiences_text=experiences_text,
            avatar_url=_avatar_url_for_user(profile_user),
            form=form,
        )
    
    @app.route("/profile_page")
    def profile_page():
        profile_user = current_user if current_user.is_authenticated else None
        user_recipes = []
        dietary_restrictions = []
        experience_text = ""
        profile_friends = []
        if profile_user:
            user_recipes = (
                Recipe.query.filter_by(author_id=profile_user.id)
                .order_by(Recipe.created_at.desc())
                .all()
            )
            dietary_restrictions = list(profile_user.dietary_restrictions or [])
            experience_text = (profile_user.experience or "").strip()
            profile_friends = get_friends_for_user(profile_user.id)
            if not experience_text:
                legacy_experiences = profile_user.experiences or []
                if isinstance(legacy_experiences, list):
                    cleaned = [str(item).strip() for item in legacy_experiences if str(item).strip()]
                    experience_text = "\n".join(cleaned)
        return render_template(
            "profile_page.html",
            user=profile_user,
            profile_user=profile_user,
            avatar_url=_avatar_url_for_user(profile_user) if profile_user else _profile_pic_url(app.config["DEFAULT_PROFILE_IMAGE"]),
            user_recipes=user_recipes,
            dietary_restrictions=dietary_restrictions,
            common_dietary_restrictions=COMMON_DIETARY_RESTRICTIONS,
            is_owner=bool(profile_user and current_user.is_authenticated and current_user.id == profile_user.id),
            experience_text=experience_text,
            friend_count=len(profile_friends),
            friend_cards=_build_friend_cards(profile_friends),
        )

    @app.post("/profile/picture")
    @login_required
    def update_my_profile_picture():
        profile_user = current_user
        app.logger.info(
            "profile update route=picture current_user=%s target_user=%s",
            getattr(current_user, "username", None),
            getattr(profile_user, "username", None),
        )
        uploaded_file = request.files.get("profile_picture")
        if not uploaded_file or not (uploaded_file.filename or "").strip():
            flash("Please choose a profile picture to upload.", "error")
            return redirect(url_for("profile_page"))

        old_profile_image = (profile_user.profile_image or "").strip()
        new_profile_image = None
        try:
            new_profile_image = save_profile_picture(uploaded_file)
            profile_user.profile_image = new_profile_image
            db.session.commit()
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("profile_page"))
        except SQLAlchemyError as exc:
            db.session.rollback()
            if new_profile_image:
                delete_profile_picture(new_profile_image)
            print(f"ERROR saving profile picture: {exc}")
            flash("Unable to save profile picture right now.", "error")
            return redirect(url_for("profile_page"))

        if old_profile_image and old_profile_image != new_profile_image:
            delete_profile_picture(old_profile_image)
        flash("Profile picture updated.", "success")
        return redirect(url_for("profile_page"))

    @app.post("/profile/bio")
    @login_required
    def update_my_profile_bio():
        app.logger.info(
            "profile update route=bio current_user=%s target_user=%s",
            getattr(current_user, "username", None),
            getattr(current_user, "username", None),
        )
        bio = (request.form.get("bio") or "").strip()
        if len(bio) > 500:
            flash("Bio is too long (max 500 characters).", "error")
            return redirect(url_for("profile_page"))
        current_user.bio = bio
        try:
            db.session.commit()
            flash("Bio updated.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving bio: {exc}")
            flash("Unable to save bio right now.", "error")
        return redirect(url_for("profile_page"))

    @app.post("/profile/experience")
    @login_required
    def update_my_profile_experience():
        app.logger.info(
            "profile update route=experience current_user=%s target_user=%s",
            getattr(current_user, "username", None),
            getattr(current_user, "username", None),
        )
        experience = (request.form.get("experience") or "").strip()
        if len(experience) > 1500:
            flash("Experience is too long (max 1500 characters).", "error")
            return redirect(url_for("profile_page"))
        current_user.experience = experience
        try:
            db.session.commit()
            flash("Experience updated.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving experience: {exc}")
            flash("Unable to save experience right now.", "error")
        return redirect(url_for("profile_page"))

    @app.post("/profile/dietary")
    @login_required
    def update_my_profile_dietary():
        app.logger.info(
            "profile update route=dietary current_user=%s target_user=%s",
            getattr(current_user, "username", None),
            getattr(current_user, "username", None),
        )
        raw_json = (request.form.get("dietary_restrictions_json") or "").strip()
        values = None
        if raw_json:
            try:
                values = json.loads(raw_json)
            except json.JSONDecodeError:
                flash("Dietary restrictions payload is invalid.", "error")
                return redirect(url_for("profile_page"))
        else:
            values = request.form.getlist("dietary_restrictions")

        custom_restriction = (request.form.get("custom_restriction") or "").strip()
        if custom_restriction:
            normalized_custom = " ".join(custom_restriction.lower().split())
            if not normalized_custom:
                flash("Custom dietary restriction cannot be empty.", "error")
                return redirect(url_for("profile_page"))
            if len(normalized_custom) > User.MAX_DIETARY_RESTRICTION_LENGTH:
                flash(
                    f"Custom dietary restriction must be {User.MAX_DIETARY_RESTRICTION_LENGTH} characters or fewer.",
                    "error",
                )
                return redirect(url_for("profile_page"))
            if any(not (ch.isalnum() or ch in {" ", "-"}) for ch in normalized_custom):
                flash(
                    "Custom dietary restriction can only include letters, numbers, spaces, and hyphens.",
                    "error",
                )
                return redirect(url_for("profile_page"))
            if not isinstance(values, list):
                values = []
            values.append(normalized_custom)

        normalized, error = User.normalize_dietary_restrictions(values)
        if error:
            flash(error, "error")
            return redirect(url_for("profile_page"))

        current_user.dietary_restrictions = normalized
        try:
            db.session.commit()
            flash("Dietary restrictions saved.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving dietary restrictions: {exc}")
            flash("Unable to save dietary restrictions right now.", "error")
        return redirect(url_for("profile_page"))

    @app.post("/users/<int:user_id>/delete")
    @login_required
    @require_admin
    def delete_account(user_id: int):
        user = db.session.get(User, user_id)
        if not user:
            return render_template("404.html"), 404
        try:
            db.session.delete(user)
            db.session.commit()
            flash("User account deleted.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR deleting user: {exc}")
            flash("Unable to delete user right now.", "error")
            return redirect(url_for("profile_page"))
        return redirect(url_for("index"))

    @app.post("/profile_page/dietary_restrictions")
    @login_required
    def update_profile_dietary_restrictions():
        raw_json = (request.form.get("dietary_restrictions_json") or "").strip()
        values = None
        if raw_json:
            try:
                values = json.loads(raw_json)
            except json.JSONDecodeError:
                flash("Dietary restrictions payload is invalid.", "error")
                return redirect(url_for("profile_page"))
        else:
            values = request.form.getlist("dietary_restrictions")

        normalized, error = User.normalize_dietary_restrictions(values)
        if error:
            flash(error, "error")
            return redirect(url_for("profile_page"))

        current_user.dietary_restrictions = normalized
        try:
            db.session.commit()
            flash("Dietary restrictions saved.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving dietary restrictions: {exc}")
            flash("Unable to save dietary restrictions right now.", "error")
        return redirect(url_for("profile_page"))
    
    @app.post("/profile_page/bio")
    @login_required
    def update_profile_bio():
        """Handles updating the user's bio from the profile page."""
        bio = (request.form.get("bio") or "").strip()

        # Optional limit (matches your textarea maxlength) to prevent database bloat
        if len(bio) > 255:
            flash("Bio is too long (max 255 characters).", "error")
            return redirect(url_for("profile_page"))

        current_user.bio = bio

        try:
            db.session.commit()
            flash("Bio saved.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving bio: {exc}")
            flash("Unable to save bio right now.", "error")

        return redirect(url_for("profile_page"))
    
    @app.route("/recipes/create", methods=["GET", "POST"])
    @login_required
    def create_recipe_page():
        """Display and handle the recipe creation form (requires login)"""
        form = RecipeForm()
        # Expected POST shape:
        # WTForms fields: title, instructions, ingredients, image, prep_time_minutes,
        # cook_time_minutes, estimated_cost.
        # Dynamic ingredient UI sends row arrays: ingredient_name[], ingredient_id[],
        # ingredient_quantity[], ingredient_unit[].
        ingredient_names = request.form.getlist("ingredient_name[]")
        ingredient_ids = request.form.getlist("ingredient_id[]")
        ingredient_qtys = request.form.getlist("ingredient_quantity[]")
        ingredient_units = request.form.getlist("ingredient_unit[]")

        if request.method == "POST":
            app.logger.debug(
                "Create recipe payload keys: form=%s files=%s json=%s",
                sorted(request.form.keys()),
                sorted(request.files.keys()),
                sorted((request.get_json(silent=True) or {}).keys()),
            )
            app.logger.debug(
                "Create recipe form values: title=%r instructions_len=%s prep=%r cook=%r cost=%r",
                (request.form.get("title") or "").strip(),
                len((request.form.get("instructions") or "").strip()),
                request.form.get("prep_time_minutes"),
                request.form.get("cook_time_minutes"),
                request.form.get("estimated_cost"),
            )
            normalized_names = [name.strip() for name in ingredient_names if (name or "").strip()]
            if normalized_names and not (form.ingredients.data or "").strip():
                # Ingredient rows are authoritative; mirror them into the hidden field
                # so WTForms validation behaves consistently.
                form.ingredients.data = "\n".join(normalized_names)

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

            app.logger.debug(
                "Create recipe parsed ingredients: count=%s sample=%r",
                len(ingredients_payload),
                ingredients_payload[:3],
            )
            
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
                app.logger.debug("Create recipe calling db.session.add for title=%r", recipe.title)
                db.session.add(recipe)
                app.logger.debug("Create recipe calling db.session.commit")
                db.session.commit()
                detail_url = url_for("recipe_detail", id_slug=f"{recipe.id}-{recipe.slug}")
                app.logger.debug(
                    "Create recipe commit succeeded id=%s slug=%s redirect=%s",
                    recipe.id,
                    recipe.slug,
                    detail_url,
                )
                flash("Recipe created successfully!", "success")
                return redirect(detail_url)
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.exception("Create recipe database error: %s", e)
                flash("An error occurred while saving the recipe. Please try again.", "error")
                return render_template("create_recipe.html", form=form), 500
            except Exception as exc:
                db.session.rollback()
                app.logger.exception("Create recipe unexpected error: %s", exc)
                flash("An unexpected error occurred while saving the recipe.", "error")
                return render_template("create_recipe.html", form=form), 500

        if request.method == "POST":
            app.logger.debug("Create recipe validation errors: %s", form.errors)
            return render_template("create_recipe.html", form=form), 400

        return render_template("create_recipe.html", form=form)

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        form = SignupForm()
        if request.method == "POST":
            if not form.validate():
                return render_template("signup.html", form=form), 400

            uploaded_file = form.profile_picture.data
            saved_profile_image = None
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
                    return render_template("signup.html", form=form), 400

                if password != confirm:
                    flash("Passwords do not match.", "error")
                    return render_template("signup.html", form=form), 400

                # Check if username already exists
                if User.query.filter_by(username=username).first():
                    flash("That username is already taken. Please choose another.", "error")
                    return render_template("signup.html", form=form), 409
                    
                # Check if email already exists
                if email and User.query.filter_by(email=email).first():
                    flash("Email already registered", "error")
                    return render_template("signup.html", form=form), 409

                # Create the user with all fields
                u = User(
                    username=username,
                    email=email or None,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    gender=gender or None,
                    role="normal",
                    profile_image=app.config["DEFAULT_PROFILE_IMAGE"],
                )

                if uploaded_file and uploaded_file.filename:
                    try:
                        saved_profile_image = save_profile_picture(uploaded_file)
                    except ValueError as exc:
                        form.profile_picture.errors.append(str(exc))
                        return render_template("signup.html", form=form), 400
                
                # Handle date of birth
                if dob:
                    from datetime import datetime as dt
                    try:
                        u.date_of_birth = dt.strptime(dob, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                
                u.set_password(password, ph)
                db.session.add(u)
                if saved_profile_image:
                    u.profile_image = saved_profile_image

                db.session.commit()
                
                flash("Account created successfully! Please log in.", "success")
                return redirect(url_for("login"))
            
            except Exception as e:
                db.session.rollback()
                if saved_profile_image:
                    delete_profile_picture(saved_profile_image)
                print(f"ERROR during signup: {e}")
                import traceback
                traceback.print_exc()
                flash("An error occurred during signup. Please try again.", "error")
                return render_template("signup.html", form=form), 500

        return render_template("signup.html", form=form)

    
    # ---- login manager user loader ----
    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ---- util: JSON & basic validation ----
    def _json():
        return request.get_json(force=True) or {}

    def _friend_auth_error():
        return jsonify({"error": "authentication required"}), 401

    @app.post("/api/friends/request")
    def api_friends_request():
        if not current_user.is_authenticated:
            return _friend_auth_error()

        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        recipient = _resolve_profile_user(username)
        if recipient is None:
            return jsonify({"error": "Recipient user does not exist."}), 400
        if recipient.id == current_user.id:
            return jsonify({"error": "You cannot add yourself as a friend."}), 400

        try:
            friend_request = create_friend_request(current_user.id, recipient.id)
            db.session.commit()
        except FriendshipError as exc:
            db.session.rollback()
            return jsonify({"error": exc.message, "code": exc.error_code}), exc.status_code
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR creating friend request: {exc}")
            return jsonify({"error": "Unable to create friend request right now."}), 500

        return (
            jsonify(
                {
                    "status": friend_request.status,
                    "request_id": friend_request.id,
                    "friend_count": get_friend_count(current_user.id),
                    "relationship_state": "outgoing_pending",
                }
            ),
            201,
        )

    @app.post("/api/friends/respond")
    def api_friends_respond():
        if not current_user.is_authenticated:
            return _friend_auth_error()

        data = request.get_json(silent=True) or {}
        request_id = data.get("request_id")
        action = (data.get("action") or "").strip().lower()
        try:
            request_id = int(request_id)
        except (TypeError, ValueError):
            return jsonify({"error": "request_id must be an integer."}), 400

        friend_request = db.session.get(FriendRequest, request_id)
        if friend_request is None:
            return jsonify({"error": "Friend request not found."}), 404

        try:
            status = respond_to_friend_request(friend_request, current_user.id, action)
            db.session.commit()
        except FriendshipError as exc:
            db.session.rollback()
            return jsonify({"error": exc.message, "code": exc.error_code}), exc.status_code
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR responding to friend request: {exc}")
            return jsonify({"error": "Unable to update friend request right now."}), 500

        return jsonify(
            {
                "status": status,
                "request_id": friend_request.id,
                "friend_count": get_friend_count(current_user.id),
                "requester_friend_count": get_friend_count(friend_request.requester_id),
                "relationship_state": "friends" if status == "accepted" else "none",
            }
        )

    @app.get("/api/friends/summary")
    def api_friends_summary():
        username = (request.args.get("username") or "").strip()
        profile_user = _resolve_profile_user(username)
        if profile_user is None:
            return jsonify({"error": "User not found."}), 404

        viewer_user_id = current_user.id if current_user.is_authenticated else None
        summary = get_relationship_summary(viewer_user_id, profile_user.id)
        return jsonify(
            {
                "username": profile_user.username,
                "friend_count": summary["friend_count"],
                "relationship_state": summary["relationship_state"],
                "request_id": summary["request_id"],
            }
        )

    @app.get("/api/users/<int:user_id>/dietary-restrictions")
    @login_required
    def get_user_dietary_restrictions(user_id: int):
        if current_user.id != user_id:
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"dietary_restrictions": current_user.dietary_restrictions or []})

    @csrf.exempt
    @app.put("/api/users/<int:user_id>/dietary-restrictions")
    @login_required
    def update_user_dietary_restrictions(user_id: int):
        if current_user.id != user_id:
            return jsonify({"error": "forbidden"}), 403

        data = request.get_json(silent=True) or {}
        normalized, error = User.normalize_dietary_restrictions(
            data.get("dietary_restrictions")
        )
        if error:
            return jsonify({"error": error}), 400

        current_user.dietary_restrictions = normalized
        try:
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR saving dietary restrictions: {exc}")
            return jsonify({"error": "unable to save dietary restrictions"}), 500

        return jsonify({"ok": True, "dietary_restrictions": normalized})

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

        u = User(
            username=username,
            role="normal",
            profile_image=app.config["DEFAULT_PROFILE_IMAGE"],
        )
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

        detail_url = url_for("recipe_detail", id_slug=f"{r.id}-{r.slug}")
        response = jsonify({"id": r.id, "slug": r.slug, "title": r.title, "url": detail_url})
        response.status_code = 201
        response.headers["Location"] = detail_url
        return response

    @app.post("/recipes/<int:recipe_id>/delete")
    @login_required
    def delete_recipe(recipe_id: int):
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            return render_template("404.html"), 404
        if not (is_staff(current_user) or recipe.author_id == current_user.id):
            return _forbidden_response()
        try:
            db.session.delete(recipe)
            db.session.commit()
            flash("Recipe deleted.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"ERROR deleting recipe: {exc}")
            flash("Unable to delete recipe right now.", "error")
            return redirect(url_for("recipe_detail", id_slug=f"{recipe.id}-{recipe.slug}"))
        return redirect(url_for("recipes"))

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
            full_ingredients,
            ingredient_index,
            debug=app.debug,
            recipe_name=r.title,
        )
        nutrition_note = None
        if nutrition_incomplete and all(
            value == 0.0 for value in nutrition_totals.values()
        ):
            nutrition_note = "Nutrition estimates incomplete (some ingredients missing data)."

        return render_template(
            "recipe_detail.html",
            recipe=r,
            recipe_author=r.author,
            ingredients=ingredients_list,
            nutrition=nutrition_totals,
            nutrition_note=nutrition_note,
            ingredient_filters_applied=filters_applied,
            ingredient_filter_message=empty_filter_message,
            ingredient_filter_clear_url=url_for(
                "recipe_detail", id_slug=f"{r.id}-{r.slug}"
            ),
            viewer_friend_ids=_current_user_friend_ids(),
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
        return jsonify(
            [
                {
                    "id": r.id,
                    "title": r.title,
                    "display_title": _display_recipe_title(r),
                    "slug": r.slug,
                    "description": r.description or "",
                    "author_name": r.author.username if r.author else "",
                    "author_username": r.author.username if r.author else "",
                    "author_avatar_url": _avatar_url_for_user(r.author) if r.author else "",
                    "cuisine": r.cuisine or "",
                    "prep_time_minutes": r.prep_time_minutes,
                    "cook_time_minutes": r.cook_time_minutes,
                    "total_time_minutes": r.total_time_minutes,
                    "ingredients": r.ingredients or "",
                    "dietary_tags": r.dietary_tags or [],
                    "image_filename": r.image_filename or "",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        )

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
    if "pytest" in sys.modules:
        app = create_app(
            config_overrides={
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
            },
            seed_demo=False,
        )
    else:
        app = create_app()
