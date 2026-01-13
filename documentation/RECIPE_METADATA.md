# Recipe Model & Seeding Guide

## Overview

The Recipe model has been extended to support richer metadata including preparation times, dietary restrictions/tags, cuisine information, and image placeholders. This guide explains how to use these new features.

## Updated Recipe Model Fields

### New Fields Added to `services/models.py`:

```python
# Timing
prep_time_minutes: int (optional)
cook_time_minutes: int (optional)
total_time_minutes: int (optional)

# Metadata
cuisine: str (optional) - e.g., "Latin American", "Middle Eastern", "American"
dietary_tags: list[str] - JSON array of dietary restrictions, e.g., ["gluten-free", "halal", "vegetarian"]
image_filename: str - path to recipe image, defaults to "images/placeholder_recipe.png"
average_rating: float (optional) - average rating out of 5.0
```

### Existing Fields (Preserved):
- `id`, `title`, `slug`, `content`, `description`
- `author_id`, `created_at`, `updated_at`

---

## Seeding Example Recipes

Three example recipes have been created and can be seeded into the database:

1. **Quinoa Black Bean Stuffed Peppers** (Latin American, gluten-free, halal, vegetarian)
2. **Chicken Shawarma Pita Wraps** (Middle Eastern, halal)
3. **Classic Bacon Cheeseburger with Fries** (American)

### How to Run the Seed Script

```bash
python seed.py
```

This will:
- Create three example recipes with all metadata populated
- Auto-generate slugs using your existing slug generation logic
- Preserve any existing recipes (unless you uncomment the delete line in `seed.py`)

Output:
```
✓ Successfully seeded 3 example recipes!
  - Quinoa Black Bean Stuffed Peppers
  - Chicken Shawarma Pita Wraps
  - Classic Bacon Cheeseburger with Fries
```

---

## Using Recipe Filters

A new utility module `utilities/recipe_filters.py` provides helper functions for querying recipes by dietary restrictions and prep time. These are designed to make implementing filtering UI easy later.

### Available Filter Functions

#### 1. Filter by Dietary Tags

```python
from utilities.recipe_filters import get_recipes_by_dietary_tags

# Get recipes that are BOTH gluten-free AND vegetarian
recipes = get_recipes_by_dietary_tags(["gluten-free", "vegetarian"])

# Get recipes that DON'T have certain tags
recipes = get_recipes_by_dietary_tags(["contains-pork"], exclude_recipes=True)
```

#### 2. Filter by Maximum Prep Time

```python
from utilities.recipe_filters import get_recipes_by_max_prep_time

# Get recipes that take 30 minutes or less to prep
quick_recipes = get_recipes_by_max_prep_time(30)
```

#### 3. Filter by Prep Time Range

```python
from utilities.recipe_filters import get_recipes_by_prep_time_range

# Get recipes that take 20-40 minutes to prep
medium_recipes = get_recipes_by_prep_time_range(20, 40)
```

#### 4. Filter by Cuisine

```python
from utilities.recipe_filters import get_recipes_by_cuisine

# Get all Latin American recipes
latin_recipes = get_recipes_by_cuisine("Latin American")
```

#### 5. Combine Multiple Filters

```python
from utilities.recipe_filters import get_recipes_by_multiple_filters

# Get recipes that meet ALL criteria:
# - gluten-free AND halal (dietary tags)
# - prep time <= 30 minutes
# - Middle Eastern cuisine
recipes = get_recipes_by_multiple_filters(
    dietary_tags=["gluten-free", "halal"],
    max_prep_time=30,
    cuisine="Middle Eastern"
)
```

#### 6. Get Available Filter Options

```python
from utilities.recipe_filters import get_all_available_dietary_tags, get_all_available_cuisines

# For building dropdown menus
available_tags = get_all_available_dietary_tags()
# Result: ["gluten-free", "halal", "vegetarian", ...]

available_cuisines = get_all_available_cuisines()
# Result: ["Latin American", "Middle Eastern", "American"]
```

---

## Template Changes

### Recipe Card Partial (`templates/partials/_recipe_card.html`)

The recipe card now displays:
- Recipe image (using `image_filename` with fallback placeholder)
- Title
- Description (truncated to 120 chars)
- Cuisine (if available)
- Prep time in minutes (if available)
- Dietary tags as colored badges
- Average rating or "No ratings yet"
- "View Recipe" button

### Dietary Tag Badges

Tags are displayed as color-coded badges with the following scheme:

| Tag | Color | Hex |
|-----|-------|-----|
| gluten-free | Blue | #3b82f6 |
| halal | Green | #10b981 |
| vegetarian | Purple | #8b5cf6 |
| vegan | Pink | #ec4899 |
| nut-free | Amber | #f59e0b |
| dairy-free | Teal | #14b8a6 |
| contains-gluten, contains-pork | Red | #ef4444 |

---

## Future Enhancement: Filtering UI

When you're ready to add a filtering interface, follow this pattern:

```python
# In your Flask route
from flask import request
from utilities.recipe_filters import get_recipes_by_multiple_filters, get_all_available_dietary_tags, get_all_available_cuisines

@app.route("/recipes/filtered", methods=["GET", "POST"])
def filtered_recipes():
    dietary_tags = request.args.getlist("tags")  # e.g., ["gluten-free", "halal"]
    max_prep_time = request.args.get("max_prep", type=int)
    cuisine = request.args.get("cuisine")
    
    recipes = get_recipes_by_multiple_filters(
        dietary_tags=dietary_tags,
        max_prep_time=max_prep_time,
        cuisine=cuisine
    )
    
    available_tags = get_all_available_dietary_tags()
    available_cuisines = get_all_available_cuisines()
    
    return render_template(
        "filtered_recipes.html",
        recipes=recipes,
        available_tags=available_tags,
        available_cuisines=available_cuisines
    )
```

---

## Database Migration Note

If you're using Flask-Migrate, run:

```bash
flask db migrate -m "Add recipe metadata: timing, dietary tags, cuisine, image"
flask db upgrade
```

If you're not using migrations (i.e., relying on `db.create_all()`), the new fields will be created automatically on next app startup, as long as the existing database is cleared or the schema update is applied.

---

## Notes

- **JSON Storage**: The `dietary_tags` field stores a list/array of strings as JSON. SQLAlchemy's JSON type handles serialization/deserialization automatically.
- **Placeholder Images**: All example recipes use placeholder image filenames. Real images can be added later without changing the model.
- **Optional Timing Fields**: `cook_time_minutes` and `total_time_minutes` are optional; only `prep_time_minutes` is used for quick filtering in the current examples.
- **Slug Generation**: Slugs are auto-generated from the title using your existing `base_slug()` and `uniquify_slug()` functions.

