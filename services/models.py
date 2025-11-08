# services/models.py
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import func
from services.db import db

# --- existing Recipe/RecipeSlugHistory remain as-is ---

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_verified = db.Column(db.Boolean, default=True)  # set up email verify later if needed
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now(), default=func.now())

    def set_password(self, password, ph):
        self.password_hash = ph.hash(password)

    def check_password(self, password, ph) -> bool:
        try:
            return ph.verify(self.password_hash, password)
        except Exception:
            return False
