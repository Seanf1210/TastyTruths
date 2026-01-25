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

/* --- Dark Mode Logic --- */
document.addEventListener('DOMContentLoaded', () => {
  const themeToggle = document.querySelector('.theme-toggle');
  
  if (themeToggle) {
    const themeIcon = themeToggle.querySelector('ion-icon');
    
    // 1. Check Local Storage on Load
    const currentTheme = localStorage.getItem('theme');
    
    // If user previously chose dark, apply it immediately
    if (currentTheme === 'dark') {
      document.body.classList.add('dark-mode');
      themeIcon.setAttribute('name', 'sunny-outline');
      // Note: Color is now handled by CSS variables
    }

    // 2. Handle Click Event
    themeToggle.addEventListener('click', () => {
      // Toggle the class
      document.body.classList.toggle('dark-mode');
      
      // Check if dark mode is now active
      const isDark = document.body.classList.contains('dark-mode');

      if (isDark) {
        // Switch to Sun icon
        themeIcon.setAttribute('name', 'sunny-outline');
        localStorage.setItem('theme', 'dark');
      } else {
        // Switch to Moon icon
        themeIcon.setAttribute('name', 'moon-outline');
        localStorage.setItem('theme', 'light');
      }
    });
  }
});