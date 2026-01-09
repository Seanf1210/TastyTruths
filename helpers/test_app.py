from app import app

# Try to import and see if it works without errors
try:
    with app.app_context():
        from services.models import Recipe
        print("✓ App context created successfully")
        print("✓ Recipe model imported successfully")
        recipes = Recipe.query.all()
        print(f"✓ Database query successful - found {len(recipes)} recipes")
        print("\n✅ All checks passed! The app is ready to run.")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
