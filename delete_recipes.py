from app import app
from services.models import Recipe
from services.db import db

with app.app_context():
    # Get count before deletion
    count = Recipe.query.count()
    print(f"Found {count} recipes in the database")
    
    if count > 0:
        # Delete all recipes
        Recipe.query.delete()
        db.session.commit()
        print(f"✓ Successfully deleted all {count} recipes")
    else:
        print("No recipes to delete")
    
    # Verify deletion
    remaining = Recipe.query.count()
    print(f"Recipes remaining: {remaining}")
