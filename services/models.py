# services/models.py
from datetime import datetime
from argon2 import PasswordHasher
from sqlalchemy import event, JSON
from flask_login import UserMixin
from services.db import db
from utilities.slug import base_slug, uniquify_slug

ph = PasswordHasher()

class Recipe(db.Model):
    __tablename__ = "recipes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(90), unique=True, index=True, nullable=False)
    content = db.Column(db.Text, default="")
    description = db.Column(db.String(500), default="")
    
    # New recipe fields
    instructions = db.Column(db.Text, nullable=True)
    ingredients = db.Column(db.Text, nullable=True)  # newline-separated or JSON list
    image_filename = db.Column(db.String(255), nullable=True)
    
    # Timing (in minutes)
    prep_time_minutes = db.Column(db.Integer, nullable=True)
    cook_time_minutes = db.Column(db.Integer, nullable=True)
    total_time_minutes = db.Column(db.Integer, nullable=True)
    
    # Metadata
    estimated_cost = db.Column(db.String(50), nullable=True)
    cuisine = db.Column(db.String(100), default="")
    dietary_tags = db.Column(JSON, default=list)
    average_rating = db.Column(db.Float, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

class RecipeSlugHistory(db.Model):
    __tablename__ = "recipe_slug_history"
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    old_slug = db.Column(db.String(90), index=True, nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# --- Auto-generate slug on insert ---
@event.listens_for(Recipe, "before_insert")
def recipe_before_insert(mapper, connection, target: Recipe):
    session = db.session
    base = base_slug(target.title)
    target.slug = uniquify_slug(session, Recipe, base)

# --- If title changes, rotate slug + save redirect history ---
@event.listens_for(Recipe, "before_update")
def recipe_before_update(mapper, connection, target: Recipe):
    session = db.session
    # Load current DB state to compare
    db_obj = session.get(Recipe, target.id)
    if not db_obj:
        return
    if db_obj.title != target.title:
        old_slug = db_obj.slug
        new_base = base_slug(target.title)
        target.slug = uniquify_slug(session, Recipe, new_base, exclude_id=target.id)
        if old_slug != target.slug:
            session.add(RecipeSlugHistory(recipe_id=target.id, old_slug=old_slug))

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password, hasher=ph):
        """Hash and store the password."""
        self.password_hash = hasher.hash(raw_password)

    def check_password(self, raw_password, hasher=ph):
        """Verify a password."""
        try:
            return hasher.verify(self.password_hash, raw_password)
        except Exception:
            return False

    def __repr__(self):
        return f"<User {self.username}>"