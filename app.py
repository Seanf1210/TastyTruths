# app.py
from datetime import timedelta
from flask import Flask, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf
from argon2 import PasswordHasher

from services.db import db
from services.models import Recipe, RecipeSlugHistory, User  # <-- add User
# If your User class isn't UserMixin, we wrap it below

ph = PasswordHasher()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
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
    )

    # --- init extensions in the right order ---
    db.init_app(app)
    Migrate(app, db)
    CSRFProtect(app)
    login_manager.init_app(app)

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
    @app.post("/api/auth/register")
    def register():
        data = _json()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not email or not password:
            return jsonify({"error": "email and password required"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "email already registered"}), 409

        u = User(email=email)
        u.set_password(password, ph)  # argon2
        db.session.add(u)
        db.session.commit()
        return jsonify({"ok": True})

    @app.post("/api/auth/login")
    def login():
        data = _json()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({"error": "invalid credentials"}), 401

        if not user.check_password(password, ph):
            return jsonify({"error": "invalid credentials"}), 401

        # Rotates session; use remember=False for pure server session
        login_user(user, remember=False, duration=timedelta(hours=8))
        return jsonify({"ok": True})

    @app.post("/api/auth/logout")
    @login_required
    def logout():
        logout_user()
        return jsonify({"ok": True})

    @app.get("/api/auth/me")
    def me():
        if current_user.is_authenticated:
            return jsonify({"id": current_user.id, "email": current_user.email})
        return jsonify({"id": None, "email": None})

    # ---- RECIPES (unchanged behavior, plus auth on create) ----

    # Create a recipe (JSON: {title, content})
    @app.post("/api/recipes")
    @login_required
    def create_recipe():
        data = _json()
        r = Recipe(title=(data.get("title") or "").strip(),
                   content=data.get("content") or "")
        db.session.add(r)
        db.session.commit()
        return jsonify({"id": r.id, "slug": r.slug, "title": r.title}), 201

    # Canonical detail URL: /recipes/<id>-<slug>
    @app.get("/recipes/<id_slug>")
    def recipe_detail(id_slug: str):
        try:
            rid_str, _, tail = id_slug.partition("-")
            rid = int(rid_str)
        except Exception:
            return jsonify({"error": "Bad id"}), 400

        r = db.session.get(Recipe, rid)
        if not r:
            # check old slugs -> redirect
            old = RecipeSlugHistory.query.filter_by(old_slug=tail or id_slug).first()
            if old:
                canonical = f"{old.recipe_id}-{db.session.get(Recipe, old.recipe_id).slug}"
                return redirect(url_for("recipe_detail", id_slug=canonical), code=301)
            return jsonify({"error": "Not found"}), 404

        canonical = f"{r.id}-{r.slug}"
        if id_slug != canonical:
            return redirect(url_for("recipe_detail", id_slug=canonical), code=301)

        return jsonify({"id": r.id, "title": r.title, "slug": r.slug, "content": r.content})

    # Simple list
    @app.get("/api/recipes")
    def list_recipes():
        rows = Recipe.query.order_by(Recipe.created_at.desc()).all()
        return jsonify([{"id": r.id, "title": r.title, "slug": r.slug} for r in rows])

    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
