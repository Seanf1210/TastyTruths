/* script.js - auth header controller (framework-agnostic) */
(function () {
  function $(sel, root = document) {
    return root.querySelector(sel);
  }

  // Minimal HTML escaping for safe label rendering
  function escapeHtml(s) {
    return String(s).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        }[c])
    );
  }

  async function getJSON(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.json();
  }

  async function postWithCsrf(url, body = null) {
    const headerEl = $("#site-header");
    const csrfUrl = headerEl?.dataset.csrf || "/api/auth/csrf-token";
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



  async function initAuthBar() {
    const headerEl = $("#site-header");
    const bar = $("#auth-bar");
    if (!headerEl || !bar) return;

    const meUrl = headerEl.dataset.authMe || "/api/auth/me";
    const logoutUrl = headerEl.dataset.logout || "/api/auth/logout";
    const loginUrl = headerEl.dataset.loginUrl || "/login.html";
    const signupUrl = headerEl.dataset.signupUrl || "/signup.html";
    const profileUrl = headerEl.dataset.profileUrl || "/account.html";

    // Initial state while we check
    bar.innerHTML = `<span class="auth-status" data-status="loading">Checking login…</span>`;

    // Helper for logout
    const handleLogout = async () => {
      const btn = $(".auth-logout", bar);
      if (btn) btn.disabled = true;
      try {
        const res = await postWithCsrf(logoutUrl);
        if (res.ok) location.reload();
        else renderLoggedOut(bar, loginUrl, signupUrl);
      } catch {
        renderLoggedOut(bar, loginUrl, signupUrl);
      }
    };

    try {
      const me = await getJSON(meUrl);
      // Consider logged-in if any recognizable user identifier is present
      if (me && (me.email || me.username || me.name || me.id)) {
        renderLoggedIn(bar, profileUrl, me, handleLogout);
      } else {
        renderLoggedOut(bar, loginUrl, signupUrl);
      }
    } catch {
      // On error (e.g., network), default to safe "logged out"
      renderLoggedOut(bar, loginUrl, signupUrl);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAuthBar);
  } else {
    initAuthBar();
  }
})();
