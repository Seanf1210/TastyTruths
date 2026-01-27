// script.js — general utilities (safe to keep)

export async function getJSON(url) {
  const res = await fetch(url, { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

export function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

export async function postWithCsrf(csrfUrl, url, body = null) {
  const { csrfToken } = await getJSON(csrfUrl);
  return fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRFToken": csrfToken,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : null,
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const themeToggle = document.querySelector('.theme-toggle');
  
  // Only run if the button exists on the current page
  if (themeToggle) {
    const themeIcon = themeToggle.querySelector('ion-icon');

    themeToggle.addEventListener('click', () => {
      // Get the current icon name
      const currentIcon = themeIcon.getAttribute('name');

      if (currentIcon === 'moon-outline') {
        // Switch to Sun
        themeIcon.setAttribute('name', 'sunny-outline');
        // Change color to an orange/yellow sun color if desired
        themeIcon.style.color = '#ffce00'; 
        
        // Optional: Add a class to the body to actually trigger dark mode colors
        document.body.classList.add('dark-mode');
      } else {
        // Switch back to Moon
        themeIcon.setAttribute('name', 'moon-outline');
        themeIcon.style.color = '#f9f871'; 
        
        // Optional: Remove dark mode class
        document.body.classList.remove('dark-mode');
      }
    });
  }
});