# CLAUDE.md - Lumber Estimator

## Project Overview

A public, multi-tenant web application for building lumber material lists and estimates for construction projects. Users import project plans (images/PDFs) and trace structural elements (walls, floors, roof lines, openings) directly on the plan. Traced elements are assigned to material "tools" (e.g., a Wall tool) that automatically calculate required lumber using standard framing techniques and the project's job settings (stud spacing, floor heights, etc.). Users can also add manual material lines directly, independent of any plan trace. The primary deliverable is a clean, exportable material list that a user can hand to a lumber company for quoting. Pricing is optional: if a user has prices, the app totals them; if not, the material list stands on its own.

## Tech Stack

- **Backend:** Django 6.0 (Python 3.13)
- **Database:** PostgreSQL only (dev and prod both point at Postgres; no SQLite fallback)
- **Auth:** Custom email-based `User` model (`users` app, no `username` field) + Django's built-in `django.contrib.auth` views (login/logout/password reset) - no allauth. `django-axes` provides brute-force login protection.
- **Cache:** `django-redis` in prod, local-memory cache in dev
- **Frontend:** Django templates + HTMX for dynamic line item editing, plus Fabric.js (via CDN, no JS build step) for the plan-tracing canvas
- **PDF/image processing:** Plans can be uploaded as PDF or a plain image (PNG/JPEG). PDFs are rasterized page-by-page with PyMuPDF (`fitz`) into per-page PNGs server-side at upload time; a plain image upload becomes a single page directly (re-encoded to PNG, no PyMuPDF resampling). Pillow generates thumbnails either way.
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
2. From the Dashboard, **New Project** (`projects:create`) opens the built 3-step setup wizard (Project / Structure / Framing) and now also shows reusable **Project Templates**. Starter templates seed common house types, account-owned templates can be saved from job settings, and the wizard automatically preselects the user's favorite template when available or the first starter/default template otherwise.
3. The **Project Detail** page (`projects:detail`) lists the project's uploaded **Plans**, each as a thumbnail gallery of its **PlanPages** with an inline label field (e.g. "First Floor") and a **Delete Page** button (`plans:page-delete`) - not every page in an uploaded PDF package is wanted, so pages can be trimmed individually without re-uploading or discarding the whole Plan. Upload now defaults to **Upload and Open**, which jumps straight into the first generated page in the viewer and prompts the user to calibrate instead of bouncing back through project detail. Deleting a page cascades its Traces and their LineItems (same FK cascade as deleting a Trace directly) and removes its image/thumbnail files from storage; the parent Plan is left in place even with zero pages remaining.
4. Clicking a thumbnail (or landing there immediately after upload) opens the **Plan Viewer** (`plans:viewer`) - a Fabric.js canvas over that page's image. Before quantities can be computed, the page must be **calibrated**: the Calibrate tool draws a reference line and the user enters its real-world length in feet, setting `PlanPage.scale_pixels_per_foot`. The user then picks the **Line/Wall tool**, sets Material and/or Assembly + settings (e.g. stud spacing) in the settings panel, and draws; each draw creates a **Trace** with that material/assembly/settings snapshotted onto it. If an Assembly is assigned, the calculation engine runs immediately against the trace's real measured length (from geometry + the page's calibration), generating `LineItem`s on the project's `Estimate`. Saved **ToolPresets** let a configured tool+material be reloaded later, and editing a selected trace in the inspector now auto-saves after a short debounce while keeping a manual **Save now** fallback.
5. The **Estimate/BOM view** (`estimating:estimate-detail`, linked from the project detail page) lists the computed `LineItem`s - the actual material list - and tool-generated rows now include a **Jump to source** link back to the exact plan page/trace that created them.
6. Completed Projects can be **Archived** from the Dashboard (soft-hide, not delete).

## Intelligent Material / Assembly Drawing Direction

The plan tools should evolve from generic drawing primitives into material-aware and assembly-aware tools. Today the viewer exposes basic line, polyline, area, count, and opening traces. Those should remain as low-level geometry primitives, but the user-facing workflow should increasingly be framed around construction elements:

- Draw Wall
- Draw Joist
- Draw Beam
- Draw Opening
- Draw Roof / Floor Area
- Count Posts / Hardware

A wall should not be treated as merely a measured line. A wall is an intelligent parametric object whose control geometry is a line or polyline in plan view. The line stores the wall path, but the attached assembly and settings define the actual buildable wall system.

### Wall Object Concept

A wall trace should be able to carry:

- Geometry: start point, end point, length, wall height, thickness, orientation, and optional polyline path.
- Assembly: e.g. 2x4 interior wall, 2x6 exterior wall, PT bottom plate, double top plate, sheathing, drywall, siding, house wrap, etc.
- Framing settings: stud spacing, plate count, bottom plate type, wall height, corner/end rules, waste rules, and account/project defaults.
- Openings: windows and doors that cut into the wall and drive king studs, jack/trimmer studs, headers, sills, and cripples.
- Generated members: studs, plates, headers, jacks, kings, cripples, blocking, sheathing panels, and other assembly components.
- Overrides: user edits such as moved/deleted studs, changed header size, added blocking, or locked custom members.

The line should be the simple plan-view interaction. The wall itself should be generated procedurally from the trace, assembly, job settings, openings, and stored overrides.

### Procedural Generation First, Overrides Second

Do not store every stud and plate as a permanent database row by default. Generate framing members procedurally whenever the wall is viewed or recalculated. Store only the input geometry, assembly/settings snapshot, related openings, and manual overrides.

Recommended model:

1. User draws a wall line or wall polyline.
2. User assigns a wall assembly.
3. The backend measures the trace using page calibration.
4. The wall framing engine generates an elevation model: plates, studs, openings, headers, jacks, kings, cripples, and related material quantities.
5. The estimating engine generates or updates LineItems.
6. If the user modifies individual members in an elevation/framing view, store only those overrides and reapply them after procedural regeneration.

This keeps the database small and makes geometry edits safe. A changed wall length or changed opening should rebuild the generated model cleanly while preserving explicit user overrides where possible.

### Wall Elevation / Framing / 3D Views

Clicking an intelligent wall trace should eventually expose additional views:

- Plan View: the current traced line/polyline on top of the uploaded plan.
- Wall Elevation View: a flat view of the wall showing plates, studs, openings, headers, jacks, kings, cripples, and blocking.
- Framing View: a simplified framing-only view with materials/layers hidden.
- 3D View: an orbitable/exploded wall model where layers such as drywall, framing, sheathing, wrap, siding, and insulation can be toggled.

The first production slice should be a read-only/generated wall elevation JSON + SVG preview. Later iterations can add direct editing of generated members, persisted overrides, and full 3D rendering.

### Opening Attachment

Opening traces should eventually attach to a parent wall rather than remain independent measurements. A window or door opening should cut the parent wall and regenerate the framing around it:

- King studs at both sides.
- Jack/trimmer studs based on header support rules.
- Header sized by opening width and assembly/account defaults.
- Sill and cripple studs for windows.
- Door openings without sill cripples below the opening.

Until explicit parent-child attachment exists, nearby opening traces on the same PlanPage can be projected onto the selected wall path to produce a best-effort wall elevation preview.

### UX Direction

The current primitive tools can remain internally, but the visible UI should move toward construction-language tools. For example, `line` can remain the stored tool_type, while the button label and workflow become `Draw Wall`. Likewise area traces can power joists, roof areas, floor systems, sheathing, and other material assemblies.

The preferred long-term mental model is:

`Draw construction element -> assign material/assembly -> generate viewable/editable model -> generate material list.`

This is intentionally a lightweight BIM/takeoff hybrid: easier than Revit, richer than a simple takeoff line.

## Job Settings Wizard

**Built.** `projects.views.ProjectCreateView` is now a `FormView` using `ProjectSetupForm`, a 3-step client-side wizard (Project / Structure / Framing) in `templates/projects/project_form.html`. Step navigation validates each step with HTML5 validity before advancing; basement-height and second-floor-height fields show conditionally; a server-side error lands the user on the first step containing it. `form.save_with_settings(account)` creates the Project, its `JobSettings`, and its first `Estimate` in one shot. `JobSettingsUpdateView` (`projects:job-settings`) edits settings afterward via `JobSettingsForm`; changing them does not retroactively recompute already-drawn traces (they carry a settings snapshot), but new/re-saved traces pick up the new defaults. The wizard captures the project-level answers that parameterize every Tool calculation:

- Number of floors
- Foundation type: slab on grade, crawl space, or full basement (`JobSettings.FoundationType`) - a slab has no floor framing at all, so this isn't just a basement-or-not toggle; basement wall height is required only for `full_basement`
- Basement height (if foundation is a full basement)
- 1st floor wall height
- 2nd floor wall height (if applicable)
- Stud spacing (16" OC, 24" OC, etc.)
- Roof framing type: rafters, trusses, or both
- Roof pitch (`roof_pitch_rise_per_12`, e.g. 6 for a 6/12 pitch) - optional, informational only today; nothing in the calc engine consumes it yet (rafter length is still a flat run from the traced bounding box, not pitch-adjusted true length) - a plausible future use, not implemented
- Floor material/system
- Siding / exterior finish (`siding_material`, free text like `floor_material` - too diverse across regions/products for a fixed enum)
- More questions will be added as calculation needs are identified.

Answers are stored as **JobSettings** on the Project. JobSettings should remain editable after initial setup; editing them should re-trigger recalculation of any LineItems generated from Tools (see Open Questions for how this interacts with manually-edited generated lines).

## Core Domain Concepts

- **Project:** A job being estimated (name, client, notes, status). Belongs to an Account.
- **Estimate:** A versioned snapshot of materials for a Project. A Project can have multiple Estimates.
- **Plan** (`plans.Plan`): An uploaded PDF or image attached to a Project, split into **PlanPages** at upload time (`plans.services.rasterize_plan`).
- **PlanPage** (`plans.PlanPage`): One rasterized page (full image + thumbnail) with a user-editable `label` (e.g. "First Floor", "Elevations") and an optional `scale_pixels_per_foot` (null until the Calibrate tool is used on that page - one scale per page, reused by every Trace drawn on it; recalibrating does **not** retroactively recompute already-drawn traces' LineItems). `PlanPageCalibrateView` (`plans/views.py`) supports two ways to set it: (a) draw a reference line and enter its real-world length in feet (the original flow - `pixels_per_foot = pixel_length(geometry) / known_length_ft`), or (b) pick a preset architectural drawing scale (e.g. "1/4 in = 1 ft", offered as a dropdown of standard scales from 1/16" to 1" in the Calibrate tool panel) with no line drawn at all - `plans.services.RENDER_ZOOM` (2.0, i.e. 144 DPI) is a fixed constant PyMuPDF rasterizes every PDF page at, so a stated print scale alone fully determines `pixels_per_foot = RENDER_ZOOM * 72 * scale_inches_per_foot`. (b) is only accurate for pages actually rasterized at that DPI (PDF uploads) - a plain image upload's real DPI is unknown/arbitrary, so the preset-scale path will silently be wrong there; (a) remains the reliable option for those pages, and the panel copy says so.
- **Trace** (`plans.Trace`): A user-drawn shape on a PlanPage. Five `tool_type`s exist: `line` (walls/beams, 2 points), `polyline` (an arbitrary multi-segment path that can optionally close into a polygon), `area` (floors/roofs/sheathing, a rectangle from 2 opposite corners), `count` (posts/hardware, N clicked points, no calibration required), and `opening` (windows/doors, 2 points = the opening width). Stores `geometry` (JSON points in image **pixel** space), an optional display `color`, a **material** FK, an optional **assembly** FK, and a `settings` JSON blob (line: `{"stud_spacing_in", "wall_height_in"}`; polyline: `{"closed"}`; area: `{"spacing_in", "member_direction"}`; opening: `{"stud_spacing_in"}`) - all **snapshotted at creation time**, so changing the settings panel afterward never mutates an already-drawn Trace. Open polylines measure total segment LF; closed polylines also expose area, perimeter, and bounding-box measurements. `material` alone is display-only (no calculation); when `assembly` is set, creating/updating the Trace computes its real-world measurement via `plans.geometry.measure_geometry(tool_type, geometry, scale, settings)` and calls `estimating.calculations.generate_line_items()`, wrapped in a transaction so a calc failure rolls back the whole request (no orphaned trace).
- **Measurement** (`plans.geometry.measure_geometry`): Converts a Trace's pixel geometry + the page's calibration into a dict the calc engine consumes: line/opening give `{length_ft}`; area gives `{area_sqft, perimeter_ft, bbox_width_ft, bbox_height_ft}` (shoelace area, bounding box for member runs); count gives `{count}` and needs no scale.
- **Tool:** A material-generating behavior identified by `tool_type` (line, area, count, opening). `tool_type` is a string shared by `Trace`, `ToolPreset`, and `estimating.Assembly`, driving which settings the frontend shows and which assemblies apply to which kind of trace. The viewer (`plans/static/plans/viewer.js`, Fabric.js) renders each tool distinctly: line (solid), opening (thick dashed), area (translucent polygon), count (group of circles); traces with an assembly assigned turn green. A rubber-band preview follows the cursor while drawing. `canvas.skipTargetFind` is set true whenever ANY tool is active (not just Hand) - otherwise clicking to place a point on or near an already-drawn trace (e.g. continuing a wall from where the last segment ended) would hover Fabric's "move" cursor and select that trace instead of placing a point, which also silently deactivated the active tool via the selection handler; only idle (no tool active) leaves traces selectable for inspection. This means a tool stays "sticky" and unselectable-around for as long as it's armed, by design (continuous drawing shouldn't require reselecting the tool for every trace) - but it also means there must be an explicit way back to idle/selectable mode, since a semantic tool (Wall/Plate/etc.) has no dedicated "none" button of its own: clicking the *same* active semantic-tool button again turns it off (mirroring the raw tool buttons, which already toggle off on a second click), and pressing **Escape** with nothing currently pending also deactivates the active tool outright. For multi-point tools (Polyline, Count), Enter, double-click, or Escape all finish the shape and keep everything already placed; Escape only falls back to a full cancel/reset when nothing meaningful has been placed yet (below the tool's minimum point count), and to deactivating the tool entirely when nothing at all is pending - for 2-point tools (raw Line, Opening, Area) Escape still just cancels the in-progress first point, since there's nothing partial to "finish." On top of these raw geometry tools, the sidebar also has **semantic construction tools** (Wall, Opening, Beam, Joist, Column, Plate, Rim Board) - see Semantic Toolbar & Dynamic Opening Resolution below - plus a **Hand tool** (`data-tool="hand"`) that pans the view by click-dragging, adjusting `#plan-canvas-wrap`'s native `scrollLeft`/`scrollTop` (consistent with how zoom already works by resizing the canvas raster and relying on native scroll, rather than Fabric's own viewportTransform panning). `#plan-canvas-wrap` has a fixed `height: 80vh` (not `max-height`) specifically so the "Fit" zoom button's measurement of the available viewport is stable regardless of the current zoom level - `max-height` let the wrapper shrink to fit a small-zoomed canvas, making the fit-ratio calculation self-referential and unreliable. The zoom level itself is scoped per `PlanPage` and remembered across an ordinary browser reload, but resets to fit on any other kind of arrival at the page (first visit, following a link, switching pages): `viewer.js` writes `currentZoom` to `sessionStorage` (keyed `plan-viewer-zoom:<page id>`) on every `setZoom()` call, and on load checks the Navigation Timing API (`performance.getEntriesByType('navigation')[0].type === 'reload'`) - only a true reload restores the stored value via `applyInitialZoom()`; every other navigation type calls `fitToView()` instead. Clicking "Fit" itself is just a manual `fitToView()` call, so it re-persists too.
- **ToolPreset** (`plans.ToolPreset`): An account-scoped saved `tool_type` + material + settings combo a user can reload into the settings panel on any project (unique per `account` + `tool_type` + `name`).
- **Assembly** (`estimating.Assembly`): A named, reusable bundle of `CalculationRule`s applied together against one measurement - e.g. "2x6 Wall - 16 in OC" bundles a stud rule + top plate rule + bottom plate rule. Global when `account` is blank (staff-managed) plus per-account custom assemblies, same visibility pattern as `MaterialProduct` (`Assembly.objects.visible_to(account)`). This is the MiTek Sapphire / STACK "Item + Assembly" pattern: reusable formula+material components bundled into one reusable takeoff-to-BOM step. `estimating/migrations/0004_seed_house_assemblies.py` ships one per tool type: `line` (2x4 wall, 2x6 exterior-on-slab with PT plate, double LVL beam), `area` (2x10 floor joists + rim + subfloor, 2x8 rafters + CDX + felt, roof trusses + CDX + felt, wall sheathing OSB + wrap), `opening` (2x10 header + king/trimmer/cripple studs), and `count` (4x4 PT post, 2x10 joist hangers). The original `0002_seed_wall_assembly.py` 2x6 wall remains. `estimating/migrations/0010_fix_rafters_and_seed_fasteners.py` fixes the rafter multiplier bug and adds a "Framing Nails" `per_box` example. `House_Lumber_Takeoff_Formulas.xlsx` (repo root) is the reference workbook every formula/waste-factor/coverage value was checked against - re-check it here first before changing any formula_kind math. Each `Assembly` also has a `category` (`Assembly.Category` - Foundation & Sill, Floor System, Wall System, Openings, Stairs, Ceiling, Roof, Siding & Exterior Trim, Exterior Deck, Miscellaneous, matching `docs/Lumber Estimator Takeoff.docx`'s build-order structure), which drives how the material list groups its output (see the Material List Output section below). `estimating/migrations/0012_backfill_categories.py` categorizes the known global assemblies by name - a starting best-guess, adjustable per-assembly via the now-categorized `AssemblyForm`.
- **Formula** (`estimating.Formula`): A reusable, account-scoped scalar calculation built from a measured trace value. Four global stock formulas are seeded: Line LF, Area SF, Perimeter LF, and Count. Users can derive formulas by applying a multiplier and fixed add-on (for example, Line LF × 3), then select those formulas on material rules in custom assemblies. Formula/assembly browsing and creation live at `estimating:library`; formulas are restricted to compatible tool types and cannot reference another account's private formula.
- **CalculationRule** (`estimating.CalculationRule`): One formula within an Assembly - a `material`, a `role` (e.g. "Stud", "Top Plate", shown on the BOM), a `formula_kind` (a fixed parameterized set, not a free-form expression language), plus `multiplier`/`extra`/`waste_factor`/`coverage_sqft`/`units_per_measurement` parameters. `evaluate_rule()` returns `(raw_quantity, piece_length_ft_or_None)`, so length-aware rules (studs sized to wall height, joists to member run, headers to opening width) set `LineItem.length_ft` while count/coverage/box rules leave it null. Verified line-by-line against `House_Lumber_Takeoff_Formulas.xlsx` (a reference workbook of standard takeoff formulas) - everything matched except the rafter multiplier bug noted below, now fixed. The nine kinds:
  - **`per_spacing`** - studs/cripples along a line: `ceil(length_ft × 12 / spacing) + extra + junction_extra`; piece length from `wall_height_in` when present. `junction_extra` comes from `corner_stud_count`/`t_intersection_stud_count`/`t_backer_stud_count` × the wall's detected corner/T-intersection occurrences - see Corner & Wall-Intersection Studs below.
  - **`per_stock_length`** - plates/rim board over a run (line `length_ft` or area `perimeter_ft`): `ceil(run / default_length) × multiplier`.
  - **`per_length`** - beams cut to the traced span: `multiplier` pieces, each the smallest stock length covering the span.
  - **`per_area_spacing`** - joists/rafters/trusses across an area: members spaced across one bbox dimension (`member_direction`), each as long as the other; `(ceil(run × 12 / spacing) + 1 + extra) × multiplier`. Rafters use `multiplier=2` (both roof planes) - fixed a seeded-data bug where this was 1, undercounting rafters by half; verified against the reference workbook's worked example (40ft building, 24" OC, 2 planes, 10% waste = 47 rafters).
  - **`per_area_coverage`** - sheathing/felt/wrap: `ceil(area_sqft / coverage_sqft) × multiplier` (e.g. 32 sqft per 4x8 sheet).
  - **`per_count`** - posts/hangers: `count × multiplier + extra`.
  - **`header`** - header sized to opening width plus `HEADER_BEARING_FT` (0.25 ft), rounded to stock; `multiplier` plies.
  - **`fixed_count`** - king/trimmer studs and other fixed-per-opening pieces: `multiplier + extra`.
  - **`per_box`** - fasteners and other box-sold materials estimated from a rate: `total_units = measurement (length_ft/area_sqft/count, whichever applies) × units_per_measurement`, then `MaterialProduct.boxes_needed(total_units) × multiplier`. Closes the "box conversion exists but isn't a rule kind" gap - seeded on the "2x6 Wall - 16 in OC" assembly as "Framing Nails" at 10 nails/linear ft, an explicitly-labeled rough placeholder (the reference workbook itself punts on the exact fastener rate: "estimate fasteners per connection, then round to boxes") - tune `units_per_measurement` via admin to match real practice.
- **Opening:** A window or door placed on/within a wall Trace, with width and height, used to calculate header size/length and trimmer/cripple stud counts (via its own `opening`-tool_type assembly) and to deduct its width from its host wall's own stud run (`estimating.calculations._attached_opening_width_ft`) - see `Trace.parent_wall` above.
- **LineItem** (`estimating.LineItem`): One computed or manually-added material quantity on an `Estimate` - material, role, quantity, waste factor, `category`, and `source` (`tool` / `manual`). Tool-generated lines carry a `trace` FK for traceability; `estimating.calculations.generate_line_items()` is idempotent per-trace (regenerating replaces only that trace's own lines) so it can never clobber a manual line, which structurally has no trace. `category` is denormalized (copied from `assembly.category` at generation time) rather than derived purely live, since `calculation_rule` is `SET_NULL` and manual lines have no rule/assembly at all - read via `Coalesce(calculation_rule__assembly__category, category)` wherever grouping needs to reflect a later assembly reclassification without regenerating every LineItem.

### Material List Output

The Estimate Detail page and CSV export group the material list by construction system, in the build order from `docs/Lumber Estimator Takeoff.docx` (Foundation & Sill → Floor System → Wall System → Openings → Stairs → Ceiling → Roof → Siding & Exterior Trim → Exterior Deck → Miscellaneous), instead of the earlier flat alphabetical-by-material listing. Both group order and item order within a group are drag-and-drop reorderable (SortableJS, vendored locally at `static/js/sortable.min.js` rather than CDN, per the codebase's move away from CDN-only assets) and persist as an **account-wide default** - `Account.category_order` (list of category keys) and `Account.item_order` (`{category_key: [role_string, ...]}`, matched case/whitespace-insensitively since the seed data has near-duplicate role strings like "Bottom Plate" vs "Bottom Plate (PT)"). Reordering the account default re-sorts every estimate the account has, past and future - it's a live preference, not a per-estimate snapshot. `estimating/views.py`'s `_category_order_for()`/`_item_rank()` compute the effective order (falling back to doc order / append-at-end for anything not yet in a saved list, so nothing silently disappears); `CategoryOrderUpdateView`/`ItemOrderUpdateView` persist drags (both wrapped in `select_for_update()` to avoid a same-account read-modify-write race); `ResetLayoutPreferencesView` clears both back to doc defaults. The CSV/"Order List" rollup (`_grouped_order_list`) still aggregates by material+dimension+length across an estimate for a supplier-ready quantity, but never merges across categories, and gets a `System` column. Explicitly out of scope: dragging an item into a *different* category (only within-category + whole-group reorder), and fuzzy-matching role strings beyond simple case/whitespace normalization.

The plan viewer (`templates/plans/viewer.html`) also shows a compact, read-only **live material list panel** to the right of the canvas (`#material-list-panel`), so a user can see quantities update without leaving the drawing view. It reuses `_grouped_order_list()` via a new `EstimateMaterialSummaryView` (`estimating:estimate-material-summary`, renders `templates/estimating/_material_summary.html`) - the same rollup as the Estimate Detail page and CSV, so the numbers can never disagree - and offers no reordering of its own (a "Full view →" link goes to the real Estimate Detail page for that). `viewer.js`'s `refreshMaterialList()` re-fetches that partial and swaps `#material-list-content`'s innerHTML on initial load and after every trace create/update/delete, giving the "live updates as materials are added" behavior without a full page reload. Since `Estimate` is per-Project (not per-PlanPage), the panel totals every page of the project, not just the one currently open - the panel copy says so explicitly ("all pages").

### Corner & Wall-Intersection Studs

Wall stud counts now account for two kinds of geometric junction between wall traces, on top of the plain `ceil(length_ft × 12 / spacing)` run: a **corner** (two wall ends meeting, or a polyline bending) and a **T-intersection** (one wall's end butting into another wall's span). `plans/wall_junctions.py::detect_wall_junctions(trace)` is the pure geometry function - `{'corner_count', 'partition_t_count', 'through_t_count'}` - reused by `estimating.calculations.generate_line_items()` (via `evaluate_rule()`'s `junctions` param) to add `corner_count × CalculationRule.corner_stud_count + partition_t_count × t_intersection_stud_count + through_t_count × t_backer_stud_count` on top of `PER_SPACING`'s existing static `extra`. At a T-intersection **both** walls get extra material: the partition (whose end butts in) gets its own allowance, and the through-wall (continuous, being butted into) gets a backer/nailer stud, since the partition needs something to nail into.

A key equivalence this is built around: drawing the same physical layout as two separate line traces meeting end-to-end vs. one polyline with a bend at that point must produce the same total extra-stud quantity ("the wall tool should work both with lines and polylines"). Two separate walls each independently detect the shared point and contribute one corner occurrence each; a polyline's own internal bend is therefore counted **twice** in `_internal_bend_count` - it stands in for both "a wall ending" and "a wall starting" at that point. `corner_stud_count` defaults to 1 (not 2) precisely because the occurrence count already carries that ×2 weighting for a bend - the constant is "studs per occurrence," not "studs per physical corner."

Cross-trace corner matching (`_shares_a_corner`) applies the same collinearity test used for polyline bends, so a straight wall arbitrarily split into two collinear trace segments is correctly **not** treated as a corner - only where two walls' directions genuinely diverge. It also matches against every vertex of the other wall, not just its overall endpoints, so a wall ending exactly on another polyline's internal bend is still detected (not invisible to both the corner and T checks). Per-endpoint corner/partition-T detection is a yes/no check (not summed per matching neighbor), so a 3+-way junction (e.g. a hallway wall on each side) isn't multiply counted - each of the *N* converging walls independently contributes its own single occurrence.

Since a `Trace`'s `geometry` is immutable after creation, a wall's junctions can only change when a new wall trace is created nearby or a neighboring one is deleted (never on a settings-only edit) - `plans/views.py::_regenerate_sibling_walls()` (cheaply pre-filtered via `wall_junctions.could_share_a_junction()` so adding one wall to a page with many others doesn't recompute all of them) is called from `TraceCreateView`/`TraceDeleteView` for line/polyline traces only, reusing the `_regenerate_wall_line_items()` helper already built for the opening-deduction feature.

**Migration note**: `estimating/migrations/0013_add_junction_stud_counts.py` gives every existing `PER_SPACING` rule non-zero junction defaults - broader than prior calc fixes, since it affects *every* wall assembly's next recalculation (for any reason), not just traces satisfying some new predicate. No data migration retroactively rewrites existing `LineItem`s, matching precedent (a fix only affects the next recalculation of a given trace).

Explicitly out of scope: the wall elevation preview (`plans/framing.py::build_wall_elevation`) doesn't visually draw corner/T-backer studs, only the calculated `LineItem` quantity changes; self-intersecting polylines aren't checked against themselves; two distinct partitions butting into the exact same point of a through-wall each still contribute their own separate `through_t_count` (not clustered); `JUNCTION_TOLERANCE_FT` (0.5 ft) is a hardcoded module constant, not user-configurable.

### Semantic Toolbar & Dynamic Opening Resolution

The viewer sidebar's raw geometry tools (Line, Area, Polyline, Count, Opening, Calibrate) are kept exactly as they were, but a row of **semantic construction tools** sits above them: Wall, Opening, and Beam each expand (Bootstrap dropdown) into variants, plus plain Joist/Column/Plate/Rim Board buttons. Picking a variant just activates the matching raw `tool_type` and narrows the assembly `<select>` to matching-tagged assemblies (`viewer.js::populateAssemblyOptions`'s `variantFilter` param) - there's no new Trace-level field for "which semantic tool drew this," the distinction lives entirely in three new `estimating.Assembly` fields. **Wall uses `tool_type='polyline'` (not `line`)** so a whole connected wall run - multiple corners/segments - can be drawn as one continuous click-each-corner action (finish with Enter, double-click, or Escape) instead of one 2-point trace per segment; this needed no backend change at all, since an open (non-`closed`) polyline was already treated identically to a `line` wall everywhere that matters (`plans/framing.py`'s elevation/corner-stud engine, `estimating/calculations.py`'s `PER_SPACING` formula, and `_resolve_assembly`'s line/area compatibility check) - only `viewer.js` needed to learn to collect/render the same stud-spacing/wall-height/plate-count/layer settings for a Wall-flavored polyline as it already does for the raw Line tool (tracked via a module-level `activeSemanticKey` for drawing, and by checking a selected trace's own `closed` flag - `!closed` means wall-like - for editing an existing one in the inspector). The raw Line tool (still labeled "Draw Wall" on its own button, `data-tool="line"`) remains available for a single straight one-shot wall segment.

- **`wall_subtype`** (`exterior` / `interior_bearing` / `interior_non_bearing`) - dual-purpose: tags a WALL assembly with the wall type it represents, *and* tags an OPENING assembly with the wall type its header/king/jack sizing is designed for.
- **`opening_kind`** (`window` / `door`) - opening assemblies only; matched against the drawn opening's own `settings.opening_type`.
- **`beam_type`** (`flush` / `dropped`) - classification only so far, not yet reflected in different calculated hardware (e.g. joist hangers for a flush beam) - a real, separate follow-up.

**Dynamic opening resolution** (the actual point of the feature, confirmed with the user over building six separate window/door-per-wall-type tools): when an opening trace has a `parent_wall` set, `plans/views.py::_resolve_opening_assembly()` automatically matches an Assembly by `(opening_kind, parent_wall.assembly.wall_subtype)`, **overriding** whatever `assembly_id` the client sent - a manual pick can never silently drift out of sync with whichever wall the opening is actually attached to. Falls back to the plain explicit `_resolve_assembly()` pick whenever it can't auto-resolve (no parent_wall yet, the host wall isn't itself classified, or nothing's tagged for that pair) - it never blocks trace creation. `_peek_parent_wall()` is a quiet, error-swallowing lookup used only to feed this resolver; the real, validating `_resolve_parent_wall()` call still runs at its original point in each view, so invalid-`parent_wall_id` error precedence is unchanged from before this feature. Detaching a wall (via the inspector, sending `parent_wall_id: null`) clears the assembly too, since `_resolve_assembly(account, None, ...)` already returns `None` for a falsy id - the frontend cooperates by clearing its own assembly `<select>` on detach so it doesn't resend a stale auto-resolved id as if it were a fresh manual pick.

**Known v1 limitation**: resolution keys only on `wall_subtype`, not stud width/dimension - fine for the current one-width-per-subtype seed catalog; would need real design if an account ever has two differently-sized walls sharing one subtype. A `UniqueConstraint` pair (mirroring the existing global/per-account dual-constraint pattern already on `Assembly` for `name`) prevents two assemblies from ever ambiguously sharing one `(opening_kind, wall_subtype)` pair, closing a nondeterminism risk an independent design review caught before this shipped.

**Seed data**: only `2x6 Exterior Wall on Slab - 16 in OC` was tagged onto *existing* data (`wall_subtype=exterior` - unambiguous from its name). `2x4 Wall - 16 in OC`, `2x6 Wall - 16 in OC`, and `LVL Beam 1-3/4x11-7/8 (Double)` are genuinely ambiguous (bearing vs. non-bearing, flush vs. dropped - nothing in their name/description says which) and were deliberately left unclassified rather than guessed at, since a wrong guess would've silently mis-tagged real accounts' existing walls/beams - `estimating/migrations/0015_seed_semantic_tool_assemblies.py` instead adds new, clearly-scoped assemblies for the tags that needed real data (`2x6 Interior Bearing Wall`, `2x4 Interior Non-Bearing Wall`, two new LVL beam variants, and six new Opening assemblies covering window/door × all three wall subtypes). The original `Window/Door Opening - 2x10 Header (2x6 Wall)` stays untouched and unclassified (can't be backfilled to one `opening_kind` - it's literally named for both) with its description flagged "(Legacy: ...)" for UI clarity in the now-larger flat fallback list.
- **MaterialProduct** (`catalog.MaterialProduct`): A catalog entry such as "2x6 SPF #2" or "Deck Screws 3in", with an auto-generated `slug` and an `input_type` (`ft` / `box` / `each`) that determines what other fields apply (stock lengths for `ft`, `quantity_per_box` for `box`). Global when `account` is blank (staff-managed via Django admin); an Account can also have its own private custom materials, isolated from other accounts (`MaterialProduct.objects.visible_to(account)`).
- **MaterialLength (Material Database):** Defines the stock lengths an `input_type="ft"` MaterialProduct is available in (e.g., 2x10 SPF #2 in 8'–24', 2' increments). `length_ft` is a `DecimalField(max_digits=8, decimal_places=5)` (not whole feet) specifically so precut stud lengths - 92-5/8 in and 104-5/8 in, the standard precuts for 8'-1-1/8" and 9'-1-1/8" wall heights - can be stored exactly (92.625/12 = 7.71875 ft, 104.625/12 = 8.71875 ft, both exact at 5 decimal places; `catalog/migrations/0006_seed_precut_stud_lengths.py` seeds both onto the global `2x4 SPF #2` and `2x6 SPF #2` products). `MaterialProduct.stock_length_for(required_ft)` returns the smallest in-stock length covering a one-piece requirement (e.g. a joist); `MaterialProduct.default_length_ft` returns the `is_default`-flagged length used for total-length ÷ default-length calculations (e.g. how many plate pieces cover a wall run). The program can only ever use lengths that appear here. A wall's stud `LineItem.length_ft` (the *cut* length, not the count) is resolved by `evaluate_rule()`'s `PER_SPACING` branch from the trace's `wall_height_in` setting minus `plans.framing.STANDARD_PLATE_ALLOWANCE_IN` (4.5", i.e. a double top + single bottom plate) - `wall_height_in` is the overall assembled wall height, not the stud's own length, and this constant is shared with (imported by) `estimating/calculations.py` from `plans/framing.py` so the elevation preview and the generated material list can never disagree about what a wall's studs are cut to. The wall-height input (`viewer.js`) reads it with `parseFloat`, not `parseInt`, and has `step="0.125"` - both needed for a fractional wall height like 97.125 to actually make it into `Trace.settings` instead of being silently truncated to 97.
- **PriceEntry (optional feature):** Per-account unit pricing. Pricing source is undetermined; treat all pricing as user-supplied and optional.

## Key Business Rules

- The material list is the product. Every feature must work with zero prices entered.
- Board feet = (nominal thickness x nominal width x length in feet) / 12.
- Waste factor is applied per line item (default 10%, configurable).
- Quantities round up to whole pieces; currency (when present) uses Decimal and rounds half-up to cents.
- If prices exist, they are snapshotted onto LineItems when applied, so historical estimates don't shift.
- Manual line items and Tool-generated line items coexist on the same Estimate; Tool recalculation must never clobber manual lines.
- All quantity calculations follow standard framing techniques as the baseline, parameterized by JobSettings, implemented as fixed/parameterized `CalculationRule.formula_kind`s (not a free-form formula language) in `estimating/calculations.py`:
  - **`per_spacing`** (implemented) - count = ceil(length_ft × 12 ÷ spacing_in) + `extra`. Used for studs; spacing is read from the Trace's `settings['stud_spacing_in']` snapshot. `extra` covers the "+1 end stud" / corner allowance as a configurable constant, not geometry-aware corner detection.
  - **`per_stock_length`** (implemented) - count = ceil(length_ft ÷ `material.default_length_ft`) × `multiplier`. Used for plates (e.g. `multiplier=2` for a double top plate) and other run-length materials (rim board, band board) that are built up from multiple stock pieces.
  - Waste factor (`CalculationRule.waste_factor` / `LineItem.waste_factor`) is applied uniformly after the raw formula result and rounded up: `ceil(raw * (1 + waste_factor))`.
  - **Headers:** `header` adds 3 inches of total bearing to the traced opening width and rounds each ply to the smallest available stock length. `fixed_count` supplies king/trimmer studs, while `per_spacing` supplies a baseline cripple count. Opening height and wall association are not modeled yet, so cripple lengths and subtraction from the parent wall remain future work.
  - **Line-length-derived materials** use `per_length` for beams and `per_area_spacing` for joists, rafters, and trusses. Lumber is rounded up to the smallest available stock length via `MaterialProduct.stock_length_for()`; unit-sold members such as custom trusses retain no stock length.
  - **Unit-sold materials** use `per_area_coverage` for sheets and rolls, `per_count` for counted hardware/posts, `fixed_count` for fixed components, and `per_box` (via `MaterialProduct.boxes_needed()`) for fasteners and other box-sold materials estimated from a per-unit rate.

## Material Library & Database

- Base dimensional lumber (**2x4, 2x6, 2x8, 2x10, 2x12, all SPF #2**) is seeded globally via `catalog/migrations/0002_seed_dimensional_lumber.py` (fixed up to `input_type="ft"` in `0003`). `catalog/migrations/0004_seed_house_framing_materials.py` adds the rest of a house-framing catalog: PT plates (2x4/2x6 PT), PT posts (4x4/6x6), LVL beams (1-3/4x9-1/2 and 1-3/4x11-7/8), sheet goods (7/16 OSB wall sheathing, 1/2 CDX roof sheathing, 3/4 T&G subfloor), rolls (house wrap, #30 felt, sill seal), per-unit hardware (roof trusses as a custom-order `each`, 2x10 joist hangers), and boxed fasteners (framing + sheathing nails, 2500/box). Additional species/grades/dimensions are added incrementally via Django admin (`catalog.MaterialProductAdmin`, staff-only for now).
- **Full catalog + categories (added).** `MaterialProduct` now has a `category` field (`MaterialProduct.Category` TextChoices: Dimensional Lumber, Pressure-Treated, Studs & Precut, Boards & Trim, Engineered Lumber, Sheathing & Panels, Subfloor & Underlayment, Roofing, Housewrap & Weather Barrier, Connectors & Hardware, Fasteners & Adhesive, Decking & Railing, Concrete & Miscellaneous, Uncategorized) added in `catalog/migrations/0007_materialproduct_category.py`. This is a catalog grouping by material *type*, distinct from a `LineItem`'s construction-system category. `catalog/migrations/0008_seed_full_catalog.py` backfills categories onto the 21 pre-existing global products and seeds a comprehensive alphabetized catalog (now ~103 global products) across the full 1x board range, the rest of the PT range, engineered lumber (LVL/LSL/PSL/glulam/I-joists), the sheathing/panel range (OSB/CDX/plywood/ZIP/drywall), subfloor/underlayment, roofing, weather barrier, connectors/hardware, fasteners/adhesive, decking/railing, and concrete/misc. The seed is idempotent by name; `ft` products get `MaterialLength` rows with a marked default. Both migrations are reversible.
- Every `MaterialProduct` has an `input_type` (`ft` / `box` / `each`) that drives which other fields are relevant - enforced in `MaterialProduct.clean()` and toggled dynamically in the admin form via `catalog/static/catalog/admin/material_product.js`:
  - **ft**: stock lengths live in `MaterialLength`; `MaterialProduct.stock_length_for(required_ft)` returns the smallest in-stock length that covers a requirement.
  - **box**: `quantity_per_box` (e.g. 100 screws/box); `MaterialProduct.boxes_needed(quantity)` rounds up to whole boxes.
  - **each**: no extra fields.
- Catalog is global by default (`account=None`, staff-managed) plus per-account custom materials (`account` set), isolated from other accounts. Slug uniqueness is scoped accordingly - two accounts can each have their own "Custom Bracket".
- Per-use-case default length overrides (e.g., rim board at 16' regardless of a product's general default) are not yet modeled - still an open question below.

## Exports

- **Built.** The Estimate detail page (`estimating.EstimateDetailView`) shows two tables: an **Order List** (`_grouped_order_list()` groups line items by product + piece length with `Sum('quantity')`, the supplier-ready view) and a **Detail** table (per-line role/material/length/qty/waste/source with a Remove button on manual lines). A print stylesheet hides everything but the order list for a clean hard copy.
- **CSV** export at `estimating:estimate-csv` (`estimates/<pk>/export.csv`) streams the same grouped order list with a `Content-Disposition` attachment filename, so a lumber yard can quote directly from it.
- **Manual lines** (`ManualLineItemForm` + `ManualLineItemCreateView`/`ManualLineItemDeleteView`) coexist with tool-generated lines; delete is restricted to `source="manual"` lines (tool lines are owned by their trace and would reappear on regeneration).
- Prices and totals appear on exports only if the estimate has pricing (still optional and undetermined).
- Formats beyond CSV + printable view (PDF, Excel, email-to-supplier) remain open.

## Billing

- Stripe powers Account subscriptions.
- Subscription tiers, pricing, and feature gating are not yet defined - build the Account/subscription model to support tiered limits later rather than hardcoding a single tier.

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
├── estimating/           # Assembly, CalculationRule, LineItem; calculations.py engine (exports still TBD)
├── templates/
├── static/
├── media/
├── logs/
├── requirements.txt
├── pyproject.toml        # pytest + ruff config
├── Dockerfile / docker-compose.yml
└── Procfile              # Render/gunicorn process command
```

New app boundaries above are a working proposal, not settled - adjust as the plan-tracing and Tool architecture solidifies.

## Conventions

- Calculation and Tool-expansion logic lives in plain Python modules (`estimating/calculations.py`), not in views or models, so it's unit-testable without the ORM. Simple derived-data lookups (e.g. `MaterialProduct.stock_length_for()`, `.default_length_ft`) are the one exception, living as model methods/properties per the fat-model convention below - the line is: single-field lookups on the model, multi-step assembly/formula orchestration in the calc module.
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

- **Recalibration drift:** recalibrating a `PlanPage` does not retroactively recompute already-drawn traces' `LineItem`s - only a future create/update on a given `Trace` regenerates its own lines. A page recalibrated after walls are already drawn will leave those walls' quantities computed against the old (wrong) scale until each is re-saved.
- Per-stud/member cut length is now set from the `wall_height_in` (line) or member run (area/beam/header) snapshot, so `length_ft` is populated for those. It's still null for count/coverage lines by design.
- Estimate versioning/selection: one `Estimate` is auto-created per `Project` and used implicitly (`project.estimates.order_by('created_at').first()`); no UI to create a new version or choose between multiple.
- **Resolved:** Opening-to-wall attachment is now explicit, not proximity-based. `Trace.parent_wall` (a nullable self-FK, `related_name='attached_openings'`) is set by the user via the inspector panel's "Attached to wall" dropdown (only shown for `tool_type=opening`), validated server-side (`plans.views._resolve_parent_wall`: only opening traces may set it, target must be `line`/`polyline`, same `PlanPage`, same account). `plans.framing._attached_openings()` queries `trace.attached_openings.all()` directly — no more distance/tolerance gate; projection math is still used, but only to compute *where along the wall* an attached opening sits, clamped to the nearest point on the wall path rather than rejected. Existing plans were backfilled (`plans/migrations/0006_backfill_opening_parent_wall.py`, proximity heuristic ported inline since migrations can't import current app code) so pre-existing wall elevations didn't visually change. Deleting a wall sets its openings' `parent_wall` to null (`SET_NULL`) rather than deleting them.
- **Resolved:** Attached openings now do subtract from a wall's own stud count. `estimating.calculations._attached_opening_width_ft(trace)` sums the real-world width of every trace in `wall.attached_openings.all()` and `evaluate_rule()`'s `PER_SPACING` branch subtracts that total from the wall's length before computing stud count (clamped at 0) - the studs that would otherwise run through a window/door rough opening are replaced by that opening's own king/jack/cripple studs (a separate `LineItem` set, generated from the opening's own assembly). Deliberately **not** touched: `PER_STOCK_LENGTH` (plates) - top plates run continuously over openings in standard framing, and the reference workbook's Wall Takeoff formulas don't discount plates for openings either, so extending the deduction there wasn't a verified rule, just an invented one. `plans.views._regenerate_wall_line_items()` re-runs the wall's own `generate_line_items()` whenever an opening is attached, detached, or reattached to a different wall (`TraceCreateView`, `TraceUpdateView`, `TraceDeleteView`), so the wall's `LineItem`s stay in sync without the user having to manually re-save the wall trace itself.
- `per_area_spacing` uses the traced rectangle's bounding box, so it assumes roughly rectangular, axis-aligned floors/roofs; angled or L-shaped areas over-count against the bbox. Sloped-roof runs use plan (footprint) length, not true rafter length up the slope.
- Trace editing is create + inspector-edit (material/assembly/settings) + delete; no drag-to-edit vertices after drawing.
- PDF rasterization (`plans.services.rasterize_plan`) runs synchronously inside the upload request - fine for small plans, but will need to move to a background job (Celery/RQ, no such infra exists yet) for large multi-page PDFs.
- Plan/media file storage: currently Django's default FileSystemStorage under `MEDIA_ROOT`. Production needs a real backend (S3-compatible bucket, Render disk, Cloudinary) - not yet chosen.
- Recalculation behavior: `generate_line_items()` already replaces a trace's own previously-generated lines on regeneration (never touches manual lines), but there's no trigger yet for *when* that should re-run (e.g. on `JobSettings` change) or whether a user should be warned before a regeneration changes quantities they'd already reviewed.
- Per-use-case default length overrides in the Material Database (e.g., rim board at 16' vs. a product's general default) - not yet modeled.
- Full list of standard framing rules/tables to encode per Tool (wall, floor joist, beam, rafter, truss, header) - need an engineering reference or source to encode against.
- Stripe subscription tiers, pricing, and feature gating - TBD.
- Export formats beyond the built printable view + CSV: PDF? Excel? Email directly to a supplier?
- Free vs paid tiers, estimate limits, or fully free at launch?

## Intelligent Wall Assembly Viewer - Phase 2

- The plan trace remains the control geometry, but a line trace can now behave as a lightweight wall object with richer wall settings captured in `Trace.settings`:
  - `stud_spacing_in`
  - `wall_height_in`
  - `top_plate_count`
  - `bottom_plate_count`
  - layer visibility flags such as `interior_drywall`, `exterior_sheathing`, `house_wrap`, and `siding`
- Opening traces now capture more than just length:
  - `opening_type` (`window` or `door`)
  - `sill_height_in`
  - `rough_height_in`
  - `header_depth_in`
  - `stud_spacing_in` for cripples
- `plans/framing.py` remains procedural. It does not persist studs, plates, headers, or layers. It generates:
  - elevation framing members
  - attached openings projected onto the selected wall trace
  - conceptual wall layers for a future material/3D view
  - a grouped preview cut list
- The wall modal now has three conceptual views:
  - **Framing elevation**: generated plates, studs, kings, jacks, headers, sill, and cripples.
  - **Layers / 3D**: an intentionally simple pseudo-3D/layer view showing drywall/framing/sheathing/WRB/siding as separable wall layers.
  - **Cut list**: generated member role/quantity/cut-length preview.
- Generated members are clickable in the modal for inspection. This is intentionally read-only right now. The next real data-model step should be a `WallMemberOverride`/`TraceMemberOverride` concept that stores only user deviations from the generated model, such as moved/deleted/locked/custom studs, custom headers, added blocking, and material substitutions.
- Future tool naming should move away from primitive geometry names in the user-facing UI. Internally the geometry can still be `line`, `polyline`, `area`, `count`, and `opening`, but the left toolbar should eventually expose construction objects such as:
  - Draw Wall
  - Draw Opening
  - Draw Joist Bay
  - Draw Beam
  - Draw Rafter / Truss Run
  - Count Posts / Hardware
- Do not convert the plan viewer into full BIM all at once. Keep the workflow simple: draw control geometry, assign an assembly/material object, generate a wall/joist/beam model from settings, and persist only manual overrides.


## Intelligent Wall Assembly Editing - Phase 3

The wall assembly viewer now supports lightweight member-level framing overrides while keeping the wall procedural. Generated studs, plates, headers, kings, jacks, and cripples are still rebuilt from the wall trace, opening traces, and assembly settings. Manual edits are stored compactly in `Trace.settings.wall_member_overrides` instead of creating database rows for every generated member.

Override shape:

```json
{
  "wall_member_overrides": {
    "edited": {
      "stud_4": {"x": 63.5, "y": 1.5, "width": 1.5, "height": 91.5, "role": "Stud"}
    },
    "deleted": ["stud_5"],
    "added": [
      {"id": "custom_123", "role": "Custom stud/blocking", "x": 72, "y": 24, "width": 1.5, "height": 36}
    ]
  }
}
```

Design rules:

- Do not persist every generated framing member as its own model yet.
- Persist only exceptions: edited generated members, deleted generated members, and custom added members.
- Recalculate cut lists from the effective member list after overrides are applied.
- Keep the plan line as the control geometry for the wall. The elevation/3D views are alternate editors for that same wall object.
- Future tools should move from generic `line` and `shape` names toward material/assembly tools such as Draw Wall, Draw Joist, Draw Beam, Draw Opening, Draw Blocking, etc.

Current UI behavior:

- Select a wall line and open Wall Elevation / Framing.
- Click a generated member to select it.
- Blue grips allow quick 1-inch nudges/extensions.
- The member form allows exact x/y/width/height/role edits.
- Users can add a custom member based on the selected member or delete generated/custom members.
- The 3D view is a pseudo-3D framing massing preview with wood-like depth, intended as a stepping stone toward a richer Three.js/BIM view.

## Intelligent Wall Assembly Editing - Phase 4

The wall assembly modal has moved from form-first editing to direct manipulation.

Current UI behavior:

- Wall framing edits update immediately on screen; users no longer need to press a member-specific save button before seeing changes.
- Member override persistence is debounced and automatic. The modal stores edits back into `Trace.settings.wall_member_overrides` after drag, resize, draw, delete, or field changes.
- The selected member can be moved by dragging the member body in the elevation SVG.
- The selected member can be stretched or shortened by dragging blue grips at the top, bottom, left, and right edges.
- Users can draw new framing members directly in the elevation view:
  - **Draw vertical member** creates a 1.5-inch-wide custom stud by click-dragging vertically.
  - **Draw blocking / custom member** creates a rectangular custom member by click-dragging a box.
- Deleting a generated or custom member now updates the wall immediately and auto-saves the override; it should not require saving the member first.
- Numeric x/y/width/height/role fields remain available for exact input, but they now apply live.
- The cut list and pseudo-3D wall preview are rebuilt from the effective member list after every edit.
- The 3D preview is still SVG-based, but it now renders wall members as individual board-like cuboids with front/top/side faces, shadows, basic wood grain, and opening overlays. This is still a lightweight preview, not a structural/photorealistic renderer.

Implementation notes:

- Keep direct member editing client-side first for responsiveness. Persist only the compact override payload after edits.
- Continue avoiding database rows for generated studs/plates/headers unless a future feature requires querying individual members server-side.
- The next usability step should be true snap behavior: snap moved members to stud spacing, opening edges, plate faces, and neighboring member edges. Snapping should be optional/toggleable so users can still make nonstandard field conditions.
- Future 3D work should eventually move to a real 3D scene renderer, but the SVG cuboid preview is acceptable while the framing model and override workflow are still evolving.

## UI / Design System (redesigned)

The interface was rebuilt around a premium, STACK-style app shell. Visual language lives entirely in `static/css/main.css` (rewritten as a token-driven design system: deep-navy rail, one confident blue primary `#2563eb`, a warm accent `#f97316` used sparingly, slate neutrals, Inter font, shadow/radius tokens).

- **App shell** (`templates/base.html`): authenticated users get a persistent dark left rail (`partials/_sidebar.html`, `.app-rail`: brand mark, Workspace/Get-started nav sections, active-state indicator, log-out foot) plus a slim sticky topbar (`partials/_navbar.html`, `.app-topbar`: mobile menu toggle, `topbar_title` block, user avatar/email). Unauthenticated users (login, password reset) get a clean centered `is-public` layout with no chrome. The old top-navbar + in-content quick-links sidebar are gone; the rail is the single global nav.
- **Blocks**: `topbar_title` (per-page topbar label), `main_class` (set to `main-full-bleed` by the plan viewer so the canvas goes edge-to-edge), `content`, `extra_css`, `extra_js`. The viewer's legacy `sidebar`/`layout_shell_class` overrides are now harmless no-ops.
- **Mobile rail**: `static/js/main.js` toggles `body.rail-open` (off-canvas rail + scrim, Escape/scrim-click to close).
- **Reusable components** (all in `main.css`): `.page-head`/`.page-title`/`.page-subtitle`, buttons (`.btn-primary`/`.btn-outline-primary`/`.btn-accent`), `.card`, `.stat-card`, `.project-card`, `.tag`/`.pill`, `.data-table`, `.messages`, `.auth-card`. Dashboard, project detail, and estimate detail headers use `.page-head`.

## Library (redesigned as a catalog browser)

`estimating.LibraryView` + `templates/estimating/library.html` are now a STACK-style tabbed catalog:

- Three tabs with live counts: **Materials**, **Assemblies**, **Formulas**.
- **Materials** are grouped by `MaterialProduct.category` (category groups sorted by label) and **alphabetized within each group**, rendered as cards showing species/grade/dimension and an input-type tag (stock lengths / N-per-box / each). Category filter chips narrow the view.
- **Assemblies** are grouped by construction-system `Assembly.category`, alphabetized within, each card showing tool type, wall subtype, description, and its rules (role + material + formula/kind).
- **Formulas** render in a data table.
- A single search box filters the active tab client-side (materials by name, assemblies by name/description, formulas by name), with per-tab "no results" states. All logic is vanilla JS in the template; no build step.
- `LibraryView.get_context_data` builds `material_groups`/`material_count`, `assembly_groups`/`assembly_count`, and alphabetized `formulas` using `itertools.groupby` over account-visible querysets.

## System Assemblies (every construction system now has a takeoff path)

`estimating/migrations/0016_seed_system_assemblies.py` seeds ~26 new global assemblies so every `Assembly.Category` has at least one prebuilt takeoff, filling the systems that were previously empty (Foundation & Sill, Stairs, Ceiling, Siding & Exterior Trim, Exterior Deck, Miscellaneous) and rounding out Floor and Roof. Total global assemblies went from 21 to 47. Each sets `category` directly (copied onto every generated `LineItem`), and each uses the correct `tool_type` for its geometry and a `formula_kind` that matches the material's `input_type`:

- **Foundation & Sill**: Sill Plate (2x6 PT, `per_stock_length`), Anchor Bolts (count).
- **Floor System** (additions): Floor Beam - Dropped (double LVL, `per_length`), Subfloor + Adhesive (area coverage).
- **Stairs**: Stair Stringers per flight (count x3), Stair Landing Framing (area joists + sheathing).
- **Ceiling**: Ceiling Joists 16 OC (area), Ceiling Strapping 16 OC (area), Ceiling Beam - Dropped (double LVL).
- **Roof** (additions): Asphalt Shingle Roofing (shingle bundles + #15 felt, area coverage), Ridge Board (line), Roof Edge - Drip + Sub-Fascia (line), Collar Ties (count), Hurricane Ties (count).
- **Siding & Exterior Trim**: House Wrap (area coverage 900), Fascia & Frieze Trim (line), Corner Trim (line x2).
- **Exterior Deck**: Deck Joists 16 OC PT (area), Deck Beam - Dropped (double 2x10 PT), Deck Ledger (line), Decking 5/4x6 PT (area coverage), Deck Posts 6x6 PT (count), Deck Footings Sonotube (count), Deck Railing (count).
- **Miscellaneous**: Bulkhead (count), Blocking 2x6 (line).

Every rule was validated against the calc engine with realistic measurements (zero failures). The one guardrail worth knowing: single-piece members (`per_length` beams, `per_area_spacing` joists/strapping) raise if the required span exceeds the material's largest stock length, since no single stock piece can cover it - use a longer-stock material or split the member. The seed is idempotent by (name, tool_type) and reversible.

## Spliced members + siding (added)

Two follow-ups closed the gaps the system-assembly seed left open: over-length members that used to raise, and a siding field that could only price wrap and trim.

**Spliced formula kinds.** `CalculationRule.FormulaKind` gained `PER_LENGTH_SPLICED` and `PER_AREA_SPACING_SPLICED` (the field widened to `max_length=30`; migration `estimating/0017`). They mirror `per_length` / `per_area_spacing` but build a member longer than the material's longest stock by splicing full-length pieces end to end instead of raising. Backed by two `MaterialProduct` helpers (`catalog/models.py`): `max_length_ft` (longest stock) and `pieces_for_length(required_ft)` which returns `(1, smallest covering length)` when it fits and `(ceil(required / max_stock), max_stock)` when it must be spliced. The engine (`estimating/calculations.py`) adds a `_spliced_pieces()` helper and the two kind branches: `per_length_spliced` returns `multiplier * pieces` (plies x spliced pieces); `per_area_spacing_spliced` returns `member_count * pieces`. Splice laps are not modeled; cover them with `waste_factor`. The plain `per_length` / `per_area_spacing` kinds keep their over-length guardrail unchanged, so existing assemblies behave identically. Seeded demo: `Built-Up Beam - Triple 2x12 (Spliced)` (line, `per_length_spliced` x3), which now handles a 40 ft span (7 pieces at 24 ft stock) instead of erroring. Tests: `estimating/test_calculations.py::SplicedFormulaTests`, `catalog/test_material_product.py::PiecesForLengthTests`.

**Siding field materials.** New `MaterialProduct.Category.SIDING` ("Siding & Exterior Finish"; `catalog/0009` alters choices). `catalog/migrations/0010_seed_siding_materials.py` seeds five `each` materials priced by the square (100 sqft): Vinyl, Clapboard, Fiber Cement Lap, Cedar Shingle, Board & Batten. `estimating/migrations/0018_seed_siding_and_spliced_assemblies.py` seeds siding coverage assemblies (`per_area_coverage`, `coverage_sqft=100`, waste 10-15%): `Vinyl Siding`, `Clapboard Siding`, `Fiber Cement Lap Siding`, `Cedar Shingle Siding`, plus a combined `Vinyl Siding + House Wrap` wall-skin assembly. Coverage lives on the rule (like sheet goods), so any square-priced siding works at any exposure by tuning `coverage_sqft`. Global catalog is now ~108 products; global assemblies ~53. All migrations idempotent and reversible.

**Repo hygiene.** Removed a batch of Dropbox "conflicted copy" duplicate files (models, views, tests, viewer.js/html) that had been shipping in the tree; pytest was collecting the duplicate `test_*` copies, which is why the count looked inflated. True suite size is 254 tests + 30 subtests, all passing.

## Default assemblies (fewer clicks to a takeoff)

Picking a semantic tool in the plan viewer now auto-loads a working assembly, so drawing produces a material list without opening the Assembly dropdown. `Assembly.is_default` (BooleanField, migration `estimating/0019`) marks one default per tool-variant group; `estimating/migrations/0020_seed_default_assemblies.py` sets nine: one per wall subtype, one per beam type, one per opening kind (fallback, since openings usually auto-resolve from their wall), one floor-joist default for the Joist tool, and one count default for the Column tool.

- The viewer serializes `is_default` in `assemblies_data` (`plans/views.py`), and `populateAssemblyOptions` in `plans/static/plans/viewer.js` gained a `preferDefault` argument. When a semantic tool is active (`activeSemanticKey` set), it selects the single default within that tool's filtered candidate set. If a set has more than one default (the raw Line tool sees all wall and beam defaults at once) it stays on "none" rather than guess, so raw tools keep their explicit behavior.
- Seeding invariant, guarded by `estimating/test_semantic_assemblies.py::DefaultAssemblyTests`: every semantic tool's filtered candidate set contains exactly one default (wall subtypes, beam types, opening kinds, the floor/ceiling/roof joist set, and the count set), while the whole line tool_type intentionally has several. `plans/test_traces.py` asserts the viewer payload carries `is_default`.

Suite is now 261 tests + 30 subtests, all passing.

## Tool memory (repeated traces never re-prompt)

The plan viewer now remembers the last-used settings, assembly, material tag, and color for each tool and variant, so drawing many walls (or joists, openings, columns) in a row does not re-prompt. All of this lives in `plans/static/plans/viewer.js`; no backend change.

- Storage mirrors the existing zoom pattern: `sessionStorage`, scoped per plan page and per tool-variant. `toolMemoryKey(tool, variantFilter, semanticKey)` builds keys like `plan-viewer-tool:<pageId>:polyline|wall:exterior`, `...:area|cat:floor_system,ceiling,roof`, `...:count|s:column`, so an exterior wall, a joist, and a column each keep separate memory, distinct from the raw tools (`line|`, `area|`).
- `saveToolMemory` snapshots `collectSettings(tool, '')` plus the assembly/material/color selects. It fires on two events: after a trace is successfully created (the "last used" moment), and on any `change` in the tool-settings panel (so a picked assembly or spacing sticks even if the user switches tools before drawing the first trace).
- `restoreToolMemory` runs at the end of `configureToolPanel`, after `populateAssemblyOptions`. That ordering means a remembered assembly intentionally overrides the auto-selected default from the previous pass, while a first-time tool with no memory still gets that default. `applyToolSettings` is the inverse of `collectSettings`, writing remembered values back into the inputs; it only applies keys that are present, so a remembered null never blanks a defaulted field, and programmatic writes do not refire the change listener.
- Safety: `optionExists` guards the assembly/material restore, so a remembered id that is not valid for the current variant is skipped rather than forced. `createTrace` snapshots the tool/variant before the async POST resolves, so memory is saved against the tool that was actually drawn even if the user has since switched.

Suite unchanged at 261 tests + 30 subtests, all passing; `node --check` clean on viewer.js.

## Start Takeoff + keyboard shortcuts (dashboard to drawing in one click)

**Start Takeoff.** `projects.StartTakeoffView` at `projects/<pk>/takeoff/` (name `projects:start-takeoff`) is a one-click entry into tracing, surfaced as the accent button at the top of the project detail page. Redirect priority: (1) the page of the project's most recent trace (resume where you left off, ordered by `Trace.created_at`), (2) the first page of the newest plan (`-plan__uploaded_at, page_number`), (3) back to the project detail with an "Upload a plan first" message. Account-scoped via `Project.objects.for_account`; foreign projects 404. Tests: `projects/test_start_takeoff.py` (all three redirect cases, tenancy, and button render).

**Tool shortcuts.** Plain single keys arm viewer tools (`plans/static/plans/viewer.js`, extending the existing keydown handler): W walls, O openings, B beams (these three cycle their variants on repeat press: W exterior -> interior bearing -> interior non-bearing -> exterior...), J joist, C column, P plate, R rim board, H hand. Repeat press of a single-variant key toggles off, matching the buttons. Implementation simulates clicks on the real sidebar buttons (`SHORTCUT_CYCLES` / `SHORTCUT_SINGLES` selector maps), so variant filters, default assemblies, and tool memory apply exactly as if clicked. Guards: never while typing (`isTypingTarget`: input/textarea/select/contentEditable) and never with Ctrl/Meta/Alt held, so browser shortcuts stay intact; Escape/Enter behavior unchanged. Button tooltips advertise the keys ("Wall (W)" etc. in `templates/plans/viewer.html`).

Suite: 266 tests + 30 subtests, all passing.

## Page switcher strip + calibration guard rail

**Page strip.** The viewer now shows a horizontal thumbnail strip of every page in the project (across all its plans, oldest plan first), so hopping floors never requires going back through project detail. `PlanViewerView` adds `project_pages` to context (`plan__project` filter, ordered `plan__uploaded_at, page_number`); the strip renders in `templates/plans/viewer.html` only when the project has more than one page. The current page is highlighted (`is-current`), uncalibrated pages carry an accent dot (`page-strip-dot`), thumbnails lazy-load, and styles live in `static/css/main.css` under "page switcher strip". Tests in `plans/test_traces.py`: strip spans plans, excludes foreign accounts, highlights current, hidden for single-page projects.

**Calibration guard.** Arming a measuring tool (`line`, `area`, `polyline`, `opening`; the `MEASURING_TOOLS` list in `plans/static/plans/viewer.js`) on an uncalibrated page no longer lets the user draw into a server error. `activateTool` intercepts the request, stores it as `pendingToolActivation`, and redirects to the calibrate tool with a hint naming the tool that will re-arm ("Set it below and the Exterior Wall tool will arm automatically"). Both calibration flows (two-point line and printed-scale preset) funnel through `onCalibrated()`, which re-arms the stored request with its original variant, source button, and settings fields; since `isCalibrated` is then true, the re-activation passes straight through the guard. Every other activation (tool switch, Escape, deactivate) clears the pending request, so a stale re-arm can never fire later. Count, hand, and calibrate itself are exempt since they need no scale.

Suite: 268 tests + 30 subtests, all passing.

## Live summary bar + inline page rename

**Summary bar.** The viewer's material list panel now opens with three headline numbers that update after every trace: total pieces, order lines, and framing board feet. `_summary_totals(order_list)` in `estimating/views.py` rolls up the same `_grouped_order_list()` rows the panel already shows, so the numbers can never disagree with the list beneath them. Framing BF uses the nominal-dimension convention, BF = thickness_in x width_in x length_ft / 12 per piece, and counts only rows whose `nominal_dimension` matches plain `NxM` (the `_DIMENSIONAL_RE` regex: 2x6, 1.75x11.875) and that carry a piece length; sheet goods (three-part dims), rolls, boxes, and per-square siding are excluded rather than guessed at. Rendered at the top of `templates/estimating/_material_summary.html` (hidden when the estimate is empty), styled by `.mat-summary-stats` in `main.css`. Because the viewer already re-fetches this partial after every trace create/update/delete, the bar is live with zero new endpoints or JS.

**Inline page rename.** The viewer title now carries a pencil button: click, type, Enter or blur saves, Escape cancels, and both the title and the current page-strip label update in place. `PlanPageLabelUpdateView` answers JSON (`{label, display_label}`) when the `X-Requested-With: XMLHttpRequest` header is present and keeps its redirect behavior for the project detail's plain form, so one endpoint serves both callers. The edit UI is a self-contained script in `templates/plans/viewer.html` (`#page-title-wrap` carries `data-label-url` / `data-label`); it swaps the title span for an input, posts FormData with the CSRF token, and guards double-submits with a `finished` flag since Enter also fires blur.

Tests: `estimating/test_views.py` (stats totals with exact BF math, bar hidden when empty), `plans/test_plan_pages.py::PlanPageLabelUpdateTests` (plain form redirect unchanged, AJAX JSON round trip, blank label falls back to "Page N", tenancy). Suite: 274 tests + 30 subtests, all passing.

## Quote header + assembly quick-edit drawer

**Quote header.** The estimate detail page now opens as a document: a `quote-head` block with the company (Account.name), a "Material Order List" doc label, and a meta grid (project, client, estimate, prepared date via `{% now %}`, contact = requesting user's email). A global `@media print` block in `main.css` hides the app chrome (rail, topbar, actions, messages, `.no-print`), strips card borders, and lets content go full width, so Print produces a clean supplier-ready sheet with no app UI on it. No view changes; everything reads from existing context.

**Quick-edit drawer.** Every assembly card in the Library grew a pencil button opening a right-side drawer (`#asm-drawer` in `library.html`) listing the assembly's rules with a material select and a waste input (percent in the UI, decimal fraction over the wire). Backend is `estimating.AssemblyQuickEditView` at `library/assemblies/<pk>/quick-edit/`:

- GET returns `{id, name, is_global, tool_type, rules: [{id, role, kind, material_id, waste_factor}]}`.
- POST takes `{rules: [{id, material_id, waste_factor}]}` and validates everything up front: rule ids must belong to the assembly, materials must be `visible_to(account)`, waste must be within 0 to 1. Any failure is a 400 with a message; the whole apply runs in one transaction.
- **Copy-on-write**: posting against a global assembly never mutates it. The view finds or creates the account's `"<name> (Custom)"` clone (a second lookup by `(account, opening_kind, wall_subtype)` guards that uniqueness constraint), copies every rule field, applies the edits (keyed by source rule id on create; matched by `(order, role)` on reuse), and returns `cloned: true/false`. Clones are always `is_default=False` so the viewer's single-default auto-select never turns ambiguous; tool memory re-selects the custom copy after the first manual pick.
- Posting against an account-owned assembly updates material and waste in place.
- The drawer JS lives in `library.html` (materials via `json_script`, save then `location.reload()` so the grouped lists re-render server-side). The drawer subtitle tells the user whether saving edits in place or creates their custom copy.

Tests: `estimating/test_views.py::AssemblyQuickEditTests` (GET shape, clone with source untouched, clone reuse on second edit, in-place edit on owned, foreign-material and out-of-range waste rejected, foreign custom assembly 404s). Suite: 280 tests + 30 subtests, all passing.

## Project templates + dashboard workflow guidance

Project setup is now template-driven instead of a blank wizard every time.

- `projects.ProjectTemplate` stores reusable job-setting defaults (floors, foundation, wall heights, stud spacing, roof framing, pitch, floor material, siding material). Four seeded starter templates ship out of the box: two ranches and two colonials using the 8 ft 1-1/8 in and 9 ft 1-1/8 in wall-height defaults.
- Wall-height fields on `JobSettings` and `ProjectTemplate` are `DecimalField(..., decimal_places=3)`, specifically so values like `97.125` and `109.125` are preserved exactly instead of being rounded to whole inches.
- `projects:template-library` is the reusable template hub. Account-owned templates can be created, edited, deleted, duplicated, and marked favorite; starter templates remain global and read-only, but can be duplicated into an account copy for customization.
- `ProjectTemplate.is_favorite` is account-only workflow memory. The library and New Project page sort favorites first, and `ProjectCreateView.get_template_object()` falls back to the favorite template when the user has not explicitly picked one, otherwise it preselects the first visible starter/default template.
- `ProjectTemplateDuplicateView` copies either a starter or custom template into the current account with a collision-safe `"(Copy)"` suffix, then redirects into edit. `ProjectTemplateFavoriteToggleView` enforces a single favorite per account by clearing any previous favorite inside one transaction before setting the new one.

The dashboard also now carries workflow-state guidance per project, computed cheaply with `Exists(...)` annotations rather than N+1 queries:

- `No plans uploaded`
- `Needs calibration`
- `Ready to trace`
- `Tracing in progress`
- `Estimate ready`

Each project card pairs that state badge with a short hint and direct `Open Project` / `Continue` actions, so users can tell the next step without drilling into the job first.

## Upload handoff + trace source links

Two navigation loops were tightened to reduce hunting:

- `plans.PlanUploadView` now defaults to `open_after_upload=1`. After rasterization, it redirects straight to the first generated `PlanPage` viewer and flashes a calibration prompt. The old "stay on project detail" behavior still exists for callers that post `open_after_upload=0`.
- Tool-generated rows on `estimating:estimate-detail` now show `Jump to source` when `LineItem.trace` exists. The link targets the owning plan page with `?trace=<trace id>`, e.g. `plans:viewer(page_id)?trace=123`.
- `plans/static/plans/viewer.js` reads that `trace` query parameter on load, finds the matching Fabric object after the page image and traces are rendered, selects it, and opens the inspector automatically. This is intentionally lightweight: no new backend endpoint was needed because the page already serializes every visible trace into `traces-data`.

## Trace inspector auto-save

The viewer's selected-trace inspector no longer requires a save click for every small tweak.

- The inspector panel in `templates/plans/viewer.html` now states `Changes save automatically.` and keeps the existing button as `Save now` for explicit retry/confirmation.
- `plans/static/plans/viewer.js` adds a debounced auto-save layer around the existing `TRACE_UPDATE_URL_BASE` POST. `traceInspectorPanel` listens to delegated `input` and `change` events for the inspector fields, `scheduleSelectedTracePersist()` batches changes for 450 ms, and `persistSelectedTraceChanges()` reuses the same payload shape the old manual button used.
- `inspectorSyncing` suppresses saves while the UI is being populated from a newly selected trace, `tracePersistNonce` prevents stale async responses from overwriting a newer edit session, and the small `#inspector-save-status` line tells the user whether the panel is pending, saving, saved, or failed.
- The selected wall/framing modal already had its own auto-save path for member overrides; this change brings the main trace inspector in line with that behavior instead of mixing one live-edit workflow with one explicit-save workflow.
