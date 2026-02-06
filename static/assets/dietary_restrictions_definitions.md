# Dietary Restrictions Logic & Ingredient Mapping
<!--  Created by Joaquin on 02-01-2026
# Last edited by Joaquin on 02-01-2026
# Gemini AI was used to assist in the creation of the file
-->

## 1. Supported Restrictions
The following dietary restrictions are supported by the platform. Users can filter recipes based on these tags:

* **Vegan:** Excludes all animal-derived products (meat, poultry, fish, dairy, eggs, honey).
* **Vegetarian:** Excludes meat, poultry, and fish.
* **Gluten-Free:** Excludes wheat, barley, rye, and cross-contaminated oats.
* **Dairy-Free:** Excludes all milk-based products (butter, cheese, cream, lactose).
* **Nut-Free:** Excludes peanuts and all tree nuts (almonds, walnuts, cashews, etc.).

---

## 2. Core Classification Rule
To ensure user safety and data consistency, the following rule is applied:

**"A Recipe is classified as [Restriction X] if and only if every individual ingredient within that recipe is tagged as meeting [Restriction X]."**

**If a single ingredient fails the check, the entire recipe is excluded from that dietary category.** 

---

## 3. Ingredient Mapping Example
This table defines how common ingredients map to the supported restrictions.

| Ingredient | Vegetarian | Vegan | Gluten-Free | Dairy-Free | Nut-Free |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Honey | Yes | **No** | Yes | Yes | Yes |
| Eggs | Yes | **No** | Yes | Yes | Yes |
| Tofu | Yes | Yes | Yes | Yes | Yes |
| Soy Sauce | Yes | Yes | **No** | Yes | Yes |
| Butter | Yes | **No** | Yes | **No** | Yes |
| Almond Milk | Yes | Yes | Yes | Yes | **No** |

---

## 4. Edge Cases & Constraints
The following limitations apply to our current data model:

* **"May Contain" Traces:** We do **not** support "may contain" data. An ingredient is considered that it is compliant based on its primary composition. Meaning, if it says may contain peanuts, (unless there is another nut present in the ingredient list) the product will be considered Nut-Free
* **Shared Equipment:** The logic does not account for restaurant-style "shared fryers" or kitchen surfaces.
* **Ambiguous Ingredients:** * Ingredients labeled "Natural Flavors" or "Spices" are assumed to be in compliance unless a known allergen is flagged.
    * "Stock" or "Broth" must be specifically labeled (e.g., "Vegetable Stock") to be categorized; otherwise, they default to non-compliant for Vegetarian/Vegan filters.