"""
Flask-WTF Forms for Tasty Truths app
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SubmitField, DecimalField
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
    ValidationError,
    Regexp,
)


class RecipeForm(FlaskForm):
    """Form for creating and editing recipes."""

    title = StringField(
        "Recipe Title",
        validators=[
            DataRequired(message="Title is required."),
            Length(
                min=3,
                max=150,
                message="Title must be between 3 and 150 characters.",
            ),
        ],
        render_kw={
            "placeholder": "e.g., Classic Chocolate Chip Cookies",
            "maxlength": "150",
            "autocomplete": "off",
        },
    )

    instructions = TextAreaField(
        "Instructions",
        validators=[
            DataRequired(message="Instructions are required."),
            Length(
                min=10,
                message="Instructions must be at least 10 characters.",
            ),
        ],
        render_kw={
            "rows": 12,
            "placeholder": "Enter step-by-step cooking instructions...",
        },
    )

    ingredients = TextAreaField(
        "Ingredients",
        validators=[DataRequired(message="Please list at least one ingredient.")],
        render_kw={
            "rows": 8,
            "placeholder": "Enter one ingredient per line.\n\nExample:\n2 cups flour\n1 cup sugar\n3 eggs\n1 tsp vanilla extract",
        },
    )

    image = FileField(
        "Recipe Image (optional)",
        validators=[
            FileAllowed(
                ["jpg", "jpeg", "png", "webp", "gif"],
                message="Only image files (jpg, jpeg, png, webp, gif) are allowed.",
            ),
        ],
    )

    prep_time_minutes = IntegerField(
        "Prep Time (minutes)",
        validators=[Optional(), NumberRange(min=0, message="Prep time cannot be negative.")],
        render_kw={"min": "0", "placeholder": "e.g., 15"},
    )

    cook_time_minutes = IntegerField(
        "Cook Time (minutes)",
        validators=[Optional(), NumberRange(min=0, message="Cook time cannot be negative.")],
        render_kw={"min": "0", "placeholder": "e.g., 30"},
    )

    estimated_cost = StringField(
        "Estimated Cost",
        validators=[Optional(), Length(max=50, message="Cost must be 50 characters or less.")],
        render_kw={"placeholder": "e.g., $12 or $12.50"},
    )

    submit = SubmitField("Create Recipe")


class BlogPostForm(FlaskForm):
    """Form for creating and editing blog posts."""

    title = StringField(
        "Title",
        validators=[
            DataRequired(message="Title is required."),
            Length(max=120, message="Title must be 120 characters or fewer."),
        ],
        render_kw={"placeholder": "e.g., Our Weekend Market Finds"},
    )

    summary = TextAreaField(
        "Summary",
        validators=[
            DataRequired(message="Summary is required."),
            Length(max=280, message="Summary must be 280 characters or fewer."),
        ],
        render_kw={"rows": 4, "placeholder": "Short preview shown on the blog listing."},
    )

    content = TextAreaField(
        "Content",
        validators=[DataRequired(message="Content is required.")],
        render_kw={"rows": 12, "placeholder": "Write the full post here..."},
    )

    submit = SubmitField("Publish Post")


class SignupForm(FlaskForm):
    """Signup form fields handled via Flask-WTF/CSRF."""

    profile_picture = FileField(
        "Profile picture (optional)",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp"],
                message="Only PNG/JPG/JPEG/WEBP allowed.",
            ),
        ],
    )


class ProfileEditForm(FlaskForm):
    """Edit profile form with optional profile picture update."""

    profile_picture = FileField(
        "Update profile picture",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp"],
                message="Only PNG/JPG/JPEG/WEBP allowed.",
            ),
        ],
    )
    bio = TextAreaField(
        "Bio",
        validators=[Optional(), Length(max=500, message="Bio is too long (max 500 characters).")],
    )
    experiences_text = TextAreaField(
        "Experiences (one per line)",
        validators=[Optional(), Length(max=3000)],
    )
