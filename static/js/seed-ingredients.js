//Created by Joaquin on 01-30-2026
//Last modified by Joaquin on 01-30-2026
//Gemini AI assisted in the creation of this file.

import { store } from "/static/js/store.js";


export async function seedIngredients() {
    console.log("🌱 Initializing Ingredient Seed from assets...");

    try {
        // Corrected path to match your storage
        const response = await fetch('/static/assets/ingredients.json');
        if (!response.ok) throw new Error(`Could not find ingredients.json at ${response.url}`);
        
        const ingredientsData = await response.json();
        const existingIngredients = store.getAll("ingredients") || [];
        
        let newItemsCount = 0;

        ingredientsData.forEach(ingredient => {
        // Check if ID already exists to maintain idempotency
        const alreadyExists = existingIngredients.some(item => item.id === ingredient.id);
        
        if (!alreadyExists) {
            store.create("ingredients", ingredient);
            newItemsCount++;
        }
    });

    if (newItemsCount > 0) {
        console.log(`✅ Seeded ${newItemsCount} new ingredients into the store.`);
    } else {
        console.log("✨ Ingredient database already up to date.");
    }

    } catch (err) {
        console.error("❌ Seeding failed:", err);
    }
}