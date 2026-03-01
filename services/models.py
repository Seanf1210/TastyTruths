# services/models.py
from datetime import datetime
from argon2 import PasswordHasher
from sqlalchemy import event, JSON
from flask_login import UserMixin
from services.db import db
from utilities.slug import base_slug, uniquify_slug

ph = PasswordHasher()

ingredient_dietary_tags = db.Table(
    "ingredient_dietary_tags",
    db.Column(
        "ingredient_id",
        db.Integer,
        db.ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("dietary_tags.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    ),
    db.UniqueConstraint("ingredient_id", "tag_id", name="uq_ingredient_dietary_tag"),
)

class DietaryTag(db.Model):
    __tablename__ = "dietary_tags"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True, index=True)

    ingredients = db.relationship(
        "Ingredient",
        secondary=ingredient_dietary_tags,
        back_populates="dietary_tags",
    )

    @staticmethod
    def normalize_name(name: str) -> str:
        if not name:
            return ""
        return " ".join(name.strip().lower().split())

    @classmethod
    def get_or_create(cls, name: str):
        normalized = cls.normalize_name(name)
        if not normalized:
            return None
        existing = cls.query.filter_by(name=normalized).first()
        if existing:
            return existing
        tag = cls(name=normalized)
        db.session.add(tag)
        return tag

    def __repr__(self):
        return f"<DietaryTag {self.name}>"

class Ingredient(db.Model):
    __tablename__ = "ingredients"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    nutrition_per_100g = db.Column(JSON, nullable=True)

    dietary_tags = db.relationship(
        "DietaryTag",
        secondary=ingredient_dietary_tags,
        back_populates="ingredients",
        order_by="DietaryTag.name",
        lazy="selectin",
    )

    def set_dietary_tags(self, tag_names):
        normalized = []
        seen = set()
        for raw in tag_names or []:
            name = DietaryTag.normalize_name(raw)
            if name and name not in seen:
                seen.add(name)
                normalized.append(name)

        if not normalized:
            self.dietary_tags = []
            return

        existing = {
            tag.name: tag
            for tag in DietaryTag.query.filter(DietaryTag.name.in_(normalized)).all()
        }
        tags = []
        for name in normalized:
            tag = existing.get(name)
            if not tag:
                tag = DietaryTag(name=name)
                db.session.add(tag)
                existing[name] = tag
            tags.append(tag)
        self.dietary_tags = tags

    def add_dietary_tag(self, name: str):
        normalized = DietaryTag.normalize_name(name)
        if not normalized:
            return
        if any(tag.name == normalized for tag in self.dietary_tags):
            return
        tag = DietaryTag.query.filter_by(name=normalized).first()
        if not tag:
            tag = DietaryTag(name=normalized)
            db.session.add(tag)
        self.dietary_tags.append(tag)

    def remove_dietary_tag(self, name: str):
        normalized = DietaryTag.normalize_name(name)
        if not normalized:
            return
        self.dietary_tags = [tag for tag in self.dietary_tags if tag.name != normalized]

    def __repr__(self):
        return f"<Ingredient {self.name}>"

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

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(90), unique=True, index=True, nullable=False)
    summary = db.Column(db.String(280), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    author = db.relationship("User", back_populates="blog_posts")

class RecipeSlugHistory(db.Model):
    __tablename__ = "recipe_slug_history"
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    old_slug = db.Column(db.String(90), index=True, nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# --- Normalize dietary tag names ---
@event.listens_for(DietaryTag, "before_insert")
@event.listens_for(DietaryTag, "before_update")
def dietary_tag_before_save(mapper, connection, target: DietaryTag):
    target.name = DietaryTag.normalize_name(target.name)

# --- Auto-generate blog slug on insert ---
@event.listens_for(BlogPost, "before_insert")
def blog_before_insert(mapper, connection, target: BlogPost):
    session = db.session
    base = base_slug(target.title)
    target.slug = uniquify_slug(session, BlogPost, base)

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
    MAX_DIETARY_RESTRICTIONS = 20
    MAX_DIETARY_RESTRICTION_LENGTH = 32

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    bio = db.Column(db.Text, nullable=True, default="")
    profile_image = db.Column(
        db.String(255),
        nullable=False,
        default="default.png",
        server_default="default.png",
    )
    experiences = db.Column(JSON, nullable=False, default=list)
    dietary_restrictions = db.Column(JSON, nullable=False, default=list)
    role = db.Column(
        db.String(20),
        nullable=False,
        default="normal",
        server_default="normal",
        doc="User access level: normal|moderator|admin",
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    blog_posts = db.relationship("BlogPost", back_populates="author", cascade="all, delete-orphan")

    @property
    def is_admin(self) -> bool:
        return (self.role or "normal") == "admin"

    @property
    def is_staff(self) -> bool:
        return (self.role or "normal") in {"moderator", "admin"}

    def set_password(self, raw_password, hasher=ph):
        """Hash and store the password."""
        self.password_hash = hasher.hash(raw_password)

    def check_password(self, raw_password, hasher=ph):
        """Verify a password."""
        try:
            return hasher.verify(self.password_hash, raw_password)
        except Exception:
            return False

    @classmethod
    def normalize_dietary_restrictions(cls, values):
        if values is None:
            values = []
        if not isinstance(values, list):
            return None, "Dietary restrictions must be a list of strings."

        normalized = []
        seen = set()
        for value in values:
            if not isinstance(value, str):
                return None, "Each dietary restriction must be text."
            cleaned = " ".join(value.strip().lower().split())
            if not cleaned:
                return None, "Dietary restrictions cannot include empty values."
            if len(cleaned) > cls.MAX_DIETARY_RESTRICTION_LENGTH:
                return (
                    None,
                    f"Each dietary restriction must be {cls.MAX_DIETARY_RESTRICTION_LENGTH} characters or fewer.",
                )
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)

        if len(normalized) > cls.MAX_DIETARY_RESTRICTIONS:
            return (
                None,
                f"You can save up to {cls.MAX_DIETARY_RESTRICTIONS} dietary restrictions.",
            )
        return normalized, None

    def __repr__(self):
        return f"<User {self.username}>"
