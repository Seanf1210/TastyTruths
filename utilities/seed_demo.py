from __future__ import annotations

import json
from typing import Iterable

from services.db import db
from services.models import BlogPost, Recipe, User
from services.nutrition import ensure_ingredient_exists_in_assets


SENTINEL_RECIPE_SLUG = "demo-spaghetti-bolognese"
SENTINEL_BLOG_SLUG = "demo-welcome"
DEMO_USERNAME = "demo_author"


def _ensure_demo_user() -> User:
    user = User.query.filter_by(username=DEMO_USERNAME).first()
    if user:
        return user
    user = User(username=DEMO_USERNAME, email="demo@example.com")
    user.set_password("demo-password")
    db.session.add(user)
    return user


def _recipe_rows() -> Iterable[dict]:
    return [
        {
            "title": "Demo Spaghetti Bolognese",
            "description": "Classic red-sauce pasta with a rich, slow-simmered meat sauce.",
            "cuisine": "Italian",
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
    sentinel_recipe = Recipe.query.filter_by(slug=SENTINEL_RECIPE_SLUG).first()
    sentinel_blog = BlogPost.query.filter_by(slug=SENTINEL_BLOG_SLUG).first()
    if sentinel_recipe or sentinel_blog:
        return False

    author = _ensure_demo_user()
    db.session.flush()
    recipe_rows = list(_recipe_rows())
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
