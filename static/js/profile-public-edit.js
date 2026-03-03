document.addEventListener("DOMContentLoaded", () => {
  const bioDisplay = document.getElementById("bio-display");
  const bioForm = document.getElementById("bio-form");
  const editBioBtn = document.getElementById("edit-bio-btn");
  const cancelBioBtn = document.getElementById("cancel-bio-btn");

  if (bioDisplay && bioForm && editBioBtn && cancelBioBtn) {
    editBioBtn.addEventListener("click", () => {
      bioDisplay.style.display = "none";
      editBioBtn.style.display = "none";
      bioForm.style.display = "block";
    });

    cancelBioBtn.addEventListener("click", () => {
      bioForm.style.display = "none";
      bioDisplay.style.display = "block";
      editBioBtn.style.display = "inline-block";
    });
  }

  const experienceDisplay = document.getElementById("experience-display");
  const experienceForm = document.getElementById("experience-form");
  const editExperienceBtn = document.getElementById("edit-experience-btn");
  const cancelExperienceBtn = document.getElementById("cancel-experience-btn");

  if (experienceDisplay && experienceForm && editExperienceBtn && cancelExperienceBtn) {
    editExperienceBtn.addEventListener("click", () => {
      experienceDisplay.style.display = "none";
      editExperienceBtn.style.display = "none";
      experienceForm.style.display = "block";
    });

    cancelExperienceBtn.addEventListener("click", () => {
      experienceForm.style.display = "none";
      experienceDisplay.style.display = "block";
      editExperienceBtn.style.display = "inline-block";
    });
  }
});
