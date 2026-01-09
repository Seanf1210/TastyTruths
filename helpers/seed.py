#!/usr/bin/env python
"""
Seed script to populate the database with example recipes.
Run with: python seed.py
"""

from app import create_app
from services.db import db
from services.models import Recipe

def seed_recipes():
    """Create and insert three example recipes."""
    app = create_app()
    
    with app.app_context():
        # Clear existing recipes (optional - comment out to keep existing data)
        # Recipe.query.delete()
        
        # Recipe 1: Quinoa Black Bean Stuffed Peppers
        recipe1 = Recipe(
            title="Quinoa Black Bean Stuffed Peppers",
            description="Colorful bell peppers stuffed with quinoa, black beans, and veggies for a hearty, gluten-free and halal-friendly dinner.",
            cuisine="Latin American",
            prep_time_minutes=20,
            cook_time_minutes=35,
            total_time_minutes=55,
            dietary_tags=["gluten-free", "halal", "vegetarian"],
            image_filename="images/placeholder_quinoa_peppers.jpg",
            content="""
## Ingredients
- 4 bell peppers, tops removed and seeds discarded
- 1 cup uncooked quinoa, rinsed
- 2 cups vegetable broth
- 1 can (15 oz) black beans, drained and rinsed
- 1 cup corn kernels (fresh or frozen)
- 1 small red onion, diced
- 2 cloves garlic, minced
- 1 tsp ground cumin
- 1 tsp smoked paprika
- 1/2 tsp chili powder
- 1/2 tsp salt (or to taste)
- 1/4 tsp black pepper
- 1/4 cup chopped fresh cilantro
- 1–2 tbsp olive oil

## Instructions
1. Preheat oven to 375°F (190°C). Lightly oil a baking dish and arrange the hollowed bell peppers upright.
2. Cook quinoa in vegetable broth according to package directions; fluff with a fork.
3. In a skillet, heat olive oil over medium heat. Sauté onion and garlic until softened.
4. Stir in black beans, corn, cooked quinoa, cumin, smoked paprika, chili powder, salt, and pepper. Cook 2–3 minutes, then remove from heat and stir in cilantro.
5. Spoon the filling into each bell pepper, packing it down gently.
6. Cover the dish with foil and bake for 25–30 minutes, until peppers are tender.
7. Serve warm, garnished with extra cilantro if desired.
            """,
            author_id=None,
        )
        
        # Recipe 2: Chicken Shawarma Pita Wraps
        recipe2 = Recipe(
            title="Chicken Shawarma Pita Wraps",
            description="Marinated chicken cooked with warm spices, tucked into fluffy pitas with crisp veggies and tangy yogurt sauce.",
            cuisine="Middle Eastern",
            prep_time_minutes=25,
            cook_time_minutes=20,
            total_time_minutes=45,
            dietary_tags=["halal"],
            image_filename="images/placeholder_chicken_shawarma.jpg",
            content="""
## Ingredients
- 1.5 lb boneless, skinless chicken thighs, cut into strips
- 3 tbsp olive oil
- 3 cloves garlic, minced
- 2 tsp ground cumin
- 2 tsp ground coriander
- 1.5 tsp ground paprika
- 1 tsp ground turmeric
- 1/2 tsp ground cinnamon
- 1/2 tsp ground black pepper
- 1 tsp salt (or to taste)
- Juice of 1 lemon
- 4–6 pita breads
- 1 cup shredded lettuce
- 1 cup sliced cucumber
- 1 cup chopped tomato
- 1/2 small red onion, thinly sliced
- For yogurt sauce:
  - 1 cup plain yogurt
  - 1 tbsp lemon juice
  - 1 tbsp olive oil
  - 1 small clove garlic, minced
  - Salt and pepper to taste

## Instructions
1. In a bowl, combine olive oil, garlic, cumin, coriander, paprika, turmeric, cinnamon, pepper, salt, and lemon juice. Add chicken and toss to coat. Marinate at least 20 minutes (or up to overnight in the fridge).
2. Mix yogurt sauce ingredients in a separate bowl and refrigerate until serving.
3. Heat a large skillet over medium-high heat. Cook the marinated chicken in batches for 6–8 minutes, until cooked through and nicely browned.
4. Warm pita breads in a dry skillet or oven.
5. To assemble, spread some yogurt sauce on each pita, then add chicken, lettuce, cucumber, tomato, and red onion.
6. Fold or roll the pita into a wrap and serve immediately.
            """,
            author_id=None,
        )
        
        # Recipe 3: Classic Bacon Cheeseburger with Fries
        recipe3 = Recipe(
            title="Classic Bacon Cheeseburger with Fries",
            description="Juicy beef burgers topped with melty cheese and crispy bacon, served with oven-baked fries.",
            cuisine="American",
            prep_time_minutes=20,
            cook_time_minutes=20,
            total_time_minutes=40,
            dietary_tags=[],
            image_filename="images/placeholder_bacon_cheeseburger.jpg",
            content="""
## Ingredients
- For burgers:
  - 1.5 lb ground beef (80/20)
  - 1 tsp salt
  - 1/2 tsp black pepper
  - 1 tsp garlic powder
  - 4 slices cheddar cheese
  - 4 burger buns
  - 8 slices bacon, cooked until crispy
  - Lettuce leaves
  - Sliced tomato
  - Sliced pickles
  - Ketchup, mustard, and/or mayonnaise
- For fries:
  - 3–4 russet potatoes, cut into fries
  - 2–3 tbsp vegetable oil
  - 1 tsp salt
  - 1/2 tsp paprika (optional)

## Instructions
1. Preheat oven to 425°F (220°C). Toss potato fries with oil, salt, and paprika. Spread on a baking sheet and bake 25–30 minutes, flipping halfway, until golden and crisp.
2. In a bowl, gently mix ground beef with salt, pepper, and garlic powder. Form into 4 equal patties.
3. Cook bacon in a skillet until crispy, then drain on paper towels.
4. In the same or a clean skillet or grill pan, cook burger patties over medium-high heat 3–4 minutes per side, or until desired doneness.
5. Place a slice of cheese on each patty during the last minute of cooking to melt.
6. Lightly toast burger buns if desired.
7. Assemble burgers with lettuce, tomato, burger patty with cheese, bacon, pickles, and condiments of choice. Serve with fries on the side.
            """,
            author_id=None,
        )
        
        # Add all recipes to session
        db.session.add(recipe1)
        db.session.add(recipe2)
        db.session.add(recipe3)
        
        # Commit to database
        try:
            db.session.commit()
            print("✓ Successfully seeded 3 example recipes!")
            print(f"  - {recipe1.title}")
            print(f"  - {recipe2.title}")
            print(f"  - {recipe3.title}")
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error seeding recipes: {e}")
            raise

if __name__ == "__main__":
    seed_recipes()
