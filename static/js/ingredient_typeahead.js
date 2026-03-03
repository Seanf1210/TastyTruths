(() => {
  const list = document.getElementById("ingredient-list");
  const addBtn = document.getElementById("add-ingredient-row");
  const form = document.querySelector("form");
  const hiddenTextarea = document.getElementById("ingredients");
  const ingredientClientError = document.getElementById("ingredient-client-error");

  if (!list || !addBtn || !form || !hiddenTextarea) {
    return;
  }
  hiddenTextarea.required = false;

  const showIngredientError = (message) => {
    if (!ingredientClientError) return;
    ingredientClientError.textContent = message || "";
    ingredientClientError.style.display = message ? "block" : "none";
  };

  const debounce = (fn, wait = 200) => {
    let timer = null;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), wait);
    };
  };

  const fetchSuggestions = async (query) => {
    const url = `/api/ingredients/suggest?q=${encodeURIComponent(query)}&limit=8`;
    const res = await fetch(url);
    if (!res.ok) return [];
    return await res.json();
  };

  const closeSuggestions = (container) => {
    container.innerHTML = "";
    container.setAttribute("aria-hidden", "true");
  };

  const renderSuggestions = (container, items, input, idInput) => {
    container.innerHTML = "";
    if (!items.length) {
      closeSuggestions(container);
      return;
    }
    container.setAttribute("aria-hidden", "false");
    items.forEach((item, idx) => {
      const option = document.createElement("div");
      option.className = "ingredient-suggestion";
      option.textContent = item.name;
      option.dataset.value = item.name;
      option.dataset.id = item.id;
      option.dataset.index = String(idx);
      option.addEventListener("mousedown", (event) => {
        event.preventDefault();
        input.value = item.name;
        idInput.value = item.id || "";
        closeSuggestions(container);
      });
      container.appendChild(option);
    });
  };

  const attachTypeahead = (row) => {
    const input = row.querySelector(".ingredient-name");
    const idInput = row.querySelector(".ingredient-id");
    const container = row.querySelector(".ingredient-suggestions");
    if (!input || !idInput || !container) return;

    let highlighted = -1;

    const updateSuggestions = debounce(async () => {
      const query = input.value.trim();
      if (query.length < 2) {
        closeSuggestions(container);
        return;
      }
      try {
        const items = await fetchSuggestions(query);
        highlighted = -1;
        renderSuggestions(container, items, input, idInput);
      } catch (err) {
        closeSuggestions(container);
      }
    }, 200);

    input.addEventListener("input", () => {
      idInput.value = "";
      updateSuggestions();
    });

    input.addEventListener("keydown", (event) => {
      const options = Array.from(container.querySelectorAll(".ingredient-suggestion"));
      if (!options.length) return;

      if (event.key === "ArrowDown") {
        event.preventDefault();
        highlighted = (highlighted + 1) % options.length;
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        highlighted = (highlighted - 1 + options.length) % options.length;
      } else if (event.key === "Enter") {
        if (highlighted >= 0) {
          event.preventDefault();
          options[highlighted].dispatchEvent(new MouseEvent("mousedown"));
        }
        return;
      } else if (event.key === "Escape") {
        closeSuggestions(container);
        return;
      } else {
        return;
      }

      options.forEach((opt, idx) => {
        opt.classList.toggle("is-active", idx === highlighted);
      });
    });

    document.addEventListener("click", (event) => {
      if (!row.contains(event.target)) {
        closeSuggestions(container);
      }
    });
  };

  const addRow = () => {
    const row = document.createElement("div");
    row.className = "ingredient-row";
    row.innerHTML = `
      <input
        type="text"
        name="ingredient_name[]"
        class="form-control ingredient-name"
        placeholder="e.g., Greek yogurt"
        autocomplete="off"
      />
      <input type="hidden" name="ingredient_id[]" class="ingredient-id" />
      <input type="text" name="ingredient_quantity[]" class="form-control ingredient-qty" placeholder="Qty" />
      <input type="text" name="ingredient_unit[]" class="form-control ingredient-unit" placeholder="Unit" />
      <div class="ingredient-suggestions" aria-hidden="true"></div>
    `;
    list.appendChild(row);
    attachTypeahead(row);
  };

  addBtn.addEventListener("click", addRow);
  list.querySelectorAll(".ingredient-row").forEach(attachTypeahead);

  form.addEventListener("submit", (event) => {
    const names = Array.from(list.querySelectorAll(".ingredient-name"))
      .map((input) => input.value.trim())
      .filter(Boolean);
    if (!names.length) {
      event.preventDefault();
      showIngredientError("Please add at least one ingredient before creating your recipe.");
      const firstNameInput = list.querySelector(".ingredient-name");
      if (firstNameInput) firstNameInput.focus();
      return;
    }
    showIngredientError("");
    hiddenTextarea.value = names.join("\n");
  });

  list.addEventListener("input", (event) => {
    if (event.target && event.target.classList.contains("ingredient-name")) {
      if (event.target.value.trim()) {
        showIngredientError("");
      }
    }
  });
})();
