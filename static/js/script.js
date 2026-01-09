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