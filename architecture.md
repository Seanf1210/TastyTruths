# Tasty Truths Architecture

## 1. High-level overview
- Flask app built around `create_app()` in `app.py`; single process with in-app route definitions (no blueprints) and Flask-Login + CSRF for session security.
- Data layer uses SQLAlchemy models in `services/models.py` with slug auto-generation events and SQLite (configured via `services/db.py`); Alembic migrations live in `migrations/`.
- Recipes feature: list, detail, random picker, creation form with image upload, slug history redirects, and JSON API for programmatic creation/listing.
- Blog feature: list, detail, random redirect, and author-only create/edit/delete flows sharing the same form class; posts linked to `User`.
- Auth layer: Argon2 password hashing, `UserMixin` model, `/login` + `/signup` HTML forms, and `/api/auth/*` JSON endpoints for JS clients.
- Templates (Jinja) in `templates/` extend `base.html`; shared header/footer markup and flash messaging live there, with page-specific bodies for recipes, blog, auth, and static info pages.
- Static assets under `static/`: CSS, images, and small JS helpers; only `static/js/script.js` is currently loaded globally for fetch helpers and dark-mode toggle.
- Helper scripts in `helpers/` seed or clean the SQLite DB; `documentation/` contains feature notes and checklists for recipe forms.
- Legacy/experimental code: `PROTOTYPE/` (early Flask UI), `utilities/models.py` (standalone declarative models), and unused JS modules (`header.js`, `footer.js`, `recipes-page.js`, `create-recipe.js`, `store.js`, `dataProvider.js`).
- Why Flask + JS helpers: The repo leans on Jinja rendering with minimal JS (only dark-mode + a few fetch helpers) and WTForms for validation, showing a preference for server-rendered pages with lightweight progressive enhancement rather than a bundled SPA.

## 2. Repository structure (tree)
```
.
├── app.py                      # Flask app factory + all routes
├── services/
│   ├── db.py                   # SQLAlchemy() extension instance
│   ├── models.py               # Recipe, BlogPost, RecipeSlugHistory, User + slug events
│   ├── forms.py                # WTForms: RecipeForm, BlogPostForm
│   └── recipes.py              # Legacy recipe creation helper (unused, stale import)
├── utilities/
│   ├── slug.py                 # Slug generation helpers used by models
│   ├── recipe_filters.py       # Recipe query helpers (diet, time, cuisine)
│   └── models.py               # Standalone declarative models (prototype)
├── templates/                  # Jinja pages (base, recipes, blog, auth, info)
│   └── partials/_recipe_card.html
├── static/
│   ├── css/styles.css
│   ├── js/ {script.js, header.js, footer.js, create-recipe.js, recipes-page.js, store.js}
│   └── assets/ {images, favicon, ingredients_starter.json} + uploads/recipes/
├── migrations/                 # Alembic env + versions
├── helpers/                    # DB seed/cleanup/check scripts
├── documentation/              # How-to docs for recipe form and implementation
├── PROTOTYPE/                  # Early Flask prototype app/templates
├── dataProvider.js             # JS provider wrapper around store.js (unused by Jinja pages)
├── instance/site.db            # Dev SQLite database
├── requirements.txt, instructions.txt, CNAME
└── README.md                   # (left unchanged)
```

## 3. Request flow map
- **A) View a recipe**
  - Browser GET `/recipes/<id>-<slug>` → `app.recipe_detail`.
  - Parses `id`, fetches `Recipe` via `db.session.get`; if slug mismatch, redirects to canonical; falls back to `RecipeSlugHistory` for old slugs.
  - Prepares `ingredients_list` (newline split) → renders `templates/recipe_detail.html` with recipe + ingredients.
  - Template extends `base.html`; pulls image from `static/uploads/recipes/…`; global `static/js/script.js` runs dark-mode helper only (no extra JS for this page).

- **B) Create/edit a recipe (edit not implemented)**
  - Browser GET `/recipes/create` → `app.create_recipe_page` shows `RecipeForm` (WTForms) in `templates/create_recipe.html`.
  - POST with CSRF: validates; optional image saved to `static/uploads/recipes/` (ensures dir, uses `secure_filename` + UUID); normalizes ingredients; writes `Recipe` row (author = `current_user.id`).
  - On success: redirect to `/recipes/<id>-<slug>`; on SQL error, flashes message and rolls back.
  - JSON API alternative: POST `/api/recipes` (login_required, CSRF exempt) accepts `{title, content}`; returns id/slug JSON; consumed by no current template (legacy `create-recipe.js` exists but is not included).
  - Editing path: **Unknown (needs confirmation)** — no route/form present.

- **C) View a blog post**
  - Browser GET `/blog/<slug>` → `app.blog_post`; queries `BlogPost` by slug.
  - Renders `templates/blog_post.html` with post, author (via relationship), and random blog link; owner-only edit/delete controls link to `/blog/<slug>/edit` and POST `/blog/<slug>/delete`.
  - Listing: `/blog` renders `templates/blog.html`; random redirect at `/blogs/random`.

## 4. Dependency diagrams (Mermaid)
### A) System-level
```mermaid
graph TD
    Browser -->|HTTP routes| AppRoutes[app.py routes/views]
    AppRoutes --> Forms[services/forms.py]
    AppRoutes --> Models[services/models.py]
    Models --> DB[services/db.py -> SQLite]
    AppRoutes --> Templates[templates/*.html]
    Templates --> StaticCSS[static/css/styles.css]
    Templates --> ScriptJS[static/js/script.js (global helpers)]
    AppRoutes -->|JSON| APIs[/api/auth/*, /api/recipes*]
    APIs --> Browser
```

### B) JS helpers inclusion
```mermaid
graph TD
    BaseTemplate[templates/base.html] --> ScriptJS[static/js/script.js\n(getJSON, postWithCsrf, dark-mode)]
    LegacyPages[(no current template reference)] -.-> HeaderJS[static/js/header.js\n(auth bar renderer)]
    LegacyPages -.-> FooterJS[static/js/footer.js]
    LegacyPages -.-> CreateRecipeJS[static/js/create-recipe.js\n(AJAX form handler)]
    LegacyPages -.-> RecipesPageJS[static/js/recipes-page.js\nlocalStorage demo]
    DataProvider[dataProvider.js] --> StoreJS[static/js/store.js\nlocalStorage CRUD]
    Note[Only script.js is actually loaded by live Jinja pages; others are unused/legacy]:::note
    classDef note fill:#fff3cd,stroke:#d39e00,color:#000;
```

## 5. Module inventory
- **app.py**
  - Imports: `services.db`, `services.models (Recipe, RecipeSlugHistory, BlogPost, User)`, `services.forms`, Flask/SQLAlchemy/Flask-Login/CSRF utilities.
  - Class: `AdminOverrideUser` (dev-only identity for bypassing login).
  - Functions:
    - `create_app(admin_override=False)`: configures Flask + extensions, optional admin override hook, registers routes, calls `db.create_all()`, returns app.
    - Routes: `/` index (featured recipe/blog), `/about`, `/contact`, `/recipes`, `/recipes/<id_slug>`, `/recipes/random`, `/recipes/create` (form), `/api/recipes` (JSON create + list), `/blog`, `/blog/new`, `/blog/<slug>`, `/blog/<slug>/edit`, `/blog/<slug>/delete`, `/blogs/random`, `/signup`, `/login`, `/logout`, `/api/auth/register|login|me|csrf-token`, `/api/whoami`, 404 handler.
    - CLI helpers: `_parse_args()`, `_run_dev_server()`, module-level `app = create_app()` when imported by WSGI.
  - Callouts: only entrypoint; admin override logs every request; `db.create_all()` inside factory could diverge from Alembic migrations.

- **services/db.py**
  - Imports: Flask-SQLAlchemy.
  - Object: `db = SQLAlchemy()`; used by models and app factory.

- **services/models.py**
  - Imports: `services.db`, `utilities.slug.base_slug/uniquify_slug`, `argon2.PasswordHasher`, `flask_login.UserMixin`.
  - Classes:
    - `Recipe`: fields for title/slug/content/description/instructions/ingredients/image, timing, cost, cuisine, dietary_tags (JSON), rating, created/updated timestamps, `author_id` FK.
    - `BlogPost`: fields for user_id/title/slug/summary/content/timestamps; relationship `author`.
    - `RecipeSlugHistory`: keeps old slugs for redirects.
    - `User`: auth model with username/email/password_hash, profile fields, relationship to BlogPost; `set_password`/`check_password`.
  - Events: `blog_before_insert`, `recipe_before_insert`, `recipe_before_update` to auto-create/rotate slugs and store history.

- **services/forms.py**
  - Imports: WTForms/Flask-WTF.
  - Classes:
    - `RecipeForm`: title, instructions, ingredients, image upload, prep/cook time, estimated cost; validation and placeholders.
    - `BlogPostForm`: title, summary, content; basic validation.

- **services/recipes.py** (legacy/unused)
  - Imports: `utilities.slug.basic_slugify` (missing in `utilities/slug.py`, so currently broken), `utilities.slug.uniquify_slug`, `models.Recipe` (wrong import path).
  - Functions: `slug_exists`, `create_recipe(session, title, author_id, content="")` to generate slug and commit.
  - Callout: not referenced anywhere; would fail due to bad imports if executed.

- **utilities/slug.py**
  - Functions: `base_slug(title, max_len=80)` (slugify), `uniquify_slug(session, Model, base, exclude_id=None)` loop appending `-2`, `-3`, … to ensure uniqueness.

- **utilities/recipe_filters.py**
  - Imports: `services.db`, `services.models.Recipe`, `sqlalchemy.and_`.
  - Functions: `get_recipes_by_dietary_tags`, `get_recipes_by_max_prep_time`, `get_recipes_by_prep_time_range`, `get_recipes_by_cuisine`, `get_recipes_by_multiple_filters`, `get_all_available_dietary_tags`, `get_all_available_cuisines`.
  - Callouts: Not wired to routes/templates yet; ready for future filter UI.

- **utilities/models.py** (legacy)
  - Declarative `Base` with `Recipe` and `RecipeSlugHistory` definitions similar to current models; unused in live app.

- **helpers/**
  - `seed.py`: runs `create_app()`, seeds three sample recipes (multi-field), optionally clears existing data.
  - `seed_blog.py`: seeds example blog posts (similar structure).
  - `delete_recipes.py`, `delete_blog_posts.py`: purge tables.
  - `check_db.py`: quick SQLite migration version check.
  - `check_schema.py`: prints table schemas (uses SQLite PRAGMAs).
  - `test_app.py`: basic Flask test client checks for home page.
  - Callout: operational scripts; not imported by app runtime.

- **migrations/**
  - `env.py` + versions: two revisions adding recipe fields and expanding users; `down_revision` mismatch (`initial_recipes` missing) needs attention.

- **PROTOTYPE/app.py**
  - Minimal Flask routes for recipe list/detail using `services` models; prototype templates under `PROTOTYPE/templates/`; not used by main app.

### Static JS helper inventory
- `static/js/script.js` (ES module; loaded via `base.html`): exports `getJSON`, `escapeHtml`, `postWithCsrf`; auto-initializes theme toggle (dark mode) on DOMContentLoaded.
- `static/js/header.js` (IIFE): renders header/auth bar using `/api/auth/me` and `/api/auth/logout`; **not included in current Jinja templates**.
- `static/js/footer.js` (IIFE): injects footer markup; **not included in current Jinja templates**.
- `static/js/create-recipe.js` (IIFE): client-side validator + POST to `/api/recipes`; expects `#recipeForm` with loaders; **not referenced by live templates** (legacy).
- `static/js/recipes-page.js` (ES module): demo recipes filter using `store.js` seed data; **not referenced by live templates**.
- `static/js/store.js` (ES module): localStorage CRUD with slug handling; not loaded by templates.
- `dataProvider.js` (root): wraps `store.js` or future API calls; not imported anywhere in Jinja-rendered pages.

## 6. “If you’re new here” orientation
- Start with `app.py` to see the app factory, routes, and how auth/CSRF/login manager are wired.
- Read `services/models.py` to understand the DB schema, slug events, and relationships.
- Skim `templates/base.html` then the feature pages (`recipes.html`, `recipe_detail.html`, `blog.html`, `blog_post.html`, `create_recipe.html`, `blog_new.html`) to see how data is presented.
- Check `services/forms.py` for validation rules used by the create/edit forms.
- Look at `static/js/script.js` to know which JS helpers are available on every page; other JS files are currently unused/legacy.
- For database changes, open `migrations/` to see existing revisions and run flask-migrate commands rather than relying on `db.create_all()`.

**Common changes**
1. Add a new page/route: define route in `app.py`, create a template under `templates/`, add navigation link in `templates/base.html`, and (if needed) a WTForm in `services/forms.py`.
2. Add a JS helper: place it in `static/js/`, include it explicitly in the target template with `<script type="module" src="{{ url_for('static', filename='js/your-file.js') }}"></script>`, and document which page loads it.
3. Add a DB model/migration: update/extend `services/models.py`, generate an Alembic migration (`flask db migrate`), review it, then apply (`flask db upgrade`); avoid relying on `db.create_all()` for schema drift.
4. Add a blog/recipe feature: reuse `RecipeForm`/`BlogPostForm` patterns, ensure slug handling via existing events, and surface data in templates; for API endpoints, mirror the JSON patterns in `/api/recipes` and `/api/auth/*`.

## Python ↔ JS boundary
- Server-rendered (Jinja) data: home page featured recipe/blog, recipe detail fields (including ingredients list and image URLs), blog listings and posts, auth forms, and flash messages. Template variables are passed directly from `render_template` in `app.py`.
- Client-fetched data: `/api/recipes` JSON is fetched inline in `templates/recipes.html` to render the simple list; `/api/auth/me` and `/api/auth/logout` are intended for `header.js` (but that script is not loaded); `/api/auth/csrf-token` supports JS POST helpers.
- JS helpers wiring: only `static/js/script.js` is currently loaded everywhere (dark-mode toggle + fetch helpers). Other helpers (`header.js`, `footer.js`, `create-recipe.js`, `recipes-page.js`, `store.js`, `dataProvider.js`) are not referenced by active templates and provide no runtime effect unless added.
- Validation split: server-side validation via WTForms (`RecipeForm`, `BlogPostForm`) and explicit checks in `/signup` and API routes; client-side validation exists in legacy `create-recipe.js` and minor password-field reset logic in `templates/signup.html`, but primary enforcement is on the server.

## Risks / TODOs
- `services/recipes.py` imports `basic_slugify` (not defined in `utilities/slug.py`) and uses an incorrect `models` import; using it would error — either fix or remove the module.
- Alembic history references `down_revision='initial_recipes'` (missing revision), and `db.create_all()` in `create_app()` may bypass migrations; align migration chain and rely on upgrades instead of create_all for production.
- Unused JS helpers (`header.js`, `footer.js`, `create-recipe.js`, `recipes-page.js`, `store.js`, `dataProvider.js`) add maintenance overhead; either wire them into templates or prune.
- Prototype code (`PROTOTYPE/`, `utilities/models.py`) duplicates model definitions; clarify ownership to avoid drift.
