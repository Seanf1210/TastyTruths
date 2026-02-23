(function () {
  const form = document.getElementById("dietary-restrictions-form");
  if (!form) return;

  const checkboxEls = Array.from(
    form.querySelectorAll(".dietary-checkboxes input[type='checkbox']")
  );
  const customInput = document.getElementById("dietary-custom-tag");
  const addButton = document.getElementById("dietary-add-btn");
  const hiddenJson = document.getElementById("dietary-restrictions-json");
  const chipList = document.getElementById("dietary-chip-list");
  const errorEl = document.getElementById("dietary-form-error");

  const config = window.profileDietaryRestrictionsConfig || {};
  const maxItems = Number(config.maxItems || 20);
  const maxLength = Number(config.maxLength || 32);
  const known = new Set(checkboxEls.map((el) => normalizeTag(el.value)));
  const state = new Set();

  function normalizeTag(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  function showError(message) {
    if (!message) {
      errorEl.hidden = true;
      errorEl.textContent = "";
      return;
    }
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  function syncCheckboxes() {
    checkboxEls.forEach((box) => {
      box.checked = state.has(normalizeTag(box.value));
    });
  }

  function renderChips() {
    chipList.innerHTML = "";
    const tags = Array.from(state.values()).sort();
    if (!tags.length) {
      const empty = document.createElement("p");
      empty.className = "no-data";
      empty.textContent = "No restrictions selected.";
      chipList.appendChild(empty);
      return;
    }

    tags.forEach((tag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "dietary-chip";
      chip.setAttribute("aria-label", `Remove ${tag}`);
      chip.dataset.value = tag;
      chip.textContent = tag;
      chipList.appendChild(chip);
    });
  }

  function addTag(rawValue) {
    const tag = normalizeTag(rawValue);
    if (!tag) {
      showError("Dietary restrictions cannot be empty.");
      return false;
    }
    if (tag.length > maxLength) {
      showError(`Each dietary restriction must be ${maxLength} characters or fewer.`);
      return false;
    }
    if (state.has(tag)) {
      showError("");
      return true;
    }
    if (state.size >= maxItems) {
      showError(`You can save up to ${maxItems} dietary restrictions.`);
      return false;
    }
    state.add(tag);
    showError("");
    syncCheckboxes();
    renderChips();
    return true;
  }

  function removeTag(rawValue) {
    const tag = normalizeTag(rawValue);
    if (!tag) return;
    state.delete(tag);
    showError("");
    syncCheckboxes();
    renderChips();
  }

  const initial = Array.isArray(window.profileDietaryRestrictions)
    ? window.profileDietaryRestrictions
    : [];
  initial.forEach((item) => addTag(item));
  checkboxEls.forEach((box) => {
    if (box.checked) addTag(box.value);
    box.addEventListener("change", () => {
      if (box.checked) addTag(box.value);
      else removeTag(box.value);
    });
  });

  addButton.addEventListener("click", () => {
    if (addTag(customInput.value)) {
      customInput.value = "";
      customInput.focus();
    }
  });

  customInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    addButton.click();
  });

  chipList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.classList.contains("dietary-chip")) return;
    removeTag(target.dataset.value || "");
  });

  form.addEventListener("submit", (event) => {
    const allTags = Array.from(state.values());
    const hasEmpty = allTags.some((tag) => !normalizeTag(tag));
    if (hasEmpty) {
      event.preventDefault();
      showError("Dietary restrictions cannot be empty.");
      return;
    }
    hiddenJson.value = JSON.stringify(allTags);
  });

  renderChips();
})();
