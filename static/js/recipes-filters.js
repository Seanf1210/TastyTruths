// recipes-filters.js
// Hook recipe filter UI to ingredient filtering logic (vanilla JS, no deps)
// Single source of truth for filter state lives in getFilterState().

const INGREDIENTS_URL = "/static/assets/ingredients.json";
const RECIPES_URL = "/api/recipes";
let ingredientCache = [];
let recipeCache = [];

// --- Filtering helpers (JS port of services/filtering.py) ---
function normalizeTags(values) {
  const normalized = [];
  const seen = new Set();
  (values || []).forEach((raw) => {
    if (raw == null) return;
    let text;
    if (typeof raw === "object" && "name" in raw) {
      text = String(raw.name);
    } else {
      text = String(raw);
    }
    const clean = text.trim().toLowerCase();
    if (!clean || seen.has(clean)) return;
    seen.add(clean);
    normalized.push(clean);
  });
  return normalized;
}

function extractIngredientTags(ingredient) {
  if (!ingredient) return [];
  if (Array.isArray(ingredient.dietary_tags)) {
    return normalizeTags(ingredient.dietary_tags);
  }
  if (Array.isArray(ingredient.dietary_restrictions)) {
    return normalizeTags(ingredient.dietary_restrictions);
  }
  return [];
}

function filterIngredientsByDietaryTags(ingredients, selectedTags, mode) {
  const normalizedSelected = normalizeTags(selectedTags);
  if (!normalizedSelected.length) return [...(ingredients || [])];

  let modeValue = (mode || "or").trim().toLowerCase();
  if (modeValue !== "and" && modeValue !== "or") {
    modeValue = "or"; // match backend default
  }

  return (ingredients || []).filter((ingredient) => {
    const tags = extractIngredientTags(ingredient);
    if (!tags.length) return false;
    return modeValue === "and"
      ? normalizedSelected.every((tag) => tags.includes(tag))
      : normalizedSelected.some((tag) => tags.includes(tag));
  });
}

// --- Filter state ---
// If match mode control is absent, we default to AND (documented below).
function getFilterState() {
  const queryInput = document.getElementById("filter-query");
  const macroSelect = document.getElementById("filter-macro-sort");
  const hideMissingBox = document.getElementById("filter-hide-missing");
  const matchModeChoice = document.querySelector(
    'input[name="filter-match-mode"]:checked'
  );
  const dietaryChecks = document.querySelectorAll('[data-filter="dietary"]');

  const query = (queryInput?.value || "").trim();
  const dietaryTags = Array.from(dietaryChecks)
    .filter((el) => el.checked)
    .map((el) => el.value);

  const matchModeRaw = matchModeChoice?.value || "AND"; // Default to AND if UI is hidden.

  return {
    query,
    dietaryTags,
    allergens: [],
    macroSort: macroSelect?.value || null,
    hideMissingNutrition: !!hideMissingBox?.checked,
    matchMode: matchModeRaw.toUpperCase() === "OR" ? "OR" : "AND",
  };
}

// --- Rendering helpers ---
function renderRecipeEmpty(show, message) {
  let emptyEl = document.getElementById("recipe-empty-state");
  if (!emptyEl) {
    emptyEl = document.createElement("p");
    emptyEl.id = "recipe-empty-state";
    emptyEl.className = "no-data";
    const container = document.getElementById("recipe-list");
    (container || document.body).appendChild(emptyEl);
  }
  emptyEl.textContent = message || "No recipes match your selected filters.";
  emptyEl.hidden = !show;
}

function renderRecipes(recipes) {
  const listEl = document.getElementById("recipe-list");
  if (!listEl) return;

  // Remove any existing children so we can rewrite
  listEl.textContent = "";
  renderRecipeEmpty(false);

  if (!recipes.length) {
    renderRecipeEmpty(true);
    return;
  }

  const ul = document.createElement("ul");
  recipes.forEach((r) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `/recipes/${r.id}-${r.slug}`;
    a.textContent = r.title;
    li.appendChild(a);
    ul.appendChild(li);
  });
  listEl.appendChild(ul);
}

// --- Application ---
function applyFiltersAndRender() {
  const state = getFilterState();
  let filteredIngredients = [...ingredientCache];

  if (state.query) {
    const q = state.query.toLowerCase();
    filteredIngredients = filteredIngredients.filter((ing) =>
      (ing.name || "").toLowerCase().includes(q) || (ing.category || "").toLowerCase().includes(q)
    );
  }

  filteredIngredients = filterIngredientsByDietaryTags(
    filteredIngredients,
    state.dietaryTags,
    state.matchMode
  );

  if (state.hideMissingNutrition) {
    filteredIngredients = filteredIngredients.filter(
      (ing) => ing && ing.nutrition_per_gram && Object.keys(ing.nutrition_per_gram).length > 0
    );
  }

  // Build a quick lookup of ingredient names that passed the filters
  const ingredientNameSet = new Set(
    filteredIngredients.map((ing) => (ing.name || "").trim().toLowerCase()).filter(Boolean)
  );

  // Filter recipes: keep those that contain at least one matching ingredient name.
  let filteredRecipes = [...recipeCache];
  if (ingredientNameSet.size) {
    filteredRecipes = filteredRecipes.filter((recipe) => {
      const names = recipe.ingredients_lower || [];
      return names.some((n) => ingredientNameSet.has(n));
    });
  }

  // If user typed a query but no ingredient matches, allow matching by recipe title too.
  if (state.query) {
    const q = state.query.toLowerCase();
    filteredRecipes = filteredRecipes.filter(
      (r) =>
        (r.ingredients_lower || []).some((n) => n.includes(q)) ||
        (r.title || "").toLowerCase().includes(q)
    );
  }

  renderRecipes(filteredRecipes);
}

function enableControls() {
  document.querySelectorAll("[data-filter-enable]").forEach((el) => {
    el.removeAttribute("disabled");
  });
}

function bindFilterListeners() {
  const handlers = ["input", "change"];
  const controls = document.querySelectorAll(
    "#filter-query, #filter-macro-sort, #filter-hide-missing, input[name='filter-match-mode'], [data-filter='dietary']"
  );
  controls.forEach((el) => {
    handlers.forEach((eventName) => {
      el.addEventListener(eventName, applyFiltersAndRender);
    });
  });
}

function clearFilters() {
  const queryInput = document.getElementById("filter-query");
  const macroSelect = document.getElementById("filter-macro-sort");
  const hideMissing = document.getElementById("filter-hide-missing");
  document
    .querySelectorAll("[data-filter='dietary']")
    .forEach((el) => (el.checked = false));
  if (queryInput) queryInput.value = "";
  if (macroSelect) macroSelect.value = "";
  if (hideMissing) hideMissing.checked = false;
  applyFiltersAndRender();
}

async function loadIngredients() {
  try {
    const res = await fetch(INGREDIENTS_URL);
    if (!res.ok) throw new Error(`Failed to fetch ${INGREDIENTS_URL} (${res.status})`);
    ingredientCache = (await res.json()) || [];
  } catch (err) {
    console.error(err);
  }
}

async function loadRecipes() {
  const listEl = document.getElementById("recipe-list");
  if (listEl) listEl.textContent = "Loading recipes...";
  try {
    const res = await fetch(RECIPES_URL);
    if (!res.ok) throw new Error(`Failed to fetch ${RECIPES_URL} (${res.status})`);
    const data = await res.json();
    recipeCache = (data || []).map((r) => {
      const lowerNames = (r.ingredients || []).map((name) => (name || "").trim().toLowerCase()).filter(Boolean);
      return { ...r, ingredients_lower: lowerNames };
    });
  } catch (err) {
    console.error(err);
    renderRecipeEmpty(true, "Unable to load recipes right now.");
    recipeCache = [];
  }
}

document.addEventListener("DOMContentLoaded", () => {
  enableControls();
  bindFilterListeners();
  const clearBtn = document.getElementById("clear-filters");
  if (clearBtn) clearBtn.addEventListener("click", clearFilters);
  const applyBtn = document.getElementById("apply-filters");
  if (applyBtn) applyBtn.addEventListener("click", applyFiltersAndRender);
  Promise.all([loadIngredients(), loadRecipes()]).then(applyFiltersAndRender);
});
