// Escape user-supplied text safely
function escapeHtml(str) {
  return str.replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      }[c])
  );
}

// Render static header layout
function renderHeader() {
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
        <!-- Left: Logo -->
        <div class="logo">
          <a href="/">
            <img src="/assets/images/logo_main.png" alt="Tasty Truths logo" />
          </a>
        </div>

        <!-- Middle: Main nav -->
        <nav class="main-nav" aria-label="Primary">
          <a href="/pages/about_us.html">About</a>
          <a href="/pages/recipes.html">Recipes</a>
          <a href="/pages/blog.html">Blog</a>
        </nav>

        <!-- Right: Auth state. Uses .auth-links styling -->
        <div
          id="auth-bar"
          class="auth-links"
          aria-live="polite"
          aria-atomic="true"
        ></div>
      </div>
    </header>
  `;

  document.getElementById("header-root").innerHTML = headerHTML;
}

// Called when the DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // 1. Put the header into #header-root
  renderHeader();

  // 2. Now that #auth-bar exists, fill it with logged-out content
  initAuthBar();
});

function initAuthBar() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const authBar = document.getElementById("auth-bar");
  if (!authBar) return;

  const loginUrl = header.dataset.loginUrl || "/pages/login.html";
  const signupUrl = header.dataset.signupUrl || "/pages/signup.html";

  // For now, always show logged out; later you can add a fetch() here
  renderLoggedOut(authBar, loginUrl, signupUrl);
}

// RENDER: Logged out view
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

// RENDER: Logged in view
function renderLoggedIn(bar, profileUrl, user, onLogout) {
  const label = user.username || user.name || user.email || "your account";

  bar.innerHTML = `
    <span class="auth-status" data-status="logged-in">
      Logged in as <a class="auth-user" href="${profileUrl}">${escapeHtml(
    label
  )}</a>
    </span>
    <button type="button" class="auth-logout">Log out</button>
  `;

  const btn = bar.querySelector(".auth-logout");
  btn.addEventListener("click", onLogout);
}
