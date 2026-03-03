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

// --- Bio Edit Toggle ---
(function () {
  const editBtn = document.getElementById("edit-bio-btn");
  const cancelBtn = document.getElementById("cancel-bio-btn");
  const bioForm = document.getElementById("bio-form");
  const bioDisplay = document.getElementById("bio-display");
  const bioTextarea = document.getElementById("bio-textarea");

  // If not on your own profile, elements won't exist
  if (!editBtn || !bioForm || !bioDisplay) return;

  function showEditor() {
    bioDisplay.style.display = "none";   // hide text
    editBtn.style.display = "none";      // hide edit button
    bioForm.style.display = "block";     // show textarea + save
    bioTextarea.focus();                 // auto focus textbox
  }

  function hideEditor() {
    bioForm.style.display = "none";      // hide form
    bioDisplay.style.display = "block";  // show text again
    editBtn.style.display = "inline-block"; // show edit button
  }

  // Click "Edit Bio"
  editBtn.addEventListener("click", showEditor);

  // Click "Cancel"
  if (cancelBtn) {
    cancelBtn.addEventListener("click", hideEditor);
  }
})();
// --- Updated Bio Editor ---
(function () {
  const editBtn = document.getElementById("edit-bio-btn");
  const cancelBtn = document.getElementById("cancel-bio-btn");
  const bioForm = document.getElementById("bio-form");
  const bioDisplay = document.getElementById("bio-display");
  const bioTextarea = document.getElementById("bio-textarea");
  const counter = document.getElementById("bio-char-counter");

  if (!bioForm || !bioTextarea || !counter) return;

  function updateCounter() {
    const max = 255;
    // If they somehow paste more than 255, chop it off instantly
    if (bioTextarea.value.length > max) {
      bioTextarea.value = bioTextarea.value.substring(0, max);
    }
    const current = bioTextarea.value.length;
    counter.textContent = `${current}/${max}`;
    counter.style.color = current >= max ? "red" : "inherit";
  }

  function showEditor() {
    // 1. Grab exactly what is shown on the screen right now
    let currentBio = bioDisplay.textContent.trim();
    
    // 2. If it's just the placeholder, clear the box
    if (currentBio === "No bio yet.") {
      currentBio = "";
    }

    // 3. Put that text into the box so it's there to edit
    bioTextarea.value = currentBio;
    updateCounter();

    // 4. Swap visibility
    bioDisplay.style.display = "none";
    bioForm.style.display = "block";
    if (editBtn) editBtn.style.display = "none";

    bioTextarea.focus();
    bioTextarea.setSelectionRange(bioTextarea.value.length, bioTextarea.value.length);
  }

  function hideEditor() {
    bioForm.style.display = "none";
    bioDisplay.style.display = "block";
    if (editBtn) editBtn.style.display = "inline-block";
  }

  // Bind the events
  bioTextarea.addEventListener("input", updateCounter);
  if (editBtn) editBtn.addEventListener("click", showEditor);
  if (cancelBtn) cancelBtn.addEventListener("click", hideEditor);

  // Initial call
  updateCounter();
})();

// --- Experience Edit Toggle ---
(function () {
  const editBtn = document.getElementById("edit-experience-btn");
  const cancelBtn = document.getElementById("cancel-experience-btn");
  const experienceForm = document.getElementById("experience-form");
  const experienceDisplay = document.getElementById("experience-display");

  if (!editBtn || !cancelBtn || !experienceForm || !experienceDisplay) return;

  function showEditor() {
    experienceDisplay.style.display = "none";
    editBtn.style.display = "none";
    experienceForm.style.display = "block";
  }

  function hideEditor() {
    experienceForm.style.display = "none";
    experienceDisplay.style.display = "block";
    editBtn.style.display = "inline-block";
  }

  editBtn.addEventListener("click", showEditor);
  cancelBtn.addEventListener("click", hideEditor);
})();
