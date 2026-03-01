document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".avatar-upload-form");
  const button = document.querySelector(".avatar-button");
  const input = document.getElementById("profile_picture_input");

  if (!form || !button || !input) {
    return;
  }

  button.addEventListener("click", () => {
    input.click();
  });

  input.addEventListener("change", () => {
    if (input.files && input.files.length > 0) {
      form.submit();
    }
  });
});
