"""
Recipe filtering and query utilities.

This module provides helper functions for querying recipes by dietary restrictions
and prep time, making it easy to implement filtering UI later.
"""

from services.db import db
from services.models import Recipe
from sqlalchemy import and_


def get_recipes_by_dietary_tags(dietary_tags: list, exclude_recipes=False) -> list:
    """
    Query recipes that match ALL specified dietary tags.
    
    Args:
        dietary_tags: List of dietary tag strings (e.g., ["gluten-free", "vegetarian"])
        exclude_recipes: If True, return recipes that DON'T have any of these tags
    
    Returns:
        List of Recipe objects matching the criteria
    
    Example:
        # Get recipes that are both gluten-free AND vegetarian
        recipes = get_recipes_by_dietary_tags(["gluten-free", "vegetarian"])
    """
    if not dietary_tags:
        return Recipe.query.all()
    
    query = Recipe.query
    
    if exclude_recipes:
        # Exclude recipes with ANY of the tags
        for tag in dietary_tags:
            query = query.filter(~Recipe.dietary_tags.contains(tag))
    else:
        # Include only recipes with ALL tags
        for tag in dietary_tags:
            query = query.filter(Recipe.dietary_tags.contains(tag))
    
    return query.order_by(Recipe.created_at.desc()).all()


def get_recipes_by_max_prep_time(max_minutes: int) -> list:
    """
    Query recipes with prep time <= max_minutes.
    
    Args:
        max_minutes: Maximum prep time in minutes
    
    Returns:
        List of Recipe objects with prep_time_minutes <= max_minutes
    
    Example:
        # Get recipes that take 30 minutes or less to prep
        quick_recipes = get_recipes_by_max_prep_time(30)
    """
    if not max_minutes or max_minutes < 0:
        return Recipe.query.all()
    
    return (
        Recipe.query
        .filter(Recipe.prep_time_minutes <= max_minutes)
        .order_by(Recipe.prep_time_minutes.asc())
        .all()
    )


def get_recipes_by_prep_time_range(min_minutes: int = 0, max_minutes: int = 999) -> list:
    """
    Query recipes with prep time within a range.
    
    Args:
        min_minutes: Minimum prep time in minutes (default 0)
        max_minutes: Maximum prep time in minutes (default 999)
    
    Returns:
        List of Recipe objects with prep_time_minutes in the specified range
    
    Example:
        # Get recipes that take 20-40 minutes to prep
        medium_recipes = get_recipes_by_prep_time_range(20, 40)
    """
    return (
        Recipe.query
        .filter(
            and_(
                Recipe.prep_time_minutes >= min_minutes,
                Recipe.prep_time_minutes <= max_minutes
            )
        )
        .order_by(Recipe.prep_time_minutes.asc())
        .all()
    )


def get_recipes_by_cuisine(cuisine: str) -> list:
    """
    Query recipes by cuisine type.
    
    Args:
        cuisine: Cuisine name (e.g., "Latin American", "Middle Eastern")
    
    Returns:
        List of Recipe objects matching the cuisine
    
    Example:
        # Get all Latin American recipes
        latin_recipes = get_recipes_by_cuisine("Latin American")
    """
    if not cuisine:
        return Recipe.query.all()
    
    return (
        Recipe.query
        .filter(Recipe.cuisine.ilike(f"%{cuisine}%"))
        .order_by(Recipe.created_at.desc())
        .all()
    )


def get_recipes_by_multiple_filters(
    dietary_tags: list = None,
    max_prep_time: int = None,
    cuisine: str = None
) -> list:
    """
    Query recipes using multiple filters combined.
    
    All filters are AND-ed together (recipe must match ALL criteria to be included).
    
    Args:
        dietary_tags: List of dietary restrictions (e.g., ["gluten-free", "halal"])
        max_prep_time: Maximum prep time in minutes
        cuisine: Cuisine type
    
    Returns:
        List of Recipe objects matching all specified criteria
    
    Example:
        # Get gluten-free AND halal recipes that take 30 minutes or less
        recipes = get_recipes_by_multiple_filters(
            dietary_tags=["gluten-free", "halal"],
            max_prep_time=30
        )
    """
    query = Recipe.query
    
    # Apply dietary tag filter
    if dietary_tags:
        for tag in dietary_tags:
            query = query.filter(Recipe.dietary_tags.contains(tag))
    
    # Apply prep time filter
    if max_prep_time is not None and max_prep_time > 0:
        query = query.filter(Recipe.prep_time_minutes <= max_prep_time)
    
    # Apply cuisine filter
    if cuisine:
        query = query.filter(Recipe.cuisine.ilike(f"%{cuisine}%"))
    
    return query.order_by(Recipe.created_at.desc()).all()


def get_all_available_dietary_tags() -> list:
    """
    Get a list of all unique dietary tags used across recipes.
    
    Useful for populating dropdown menus or filter UI.
    
    Returns:
        List of unique dietary tag strings
    
    Example:
        # Build a dropdown of available dietary options
        tags = get_all_available_dietary_tags()
        # Result: ["gluten-free", "halal", "vegetarian", ...]
    """
    all_recipes = Recipe.query.all()
    unique_tags = set()
    
    for recipe in all_recipes:
        if recipe.dietary_tags:
            unique_tags.update(recipe.dietary_tags)
    
    return sorted(list(unique_tags))


def get_all_available_cuisines() -> list:
    """
    Get a list of all unique cuisines used across recipes.
    
    Useful for populating dropdown menus or filter UI.
    
    Returns:
        List of unique cuisine strings
    
    Example:
        # Build a dropdown of available cuisines
        cuisines = get_all_available_cuisines()
        # Result: ["Latin American", "Middle Eastern", "American", ...]
    """
    cuisines = db.session.query(Recipe.cuisine).filter(
        Recipe.cuisine != ""
    ).distinct().all()
    
    return sorted([c[0] for c in cuisines if c[0]])
