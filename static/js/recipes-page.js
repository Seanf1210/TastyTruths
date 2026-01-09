// /static/js/recipes-page.js
// Page controller for recipe_template.html

import { store } from "/static/js/store.js";

// --- initial seed data (only used if store is empty) ---
const SEED_RECIPES = [
  {
    title: "Creamy Pesto Pasta",
    slug: "creamy-pesto-pasta",
    excerpt: "Weeknight comfort with basil, garlic, and a silky finish.",
    imageSrc: "/assets/images/recipes/pesto-pasta.jpg",
    imageAlt: "Creamy pesto pasta in a bowl topped with parmesan",
    timeISO: "PT25M",
    timeLabel: "25 min",
    serves: 4,
    level: "Easy",
    cuisine: "Italian",
    diet: "Vegetarian",
    tags: ["Vegetarian", "Pasta", "Quick"],
    ratingValue: 4.6,
    ratingStars: "★★★★☆",
    ratingCount: 128,
  },
  {
    title: "Kimchi Fried Rice",
    slug: "kimchi-fried-rice",
    excerpt: "Tangy, spicy, and ready in under 15 minutes.",
    imageSrc: "/assets/images/recipes/kimchi-fried-rice.jpg",
    imageAlt: "Kimchi fried rice topped with a sunny-side egg",
    timeISO: "PT15M",
    timeLabel: "15 min",
    serves: 2,
    level: "Easy",
    cuisine: "Korean",
    diet: "None", // or "Carnivore", "Omnivore", etc.
    tags: ["Korean", "Rice", "Spicy"],
    ratingValue: 4.8,
    ratingStars: "★★★★★",
    ratingCount: 342,
  },
];

// --- utilities ---
function minutesFromISO(duration) {
  // Very small helper for PTxxM style strings
  // e.g. "PT25M" -> 25
  const match = /^PT(\d+)M$/.exec(duration);
  return match ? parseInt(match[1], 10) : null;
}

function filterRecipes(all, filters) {
  return all.filter((r) => {
    // Cuisine (string)
    if (filters.cuisine && r.cuisine !== filters.cuisine) return false;

    // Diet (string; could be "Vegetarian", "Vegan", etc.)
    if (filters.diet && r.diet !== filters.diet) return false;

    // Time buckets
    if (filters.time) {
      const mins = minutesFromISO(r.timeISO || "");
      if (mins == null) return false;

      if (filters.time === "under-20" && !(mins < 20)) return false;
      if (filters.time === "20-45" && !(mins >= 20 && mins <= 45)) return false;
      if (filters.time === "over-45" && !(mins > 45)) return false;
    }

    return true;
  });
}

// --- rendering ---
function renderRecipes(recipes) {
  const grid = document.querySelector(".recipe-grid");
  const emptyState = grid.querySelector(".empty-state");
  const template = document.getElementById("recipe-card-template");

  if (!grid || !template) return;

  // Clear previous cards (leave empty-state paragraph)
  [...grid.querySelectorAll(".recipe-card")].forEach((el) => el.remove());

  if (!recipes.length) {
    if (emptyState) emptyState.hidden = false;
    return;
  } else if (emptyState) {
    emptyState.hidden = true;
  }

  recipes.forEach((recipe) => {
    const node = template.content.cloneNode(true);
    const card = node.querySelector(".recipe-card");

    // Link
    const link = node.querySelector(".card-link");
    if (link) {
      link.href = `/recipes/${recipe.slug}.html`;
      link.setAttribute("aria-label", `View recipe: ${recipe.title}`);
    }

    // Image
    const img = node.querySelector("img");
    if (img) {
      img.src = recipe.imageSrc || "";
      img.alt = recipe.imageAlt || recipe.title || "";
    }

    // Title & excerpt
    const titleEl = node.querySelector(".card-title");
    const excerptEl = node.querySelector(".card-excerpt");
    if (titleEl) titleEl.textContent = recipe.title || "";
    if (excerptEl) excerptEl.textContent = recipe.excerpt || "";

    // Meta (time, serves, level)
    const timeEl = node.querySelector(".meta time");
    if (timeEl) {
      timeEl.dateTime = recipe.timeISO || "";
      timeEl.textContent = recipe.timeLabel || "";
    }

    const ddEls = node.querySelectorAll(".meta dd");
    if (ddEls[1]) ddEls[1].textContent = recipe.serves ?? "";
    if (ddEls[2]) ddEls[2].textContent = recipe.level ?? "";

    // Tags
    const tagsList = node.querySelector(".tags");
    if (tagsList) {
      tagsList.innerHTML = "";
      (recipe.tags || []).forEach((tag) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        const slug = tag.toLowerCase().replace(/\s+/g, "-");
        a.href = `/tags/${slug}.html`;
        a.textContent = tag;
        li.appendChild(a);
        tagsList.appendChild(li);
      });
    }

    // Rating
    const ratingDiv = node.querySelector(".rating");
    const starsSpan = node.querySelector(".rating-stars");
    const countSpan = node.querySelector(".rating-count");
    if (ratingDiv) {
      const value = recipe.ratingValue ?? 0;
      ratingDiv.setAttribute(
        "aria-label",
        `Rated ${value.toFixed(1)} out of 5`
      );
    }
    if (starsSpan) {
      starsSpan.textContent = recipe.ratingStars || "★★★★☆";
    }
    if (countSpan) {
      const count = recipe.ratingCount ?? 0;
      countSpan.textContent = count ? `(${count})` : "";
    }

    // Save button (stub for now)
    const saveBtn = node.querySelector(".save-button");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => {
        const pressed = saveBtn.getAttribute("aria-pressed") === "true";
        saveBtn.setAttribute("aria-pressed", String(!pressed));
        // TODO: integrate with favorites in localStorage or backend
      });
    }

    grid.appendChild(node);
  });
}

// --- set up filters & initial data ---
document.addEventListener("DOMContentLoaded", () => {
  // Load or seed recipes
  let recipes = store.getAll("recipes");
  if (!recipes.length) {
    SEED_RECIPES.forEach((r) => store.create("recipes", r));
    recipes = store.getAll("recipes");
  }

  const cuisineSelect = document.getElementById("filter-cuisine");
  const dietSelect = document.getElementById("filter-diet");
  const timeSelect = document.getElementById("filter-time");
  const applyBtn = document.getElementById("apply-filters");
  const clearBtn = document.getElementById("clear-filters");

  function applyFilters() {
    const filters = {
      cuisine: cuisineSelect?.value || "",
      diet: dietSelect?.value || "",
      time: timeSelect?.value || "",
    };
    const filtered = filterRecipes(recipes, filters);
    renderRecipes(filtered);
  }

  function clearFilters() {
    if (cuisineSelect) cuisineSelect.value = "";
    if (dietSelect) dietSelect.value = "";
    if (timeSelect) timeSelect.value = "";
    renderRecipes(recipes);
  }

  if (applyBtn) applyBtn.addEventListener("click", applyFilters);
  if (clearBtn) clearBtn.addEventListener("click", clearFilters);

  // Initial render
  renderRecipes(recipes);
});
