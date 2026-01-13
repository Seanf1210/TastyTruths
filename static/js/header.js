// header.js
// Renders the Tasty Truths header and manages the auth bar.

(function () {
  "use strict";

  // --- helpers (scoped to this file) ---
  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      }[c])
    );
  }

  async function getJSON(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return res.json();
  }

  async function postWithCsrf(headerEl, url, body = null) {
    const csrfUrl = headerEl.dataset.csrf || "/api/auth/csrf-token";
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

  // --- render static header shell ---
  function renderHeader() {
    const root = document.getElementById("header-root");
    if (!root) return;

    const headerHTML = `
      <header
        class="site-header"
        data-auth-me="/api/auth/me"
        data-csrf="/api/auth/csrf-token"
        data-logout="/api/auth/logout"
        data-login-url="/pages/login.html"
        data-signup-url="/pages/signup.html"
        data-profile-url="/pages/account.html"
      >
        <div class="header-container container">
          <div class="logo">
            <a href="/static/index.html">
              <img src="{{ url_for('static', filename='assets/images/logo_main.png') }}" alt="Tasty Truths logo">
            </a>
          </div>

          <nav class="main-nav" aria-label="Primary">
            <a href="/static/pages/about_us.html">About</a>
            <a href="/static/pages/recipes.html">Recipes</a>
            <a href="/static/pages/blog.html">Blog</a>
          </nav>

          <div
            id="auth-bar"
            class="auth-links"
            aria-live="polite"
            aria-atomic="true"
          ></div>
        </div>
      </header>
    `;

    root.innerHTML = headerHTML;
  }

  // --- auth bar renderers ---
  function renderLoggedOut(bar, loginUrl, signupUrl) {
    bar.innerHTML = `
      <div class="logged-out-container">
        <span class="auth-status" data-status="logged-out">Not logged in</span>
        <div class="auth-buttons-container">
          <a href="${loginUrl}" class="button">Login</a>
          <a href="${signupUrl}" class="button signup">Sign Up</a>
        </div>
      </div>
    `;
  }

  function renderLoggedIn(bar, profileUrl, user, onLogout) {
    const label = user.username || user.name || user.email || "your account";
    bar.innerHTML = `
      <span class="auth-status" data-status="logged-in">
        Logged in as
        <a class="auth-user" href="${profileUrl}">${escapeHtml(label)}</a>
      </span>
      <button type="button" class="auth-logout">Log out</button>
    `;
    const btn = bar.querySelector(".auth-logout");
    if (btn) {
      btn.addEventListener("click", onLogout);
    }
  }

  // --- main auth logic ---
  async function initAuthBar() {
    const headerEl = document.querySelector(".site-header");
    const bar = document.getElementById("auth-bar");
    if (!headerEl || !bar) return;

    const meUrl = headerEl.dataset.authMe || "/api/auth/me";
    const logoutUrl = headerEl.dataset.logout || "/api/auth/logout";
    const loginUrl = headerEl.dataset.loginUrl || "/pages/login.html";
    const signupUrl = headerEl.dataset.signupUrl || "/pages/signup.html";
    const profileUrl = headerEl.dataset.profileUrl || "/pages/account.html";

    bar.innerHTML =
      '<span class="auth-status" data-status="loading">Checking login…</span>';

    const handleLogout = async () => {
      const btn = bar.querySelector(".auth-logout");
      if (btn) btn.disabled = true;
      try {
        const res = await postWithCsrf(headerEl, logoutUrl);
        if (res.ok) {
          location.reload();
        } else {
          renderLoggedOut(bar, loginUrl, signupUrl);
        }
      } catch (err) {
        console.error("Logout failed:", err);
        renderLoggedOut(bar, loginUrl, signupUrl);
      }
    };

    try {
      const me = await getJSON(meUrl);
      if (me && (me.email || me.username || me.name || me.id)) {
        renderLoggedIn(bar, profileUrl, me, handleLogout);
      } else {
        renderLoggedOut(bar, loginUrl, signupUrl);
      }
    } catch (err) {
      console.error("Auth check failed:", err);
      renderLoggedOut(bar, loginUrl, signupUrl);
    }
  }

  // --- bootstrap ---
  document.addEventListener("DOMContentLoaded", () => {
    renderHeader();
    initAuthBar();
  });
})();
