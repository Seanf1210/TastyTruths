from __future__ import annotations

import json
import os
import re
import shutil
from typing import Iterable

from services.db import db
from services.friendships import (
    FRIEND_REQUEST_ACCEPTED,
    FRIEND_REQUEST_DECLINED,
    FRIEND_REQUEST_PENDING,
    ensure_bidirectional_friendship,
)
from services.models import BlogPost, FriendRequest, Recipe, User
from services.nutrition import ensure_ingredient_exists_in_assets


SENTINEL_RECIPE_SLUG = "demo-spaghetti-bolognese"
SENTINEL_BLOG_SLUG = "demo-welcome"
DEMO_USERNAME = "demo_user"
DEFAULT_PROFILE_IMAGE = "default.png"
SEED_PROFILE_IMAGE_FILENAME = "stock_alpaca.jpg"

ADDITIONAL_USERS = [
    {
        "username": "demo_social",
        "email": "social@example.com",
        "password": "demo-social",
        "bio": "I love meeting new cooks and trying every recipe here.",
        "experience": "Community builder and recipe tester.",
        "experiences": ["Hosting potlucks", "Recipe feedback", "Sharing tips"],
    },
    {
        "username": "demo_one_friend",
        "email": "onefriend@example.com",
        "password": "demo-one",
        "bio": "Keeping my circle small while I learn the basics.",
        "experience": "Practicing simple dishes.",
        "experiences": ["Beginner cooking"],
    },
    {
        "username": "demo_three_friends",
        "email": "threefriends@example.com",
        "password": "demo-three",
        "bio": "Building a close crew of kitchen buddies.",
        "experience": "Swapping family recipes.",
        "experiences": ["Family recipes", "Weeknight meals"],
    },
]


def _ensure_seed_profile_image() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    source = os.path.join(project_root, "assets", "images", SEED_PROFILE_IMAGE_FILENAME)
    destination_dir = os.path.join(project_root, "static", "uploads", "profile_pics")
    destination = os.path.join(destination_dir, SEED_PROFILE_IMAGE_FILENAME)
    if not os.path.exists(source):
        return
    os.makedirs(destination_dir, exist_ok=True)
    if not os.path.exists(destination):
        shutil.copy2(source, destination)


def _default_bio_for_role(role: str) -> str:
    return f"I am a {role}"


def _default_experience_for_role(role: str) -> str:
    if role == "admin":
        return "I help manage community content and keep the platform running smoothly."
    if role == "moderator":
        return "I review community submissions and support recipe quality."
    return "I enjoy home cooking and sharing practical recipes for busy schedules."


def _default_experiences_for_role(role: str) -> list[str]:
    if role == "admin":
        return ["Site moderation", "Community management"]
    if role == "moderator":
        return ["Recipe review", "Content moderation"]
    return ["Home cooking", "Trying new recipes weekly"]


def _ensure_demo_user() -> User:
    user = User.query.filter_by(username=DEMO_USERNAME).first()
    if user:
        if not (user.bio or "").strip():
            user.bio = _default_bio_for_role("user")
        if not (user.experience or "").strip():
            user.experience = _default_experience_for_role("user")
        if not isinstance(user.experiences, list) or not user.experiences:
            user.experiences = _default_experiences_for_role("user")
        user.profile_image = SEED_PROFILE_IMAGE_FILENAME
        return user
    user = User(
        username=DEMO_USERNAME,
        email="demo@example.com",
        role="normal",
        bio=_default_bio_for_role("user"),
        experience=_default_experience_for_role("user"),
        experiences=_default_experiences_for_role("user"),
        profile_image=SEED_PROFILE_IMAGE_FILENAME,
    )
    user.set_password("demo-user")
    db.session.add(user)
    return user


def _ensure_staff_users() -> tuple[User, User]:
    admin = User.query.filter_by(username="demo_admin").first()
    if admin:
        if not (admin.bio or "").strip():
            admin.bio = _default_bio_for_role("admin")
        if not (admin.experience or "").strip():
            admin.experience = _default_experience_for_role("admin")
        if not isinstance(admin.experiences, list) or not admin.experiences:
            admin.experiences = _default_experiences_for_role("admin")
        admin.profile_image = SEED_PROFILE_IMAGE_FILENAME
    else:
        admin = User(
            username="demo_admin",
            email="admin@example.com",
            role="admin",
            bio=_default_bio_for_role("admin"),
            experience=_default_experience_for_role("admin"),
            experiences=_default_experiences_for_role("admin"),
            profile_image=SEED_PROFILE_IMAGE_FILENAME,
        )
        admin.set_password("demo-admin")
        db.session.add(admin)

    moderator = User.query.filter_by(username="demo_moderator").first()
    if moderator:
        if not (moderator.bio or "").strip():
            moderator.bio = _default_bio_for_role("moderator")
        if not (moderator.experience or "").strip():
            moderator.experience = _default_experience_for_role("moderator")
        if not isinstance(moderator.experiences, list) or not moderator.experiences:
            moderator.experiences = _default_experiences_for_role("moderator")
        moderator.profile_image = SEED_PROFILE_IMAGE_FILENAME
    else:
        moderator = User(
            username="demo_moderator",
            email="moderator@example.com",
            role="moderator",
            bio=_default_bio_for_role("moderator"),
            experience=_default_experience_for_role("moderator"),
            experiences=_default_experiences_for_role("moderator"),
            profile_image=SEED_PROFILE_IMAGE_FILENAME,
        )
        moderator.set_password("demo-moderator")
        db.session.add(moderator)

    return admin, moderator


def _ensure_additional_seed_users() -> list[User]:
    users: list[User] = []
    for row in ADDITIONAL_USERS:
        username = row["username"]
        user = User.query.filter_by(username=username).first()
        if user:
            if not (user.email or "").strip():
                user.email = row["email"]
            if not (user.bio or "").strip():
                user.bio = row["bio"]
            if not (user.experience or "").strip():
                user.experience = row["experience"]
            if not isinstance(user.experiences, list) or not user.experiences:
                user.experiences = list(row["experiences"])
            if not (user.role or "").strip():
                user.role = "normal"
            user.profile_image = SEED_PROFILE_IMAGE_FILENAME
        else:
            user = User(
                username=username,
                email=row["email"],
                role="normal",
                bio=row["bio"],
                experience=row["experience"],
                experiences=list(row["experiences"]),
                profile_image=SEED_PROFILE_IMAGE_FILENAME,
            )
            user.set_password(row["password"])
            db.session.add(user)
        users.append(user)
    return users


def _ensure_friend_request(
    requester: User,
    recipient: User,
    status: str,
) -> FriendRequest:
    friend_request = FriendRequest.query.filter_by(
        requester_id=requester.id,
        recipient_id=recipient.id,
        status=status,
    ).first()
    if friend_request:
        return friend_request

    friend_request = FriendRequest(
        requester_id=requester.id,
        recipient_id=recipient.id,
        status=status,
    )
    db.session.add(friend_request)
    db.session.flush()
    return friend_request


def _ensure_friendship_seed_data(author: User, admin: User, moderator: User) -> None:
    ensure_bidirectional_friendship(author.id, admin.id)
    _ensure_friend_request(moderator, author, FRIEND_REQUEST_PENDING)
    _ensure_friend_request(admin, moderator, FRIEND_REQUEST_DECLINED)
    _ensure_friend_request(author, admin, FRIEND_REQUEST_ACCEPTED)


def _ensure_additional_social_graph(
    author: User,
    admin: User,
    moderator: User,
    extra_users: list[User],
) -> None:
    if len(extra_users) < 3:
        return

    social_user, one_friend_user, three_friends_user = extra_users[:3]
    ensure_bidirectional_friendship(author.id, social_user.id)
    ensure_bidirectional_friendship(author.id, one_friend_user.id)
    ensure_bidirectional_friendship(author.id, three_friends_user.id)
    ensure_bidirectional_friendship(admin.id, three_friends_user.id)
    ensure_bidirectional_friendship(moderator.id, three_friends_user.id)

    _ensure_friend_request(social_user, moderator, FRIEND_REQUEST_PENDING)
    _ensure_friend_request(one_friend_user, admin, FRIEND_REQUEST_DECLINED)
    _ensure_friend_request(three_friends_user, social_user, FRIEND_REQUEST_ACCEPTED)


def _recipe_rows() -> Iterable[dict]:
    def _seed_image(title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", title.strip().lower()).strip("_")
        return f"assets/images/seed/{slug}.jpg"

    return [
        {
            "title": "Demo Spaghetti Bolognese",
            "description": "Classic red-sauce pasta with a rich, slow-simmered meat sauce.",
            "cuisine": "Italian",
            "image_filename": _seed_image("Demo Spaghetti Bolognese"),
            "prep_time_minutes": 20,
            "cook_time_minutes": 60,
            "ingredients": json.dumps(
                [
                    {"name": "Spaghetti", "quantity": 12, "unit": "oz"},
                    {"name": "Ground beef", "quantity": 1, "unit": "lb"},
                    {"name": "Onion", "quantity": 1, "unit": "small"},
                    {"name": "Garlic", "quantity": 3, "unit": "cloves"},
                    {"name": "Crushed tomatoes", "quantity": 28, "unit": "oz"},
                    {"name": "Olive oil", "quantity": 2, "unit": "tbsp"},
                    {"name": "Salt", "unit": "to taste"},
                ]
            ),
            "instructions": "Brown the beef. Saute onion and garlic. Simmer with tomatoes. Cook pasta and combine.",
        },
        {
            "title": "Demo Veggie Stir Fry",
            "description": "Fast weeknight stir fry with crisp veggies and a light soy-ginger sauce.",
            "cuisine": "Asian",
            "image_filename": _seed_image("Demo Veggie Stir Fry"),
            "prep_time_minutes": 15,
            "cook_time_minutes": 10,
            "ingredients": json.dumps(
                [
                    {"name": "Broccoli", "quantity": 2, "unit": "cups"},
                    {"name": "Carrots", "quantity": 2, "unit": "medium"},
                    {"name": "Bell pepper", "quantity": 1},
                    {"name": "Soy sauce", "quantity": 2, "unit": "tbsp"},
                    {"name": "Ginger", "quantity": 1, "unit": "tsp"},
                ]
            ),
            "instructions": "Stir-fry vegetables. Add sauce and cook until glossy.",
        },
        {
            "title": "Demo Pancakes",
            "description": "Fluffy breakfast pancakes with maple syrup.",
            "cuisine": "American",
            "image_filename": _seed_image("Demo Pancakes"),
            "prep_time_minutes": 10,
            "cook_time_minutes": 15,
            "ingredients": json.dumps(
                [
                    {"name": "Flour", "quantity": 1.5, "unit": "cups"},
                    {"name": "Baking powder", "quantity": 2, "unit": "tsp"},
                    {"name": "Milk", "quantity": 1.25, "unit": "cups"},
                    {"name": "Egg", "quantity": 1},
                    {"name": "Butter", "quantity": 2, "unit": "tbsp"},
                ]
            ),
            "instructions": "Whisk batter and cook on a griddle until golden.",
        },
        {
            "title": "Demo Lemon Herb Chicken",
            "description": "Juicy chicken thighs with lemon, garlic, and herbs.",
            "cuisine": "Mediterranean",
            "image_filename": _seed_image("Demo Lemon Herb Chicken"),
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "ingredients": json.dumps(
                [
                    {"name": "Chicken thighs", "quantity": 6},
                    {"name": "Lemon", "quantity": 1},
                    {"name": "Garlic", "quantity": 4, "unit": "cloves"},
                    {"name": "Olive oil", "quantity": 2, "unit": "tbsp"},
                    {"name": "Oregano", "quantity": 1, "unit": "tsp"},
                ]
            ),
            "instructions": "Marinate, then roast until cooked through.",
        },
        {
            "title": "Demo Tomato Soup",
            "description": "Creamy tomato soup served with toasted bread.",
            "cuisine": "American",
            "image_filename": _seed_image("Demo Tomato Soup"),
            "prep_time_minutes": 10,
            "cook_time_minutes": 25,
            "ingredients": json.dumps(
                [
                    {"name": "Tomatoes", "quantity": 28, "unit": "oz"},
                    {"name": "Onion", "quantity": 1, "unit": "small"},
                    {"name": "Cream", "quantity": 0.5, "unit": "cup"},
                    {"name": "Salt", "unit": "to taste"},
                ]
            ),
            "instructions": "Simmer tomatoes and onion. Blend and finish with cream.",
        },
        {
            "title": "Demo Garden Salad",
            "description": "Fresh greens with a simple vinaigrette.",
            "cuisine": "American",
            "image_filename": _seed_image("Demo Garden Salad"),
            "prep_time_minutes": 10,
            "cook_time_minutes": 0,
            "ingredients": json.dumps(
                [
                    {"name": "Mixed greens", "quantity": 6, "unit": "cups"},
                    {"name": "Cucumber", "quantity": 0.5, "unit": "cup"},
                    {"name": "Tomatoes", "quantity": 1, "unit": "cup"},
                    {"name": "Olive oil", "quantity": 2, "unit": "tbsp"},
                    {"name": "Vinegar", "quantity": 1, "unit": "tbsp"},
                ]
            ),
            "instructions": "Toss vegetables with vinaigrette.",
        },
        {
            "title": "Demo Baked Salmon",
            "description": "Simple oven-baked salmon with lemon pepper.",
            "cuisine": "Seafood",
            "image_filename": _seed_image("Demo Baked Salmon"),
            "prep_time_minutes": 10,
            "cook_time_minutes": 15,
            "ingredients": json.dumps(
                [
                    {"name": "Salmon fillets", "quantity": 2},
                    {"name": "Lemon", "quantity": 0.5},
                    {"name": "Black pepper", "unit": "to taste"},
                    {"name": "Salt", "unit": "to taste"},
                ]
            ),
            "instructions": "Season and bake until flaky.",
        },
        {
            "title": "Demo Veggie Wraps",
            "description": "Crunchy veggie wraps with hummus.",
            "cuisine": "Vegetarian",
            "image_filename": _seed_image("Demo Veggie Wraps"),
            "prep_time_minutes": 15,
            "cook_time_minutes": 0,
            "ingredients": json.dumps(
                [
                    {"name": "Tortillas", "quantity": 4},
                    {"name": "Hummus", "quantity": 0.5, "unit": "cup"},
                    {"name": "Spinach", "quantity": 2, "unit": "cups"},
                    {"name": "Carrots", "quantity": 1, "unit": "cup"},
                ]
            ),
            "instructions": "Spread hummus, add veggies, roll and slice.",
        },
        {
            "title": "Demo Berry Parfait",
            "description": "Layered yogurt parfait with berries and granola.",
            "cuisine": "Breakfast",
            "image_filename": _seed_image("Demo Berry Parfait"),
            "prep_time_minutes": 10,
            "cook_time_minutes": 0,
            "ingredients": json.dumps(
                [
                    {"name": "Greek yogurt", "quantity": 2, "unit": "cups"},
                    {"name": "Mixed berries", "quantity": 1, "unit": "cup"},
                    {"name": "Granola", "quantity": 0.5, "unit": "cup"},
                ]
            ),
            "instructions": "Layer yogurt, berries, and granola in glasses.",
        },
        {
            "title": "Demo Mystery Stew",
            "description": "A placeholder recipe to demonstrate empty ingredients.",
            "cuisine": "Demo",
            "image_filename": _seed_image("Demo Mystery Stew"),
            "prep_time_minutes": 5,
            "cook_time_minutes": 5,
            "ingredients": "",
            "instructions": "No ingredients provided for this demo recipe.",
        },
    ]


def _blog_rows(author_id: int) -> Iterable[dict]:
    return [
        {
            "title": "Demo Welcome",
            "summary": "Welcome to the demo blog for Tasty Truths.",
            "content": "This is a demo post to show how blog content appears.",
            "user_id": author_id,
        },
        {
            "title": "Demo Kitchen Tips",
            "summary": "Quick tips to speed up your prep time.",
            "content": "Sharpen your knife, prep in batches, and keep a clean station.",
            "user_id": author_id,
        },
        {
            "title": "Demo Pantry Staples",
            "summary": "The pantry basics that make weeknight dinners easier.",
            "content": "Stock beans, pasta, canned tomatoes, and spices.",
            "user_id": author_id,
        },
        {
            "title": "Demo Meal Planning",
            "summary": "A simple method for planning meals for the week.",
            "content": "Pick a theme, plan leftovers, and shop once.",
            "user_id": author_id,
        },
        {
            "title": "Demo Budget Cooking",
            "summary": "Stretch your grocery budget without sacrificing flavor.",
            "content": "Use beans, grains, and frozen vegetables.",
            "user_id": author_id,
        },
        {
            "title": "Demo Quick Breakfasts",
            "summary": "Five-minute breakfasts for busy mornings.",
            "content": "Overnight oats, yogurt parfaits, and smoothies.",
            "user_id": author_id,
        },
        {
            "title": "Demo Campus Cooking",
            "summary": "Dorm-friendly ideas with minimal equipment.",
            "content": "Use a microwave, kettle, and a good meal plan.",
            "user_id": author_id,
        },
        {
            "title": "Demo Flavor Boosters",
            "summary": "Small additions that make meals pop.",
            "content": "Finish with citrus, herbs, and a dash of acid.",
            "user_id": author_id,
        },
        {
            "title": "Demo Leftover Remix",
            "summary": "Turn last night's dinner into a new meal.",
            "content": "Use roasted vegetables in wraps or bowls.",
            "user_id": author_id,
        },
        {
            "title": "Demo Kitchen Safety",
            "summary": "Stay safe while cooking.",
            "content": "Keep handles turned in and use dry towels for hot pans.",
            "user_id": author_id,
        },
    ]


def seed_demo_data() -> bool:
    _ensure_seed_profile_image()
    author = _ensure_demo_user()
    admin, moderator = _ensure_staff_users()
    extra_users = _ensure_additional_seed_users()
    db.session.flush()

    _ensure_friendship_seed_data(author, admin, moderator)
    _ensure_additional_social_graph(author, admin, moderator, extra_users)

    sentinel_recipe = Recipe.query.filter_by(slug=SENTINEL_RECIPE_SLUG).first()
    sentinel_blog = BlogPost.query.filter_by(slug=SENTINEL_BLOG_SLUG).first()
    if sentinel_recipe or sentinel_blog:
        db.session.commit()
        return False

    recipe_seed_users = [author, admin, moderator, *extra_users]
    base_recipe_templates = list(_recipe_rows())[:5]
    recipe_rows = []
    for user_index, seed_user in enumerate(recipe_seed_users):
        for template in base_recipe_templates:
            row = dict(template)
            if user_index > 0:
                row["title"] = f"{template['title']} ({seed_user.username})"
            row["author_id"] = seed_user.id
            recipe_rows.append(row)

    for row in recipe_rows:
        raw = row.get("ingredients") or ""
        try:
            data = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            data = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("ingredient")
                else:
                    name = item
                if name:
                    ensure_ingredient_exists_in_assets(str(name))
    recipes = [Recipe(**row) for row in recipe_rows]
    blogs = [BlogPost(**row) for row in _blog_rows(author.id)]

    db.session.add_all(recipes)
    db.session.add_all(blogs)
    db.session.commit()
    return True
