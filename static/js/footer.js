function renderFooter() {
  const footerHTML = `
    <footer class="footer">
      <div class="footerbox">
        <div class="fbox" id="fbox1">
          <a href="../index.html">
            <img src="../assets/images/logo_main.png" alt="Tasty Truths logo" />
          </a>
        </div>

        <div class="fbox" id="fbox2">
          <p class="hover-menu">Pages ↑</p>
          <div class="popup">
            <a href="/index.html">Home</a>
            <a href="/pages/recipes.html">Recipes</a>
            <a href="/pages/contact.html">Contact</a>
            <a href="/pages/blog.html">Blog</a>
          </div>
        </div>

        <div class="fbox" id="fbox3">
          <a href="mailto:support@tastytruths.com?subject=Customer%20Support">
            Support
          </a>
        </div>

        <div class="fbox" id="fbox4">
          <a href="/pages/about_us.html">About Us</a>
        </div>

        <div class="fbox" id="fbox5">
          <a href="/pages/contact.html">Contact</a>
        </div>

        <div class="fbox" id="fbox6">
          <a href="mailto:tastytruths@gmail.com">
            <ion-icon name="mail-outline"></ion-icon>
          </a>
          <a href="tel:+1234567890">
            <ion-icon name="call-outline"></ion-icon>
          </a>
          <a href="https://www.instagram.com" target="_blank">
            <ion-icon name="logo-instagram"></ion-icon>
          </a>
          <a href="https://www.facebook.com" target="_blank">
            <ion-icon name="logo-facebook"></ion-icon>
          </a>
          <a href="https://www.youtube.com" target="_blank">
            <ion-icon name="logo-youtube"></ion-icon>
          </a>
        </div>
      </div>
      <small>&copy; 2025</small>
    </footer>
  `;

  const root = document.getElementById("footer-root");
  if (root) {
    root.innerHTML = footerHTML;
  }
}

// Run once the DOM is ready
document.addEventListener("DOMContentLoaded", renderFooter);
