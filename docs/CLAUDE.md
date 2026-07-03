# CLAUDE.md - Lumber Estimator

## Project Overview

A public, multi-tenant web application for building lumber material lists and estimates for construction projects. Users import project plans (images/PDFs) and trace structural elements (walls, floors, roof lines, openings) directly on the plan. Traced elements are assigned to material "tools" (e.g., a Wall tool) that automatically calculate required lumber using standard framing techniques and the project's job settings (stud spacing, floor heights, etc.). Users can also add manual material lines directly, independent of any plan trace. The primary deliverable is a clean, exportable material list that a user can hand to a lumber company for quoting. Pricing is optional: if a user has prices, the app totals them; if not, the material list stands on its own.

## Tech Stack

- **Backend:** Django 6.0 (Python 3.13)
- **Database:** PostgreSQL only (dev and prod both point at Postgres; no SQLite fallback)
- **Auth:** Custom email-based `User` model (`users` app, no `username` field) + Django's built-in `django.contrib.auth` views (login/logout/password reset) — no allauth. `django-axes` provides brute-force login protection.
- **Cache:** `django-redis` in prod, local-memory cache in dev
- **Frontend:** Django templates + HTMX for dynamic line item editing, plus Fabric.js (via CDN, no JS build step) for the plan-tracing canvas
- **PDF/image processing:** PyMuPDF (`fitz`) rasterizes uploaded PDF plans to per-page PNGs server-side at upload time; Pillow generates thumbnails
- **Static files:** WhiteNoise (prod only, via `CompressedManifestStaticFilesStorage`)
- **Payments:** Stripe (subscriptions; tiers TBD)
- **Deployment:** Render (web service + managed Postgres), gunicorn (Dockerfile + docker-compose also present for containerized dev/deploy)
- **Environment config:** `python-dotenv` loads `.env` into `os.environ`; settings read directly via `os.environ`

## Multi-Tenancy Model

- Row-level tenancy via foreign keys, not schema-per-tenant.
- **Account** is the tenant: every Project, Estimate, and PriceEntry belongs to an Account. `Account` lives in a new `accounts` app, alongside the existing `users` app (the custom `User` model already in place is not itself the tenant).
- A User belongs to one Account at launch (solo users get a personal Account created automatically at signup). Team membership under one Account is a planned follow-up.
- Every queryset in views MUST filter by `request.user.account`. A custom model manager (`AccountScopedManager`) enforces this; never query tenant-owned models with `.objects.all()` in views.
- No cross-tenant data access, ever, including in exports and admin-facing views.

## Application Flow

1. User signs up (custom `User` model + built-in Django auth views) and lands on a **Dashboard** listing their Projects.
2. From the Dashboard, **New Project** (`projects:create`) currently takes just name/client and auto-creates a `JobSettings` row with model defaults — the full Job Settings Wizard below is not yet built.
3. The **Project Detail** page (`projects:detail`) lists the project's uploaded **Plans**, each as a thumbnail gallery of its **PlanPages** with an inline label field (e.g. "First Floor").
4. Clicking a thumbnail opens the **Plan Viewer** (`plans:viewer`) — a Fabric.js canvas over that page's image. The user picks a **Tool** (currently just Line/Wall), sets its Material + settings (e.g. stud spacing) in the settings panel, and draws; each draw creates a **Trace** with that material/settings snapshotted onto it. Saved **ToolPresets** let a configured tool+material be reloaded later.
5. Completed Projects can be **Archived** from the Dashboard (soft-hide, not delete).

## Job Settings Wizard

**Not yet built.** Today, `JobSettings` is created with plain model defaults alongside a new Project (see `projects.views.ProjectCreateView`). The intended wizard runs when a Project is first created, before/alongside plan import, and should capture project-level answers that parameterize every Tool calculation, at minimum:

- Number of floors
- Basement height (if applicable)
- 1st floor wall height
- 2nd floor wall height (if applicable)
- Stud spacing (16" OC, 24" OC, etc.)
- Roof framing type: rafters, trusses, or both
- Floor material/system
- More questions will be added as calculation needs are identified.

Answers are stored as **JobSettings** on the Project. JobSettings should remain editable after initial setup; editing them should re-trigger recalculation of any LineItems generated from Tools (see Open Questions for how this interacts with manually-edited generated lines).

## Core Domain Concepts

- **Project:** A job being estimated (name, client, notes, status). Belongs to an Account.
- **Estimate:** A versioned snapshot of materials for a Project. A Project can have multiple Estimates.
- **Plan** (`plans.Plan`): An uploaded PDF attached to a Project, split into **PlanPages** at upload time (`plans.services.rasterize_plan`, PyMuPDF).
- **PlanPage** (`plans.PlanPage`): One rasterized page (full image + thumbnail) with a user-editable `label` (e.g. "First Floor", "Elevations").
- **Trace** (`plans.Trace`, doc-named "PlanLine" earlier): A user-drawn shape on a PlanPage (currently just `tool_type="line"` for walls). Stores `geometry` (JSON points in image pixel space) plus a **material** FK and a `settings` JSON blob (e.g. `{"stud_spacing_in": 16}`) that are **snapshotted at creation time** — changing the tool's settings panel afterward never mutates an already-drawn Trace. No automatic LineItem/quantity generation from a Trace exists yet; that's the still-pending `estimating` Tool-calculation engine described below.
- **Tool:** A material-generating behavior identified by `tool_type` (Line/Wall today; Floor Joist, Beam, Rafter/Truss planned). Right now `tool_type` is just a string on `Trace`/`ToolPreset` driving which settings the frontend shows — the actual calculation logic (turning a Trace into LineItems per standard framing rules) is not implemented yet.
- **ToolPreset** (`plans.ToolPreset`): An account-scoped saved `tool_type` + material + settings combo a user can reload into the settings panel on any project (unique per `account` + `tool_type` + `name`).
- **Opening:** A window or door placed on/within a wall Trace, with width and height, used to calculate header size/length and trimmer/cripple stud counts. Not yet modeled.
- **LineItem:** One lumber entry on an Estimate: species/grade, nominal dimensions (e.g., 2x4), length, quantity, waste factor, and an OPTIONAL unit price. May be manual or Tool-generated (`source="tool"` / `source="manual"`). Not yet modeled — depends on the Tool-calculation engine above.
- **MaterialProduct** (`catalog.MaterialProduct`): A catalog entry such as "2x6 SPF #2" or "Deck Screws 3in", with an auto-generated `slug` and an `input_type` (`ft` / `box` / `each`) that determines what other fields apply (stock lengths for `ft`, `quantity_per_box` for `box`). Global when `account` is blank (staff-managed via Django admin); an Account can also have its own private custom materials, isolated from other accounts (`MaterialProduct.objects.visible_to(account)`).
- **MaterialLength (Material Database):** Defines the stock lengths an `input_type="ft"` MaterialProduct is available in (e.g., 2x10 SPF #2 in 8'–24', 2' increments) and the default length used for total-length ÷ default-length calculations (`is_default`). The program can only ever use lengths that appear here (`MaterialProduct.stock_length_for()`).
- **PriceEntry (optional feature):** Per-account unit pricing. Pricing source is undetermined; treat all pricing as user-supplied and optional.

## Key Business Rules

- The material list is the product. Every feature must work with zero prices entered.
- Board feet = (nominal thickness x nominal width x length in feet) / 12.
- Waste factor is applied per line item (default 10%, configurable).
- Quantities round up to whole pieces; currency (when present) uses Decimal and rounds half-up to cents.
- If prices exist, they are snapshotted onto LineItems when applied, so historical estimates don't shift.
- Manual line items and Tool-generated line items coexist on the same Estimate; Tool recalculation must never clobber manual lines.
- All quantity calculations follow standard framing techniques as the baseline, parameterized by JobSettings:
  - **Wall Tool:** stud count derives from traced wall length and job stud spacing (OC), plus standard allowances for corners and opening rough openings; plate count derives from wall length and plate stock/default length (accounting for double top plate).
  - **Headers:** Opening width/height determine header size and length per standard framing rules; trimmer and cripple stud counts derive from opening height vs. wall height.
  - **Line-length-derived materials** (floor joists, beams, rafters, etc.) use the traced line's length directly, rounded up to the nearest available stock length for that product.
  - **Run-length-derived materials** (e.g., rim board, band board) are calculated as total run length ÷ that material's default length (from the Material Database), rounded up, unless the user overrides the default length for that use.
  - **Unit-sold materials** (sheathing, fasteners, adhesive, felt, etc.) use a per-unit rule keyed to the material's sale unit (each, ft, board ft, box, roll, sheet) as defined in the Material Database.

## Material Library & Database

- Launch material library is intentionally minimal: **2x4, 2x6, 2x8, 2x10, 2x12, all SPF #2**, seeded globally via a data migration (`catalog/migrations/0002_seed_dimensional_lumber.py`, fixed up to `input_type="ft"` in `0003`). Additional species/grades/dimensions are added incrementally as needed, via Django admin (`catalog.MaterialProductAdmin`, staff-only for now).
- Every `MaterialProduct` has an `input_type` (`ft` / `box` / `each`) that drives which other fields are relevant — enforced in `MaterialProduct.clean()` and toggled dynamically in the admin form via `catalog/static/catalog/admin/material_product.js`:
  - **ft**: stock lengths live in `MaterialLength`; `MaterialProduct.stock_length_for(required_ft)` returns the smallest in-stock length that covers a requirement.
  - **box**: `quantity_per_box` (e.g. 100 screws/box); `MaterialProduct.boxes_needed(quantity)` rounds up to whole boxes.
  - **each**: no extra fields.
- Catalog is global by default (`account=None`, staff-managed) plus per-account custom materials (`account` set), isolated from other accounts. Slug uniqueness is scoped accordingly — two accounts can each have their own "Custom Bracket".
- Per-use-case default length overrides (e.g., rim board at 16' regardless of a product's general default) are not yet modeled — still an open question below.

## Exports

- Material list export is the core workflow: printable web view + CSV at minimum (formats TBD, see Open Questions).
- Exports group by product (species/grade + dimension + length) with total piece counts, so a lumber yard can quote directly from it.
- Prices and totals appear on exports only if the estimate has pricing.

## Billing

- Stripe powers Account subscriptions.
- Subscription tiers, pricing, and feature gating are not yet defined — build the Account/subscription model to support tiered limits later rather than hardcoding a single tier.

## Project Structure

Apps live flat at the project root (not nested under `apps/`), matching the existing `users`/`core` apps:

```
lumber_estimator/
├── config/
│   └── Settings/         # base.py, dev.py, prod.py (note capital "Settings")
├── core/                 # existing: home page / marketing views
├── users/                # existing: custom User model, manager, admin
├── accounts/             # Account (tenant), AccountScopedManager; Stripe subscriptions still TBD
├── projects/             # Project, JobSettings, Estimate models; Dashboard/Create/Detail views (wizard still TBD)
├── plans/                # Plan, PlanPage, Trace, ToolPreset; upload/rasterize/viewer/trace/preset views
├── catalog/              # MaterialProduct, MaterialLength/Material Database, optional PriceEntry
├── estimating/           # NOT YET BUILT: Tool calculation engine (Trace -> LineItem), exports
├── templates/
├── static/
├── media/
├── logs/
├── requirements.txt
├── pyproject.toml        # pytest + ruff config
├── Dockerfile / docker-compose.yml
└── Procfile              # Render/gunicorn process command
```

New app boundaries above are a working proposal, not settled — adjust as the plan-tracing and Tool architecture solidifies.

## Conventions

- Calculation and Tool-expansion logic lives in plain Python modules (`estimating/calc.py`, `estimating/tools.py`), not in views or models, so it's unit-testable without the ORM.
- Money handled with `Decimal`, never floats. Price fields are nullable.
- Fat models / thin views; forms for validation.
- Tests with pytest + pytest-django; every calc/Tool function gets tests before wiring into views. Tenancy isolation gets explicit tests (user A can never see account B's data).
- Migrations are always committed; never edit an applied migration.

## Commands

```bash
# Local dev (defaults to config.Settings.dev via manage.py / pyproject.toml)
python manage.py runserver
python manage.py migrate
pytest

# Container (Dockerfile + docker-compose.yml already present)
docker-compose up --build
```

## Deployment Notes (Render)

- Deploys from the `Dockerfile`; process types come from `Procfile` (`web: gunicorn config.wsgi:application`, `release: python manage.py migrate` runs pre-deploy).
- `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `ALLOWED_HOSTS`, `DJANGO_SETTINGS_MODULE=config.Settings.prod`, `REDIS_URL`, `CSRF_TRUSTED_ORIGINS` set as Render environment variables (see `.env` for the full local list, loaded via `python-dotenv`).
- `DEBUG=False` in prod; WhiteNoise serves static assets; `django-redis` backs the cache.
- Public app: enable Render's managed TLS; `prod.py` already sets `SECURE_SSL_REDIRECT`, HSTS, and secure cookies.

## Open Questions

- **Tool-calculation engine (biggest gap):** Traces capture material + settings, but nothing yet turns a Trace into LineItems/quantities per the Key Business Rules above. This is the `estimating` app and is not started.
- Job Settings Wizard UI doesn't exist yet — New Project only takes name/client today; JobSettings gets model defaults.
- Additional tool types beyond Line/Wall (Floor Joist, Beam, Rafter/Truss) and Opening (window/door) placement are not built.
- Trace editing is create+delete only; no drag-to-edit vertices after drawing.
- PDF rasterization (`plans.services.rasterize_plan`) runs synchronously inside the upload request — fine for small plans, but will need to move to a background job (Celery/RQ, no such infra exists yet) for large multi-page PDFs.
- Plan/media file storage: currently Django's default FileSystemStorage under `MEDIA_ROOT`. Production needs a real backend (S3-compatible bucket, Render disk, Cloudinary) — not yet chosen.
- Recalculation behavior: once the Tool-calculation engine exists, does changing JobSettings/a Trace overwrite a manually-edited generated LineItem, warn, or flag it stale?
- Per-use-case default length overrides in the Material Database (e.g., rim board at 16' vs. a product's general default) — not yet modeled.
- Full list of standard framing rules/tables to encode per Tool (wall, floor joist, beam, rafter, truss, header) — need an engineering reference or source to encode against.
- Stripe subscription tiers, pricing, and feature gating — TBD.
- Export formats beyond printable view + CSV: PDF? Excel? Email directly to a supplier?
- Free vs paid tiers, estimate limits, or fully free at launch?
