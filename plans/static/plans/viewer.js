'use strict';

document.addEventListener('DOMContentLoaded', function () {
    var root = document.getElementById('plan-viewer');
    if (!root) {
        return;
    }

    var IMAGE_URL = root.dataset.imageUrl;
    var TRACE_CREATE_URL = root.dataset.traceCreateUrl;
    var TRACE_UPDATE_URL_BASE = root.dataset.traceUpdateUrlBase;
    var TRACE_DELETE_URL_BASE = root.dataset.traceDeleteUrlBase;
    var TRACE_BATCH_UPDATE_URL = root.dataset.traceBatchUpdateUrl;
    var TRACE_BATCH_DELETE_URL = root.dataset.traceBatchDeleteUrl;
    var WALL_DETAIL_URL_BASE = root.dataset.wallDetailUrlBase;
    var CALIBRATE_URL = root.dataset.calibrateUrl;
    var PRESETS_URL = root.dataset.presetsUrl;
    var PRESET_FAVORITE_URL_BASE = root.dataset.presetFavoriteUrlBase;
    var MATERIAL_SUMMARY_URL = root.dataset.materialSummaryUrl;
    var PROJECT_ID = root.dataset.projectId;
    var PAGE_ID = root.dataset.pageId;
    var isCalibrated = root.dataset.isCalibrated === 'true';
    var scalePixelsPerFoot = parseFloat(root.dataset.scalePixelsPerFoot) || null;
    var defaultStudSpacing = parseInt(root.dataset.defaultStudSpacing, 10) || 16;
    var defaultWallHeight = parseFloat(root.dataset.defaultWallHeight) || 109.125;
    var TOOLBAR_SELECTOR = '#tool-toolbar';

    // Drawing tools that create traces. Calibrate is handled separately.
    var TOOLS = {
        line: {
            label: 'Draw Wall', color: '#0d6efd', activeColor: '#198754',
            settingsFields: ['stud-spacing', 'wall-height', 'plate-counts', 'wall-layers'], minPoints: 2, maxPoints: 2,
            hint: 'Click the start and end of the wall. Snaps to linework, endpoints, and square angles; hold Shift for free angles.',
        },
        area: {
            label: 'Draw Area Assembly', color: '#6f42c1', activeColor: '#198754',
            settingsFields: ['spacing', 'direction'], minPoints: 3, maxPoints: null,
            hint: 'Click two opposite corners for a rectangle.',
        },
        polyline: {
            label: 'Draw Polyline / Custom Assembly', color: '#20c997', activeColor: '#198754',
            settingsFields: ['closed'], minPoints: 2, maxPoints: null,
            hint: 'Click each corner (snaps to linework, endpoints, and square angles; Shift for free angles, Backspace removes the last point). Enter or double-click finishes.',
        },
        count: {
            label: 'Count', color: '#fd7e14', activeColor: '#198754',
            settingsFields: [], minPoints: 1, maxPoints: null,
            hint: 'Click each item. Double-click (or press Enter) to finish.',
        },
        opening: {
            label: 'Draw Opening', color: '#dc3545', activeColor: '#198754',
            settingsFields: ['opening-type', 'opening-size', 'stud-spacing'], minPoints: 2, maxPoints: 2,
            hint: 'One click on a wall places the opening at the Width setting, centered where you click. Or click both sides to size it by hand.',
        },
        measure: {
            label: 'Measure / Verify', color: '#6c757d', activeColor: '#6c757d',
            settingsFields: [], minPoints: 2, maxPoints: 2,
            hint: 'Click two points to verify a dimension. Snaps to linework and endpoints. Nothing is saved to the plan or estimate.',
        },
    };

    var toolPanelEl = document.getElementById('tool-panel');
    var noSelectionPanel = document.getElementById('no-selection-panel');
    var calibratePanel = document.getElementById('calibrate-panel');
    var toolSettingsPanel = document.getElementById('tool-settings-panel');
    var traceInspectorPanel = document.getElementById('trace-inspector-panel');
    var bulkSelectionPanel = document.getElementById('bulk-selection-panel');
    var calibrationStatus = document.getElementById('calibration-status');
    var toolHint = document.getElementById('tool-hint');
    var toolPanelTitle = document.getElementById('tool-panel-title');
    var lastMeasurement = document.getElementById('last-measurement');
    var dismissOnboardingTipButton = document.getElementById('dismiss-onboarding-tip');
    var headerCalibrateButton = document.getElementById('header-calibrate-tool');
    var prevPageButton = document.getElementById('prev-page-button');
    var nextPageButton = document.getElementById('next-page-button');
    var scalePresetSelect = document.getElementById('scale-preset-select');
    var applyScalePresetButton = document.getElementById('apply-scale-preset');

    var materialSelect = document.getElementById('material-select');
    var assemblySelect = document.getElementById('assembly-select');
    var studSpacingInput = document.getElementById('stud-spacing-input');
    var wallHeightInput = document.getElementById('wall-height-input');
    var spacingInput = document.getElementById('spacing-input');
    var directionSelect = document.getElementById('direction-select');
    var colorInput = document.getElementById('color-input');
    var closedInput = document.getElementById('closed-input');
    var presetSelect = document.getElementById('preset-select');
    var presetNameInput = document.getElementById('preset-name-input');
    var presetFavoriteButton = document.getElementById('preset-favorite-toggle');
    var toolMemoryStatus = document.getElementById('tool-memory-status');
    var toolMemoryToggleButton = document.getElementById('tool-memory-toggle');
    var toolMemoryClearButton = document.getElementById('tool-memory-clear');
    var deleteButton = document.getElementById('delete-selected');
    var materialControlsTrigger = document.getElementById('material-controls-trigger');
    var materialPageScopeButton = document.getElementById('material-page-scope');
    var materialFocusLinkedButton = document.getElementById('material-focus-linked');
    var materialSelectedOnlyButton = document.getElementById('material-selected-only');
    var materialCategoryOnlyButton = document.getElementById('material-category-only');
    var materialPrevLinkedButton = document.getElementById('material-prev-linked');
    var materialNextLinkedButton = document.getElementById('material-next-linked');
    var materialApplyToolSetupButton = document.getElementById('material-apply-tool-setup');
    var materialDeleteLinkedButton = document.getElementById('material-delete-linked');
    var materialClearLinkedButton = document.getElementById('material-clear-linked');
    var materialListStatus = document.getElementById('material-list-status');
    var selectionSummary = document.getElementById('selection-summary');
    var deleteUndoBanner = document.getElementById('delete-undo-banner');
    var deleteUndoText = document.getElementById('delete-undo-text');
    var undoDeleteTraceButton = document.getElementById('undo-delete-trace');

    var inspectorTitle = document.getElementById('inspector-title');
    var inspectorMeasurement = document.getElementById('inspector-measurement');
    var inspectorConfidenceStatus = document.getElementById('inspector-confidence-status');
    var inspectorConfidenceText = document.getElementById('inspector-confidence-text');
    var inspectorMaterialSelect = document.getElementById('inspector-material-select');
    var inspectorAssemblySelect = document.getElementById('inspector-assembly-select');
    var inspectorParentWallWrap = document.getElementById('inspector-parent-wall-wrap');
    var inspectorParentWallSelect = document.getElementById('inspector-parent-wall-select');
    var inspectorColorInput = document.getElementById('inspector-color-input');
    var inspectorSettingsWrap = document.getElementById('inspector-settings');
    var inspectorSaveStatus = document.getElementById('inspector-save-status');
    var useTraceForNewButton = document.getElementById('use-trace-for-new');
    var duplicateInspectedButton = document.getElementById('duplicate-inspected-trace');
    var selectSimilarInspectedButton = document.getElementById('select-similar-inspected-trace');
    var saveTraceChangesButton = document.getElementById('save-trace-changes');
    var deleteInspectedButton = document.getElementById('delete-inspected-trace');
    var viewWallElevationButton = document.getElementById('view-wall-elevation');
    var bulkSelectionTitle = document.getElementById('bulk-selection-title');
    var bulkSelectionSummary = document.getElementById('bulk-selection-summary');
    var bulkMaterialToggle = document.getElementById('bulk-material-toggle');
    var bulkMaterialSelect = document.getElementById('bulk-material-select');
    var bulkAssemblyWrap = document.getElementById('bulk-assembly-wrap');
    var bulkAssemblyToggle = document.getElementById('bulk-assembly-toggle');
    var bulkAssemblySelect = document.getElementById('bulk-assembly-select');
    var bulkColorToggle = document.getElementById('bulk-color-toggle');
    var bulkColorInput = document.getElementById('bulk-color-input');
    var bulkApplyButton = document.getElementById('bulk-apply-button');
    var bulkDeleteButton = document.getElementById('bulk-delete-button');
    var wallElevationBackdrop = document.getElementById('wall-elevation-backdrop');
    var wallElevationModal = document.getElementById('wall-elevation-modal');
    var wallElevationMeta = document.getElementById('wall-elevation-meta');
    var wallElevationSummary = document.getElementById('wall-elevation-summary');
    var wallElevationCanvas = document.getElementById('wall-elevation-canvas');
    var wall3dCanvas = document.getElementById('wall-3d-canvas');
    var wallLayerList = document.getElementById('wall-layer-list');
    var wallCutList = document.getElementById('wall-cut-list');
    var wallMemberDetail = document.getElementById('wall-member-detail');
    var wallEditToolbar = document.getElementById('wall-edit-toolbar');
    var wallEditStatus = document.getElementById('wall-edit-status');
    var deleteWallMemberInline = document.getElementById('delete-wall-member-inline');
    var currentWallModel = null;
    var selectedWallMemberId = null;
    var wallSvgState = null;
    var wallEditMode = 'select';
    var wallDrag = null;
    var wallPersistTimer = null;
    var closeWallElevationButton = document.getElementById('close-wall-elevation');

    // Pure geometry/format helpers live in viewer-helpers.js (loaded first),
    // shared with the node test suite in js_tests/.
    var viewerHelpers = window.LumberViewerHelpers;
    var formatFeetInches = viewerHelpers.formatFeetInches;
    var parseTraceIds = viewerHelpers.parseTraceIds;
    var projectPointToSegment = viewerHelpers.projectPointToSegment;

    var initialTraces = JSON.parse(document.getElementById('traces-data').textContent);
    var materialsData = JSON.parse(document.getElementById('materials-data').textContent);
    var assembliesData = JSON.parse(document.getElementById('assemblies-data').textContent);
    var wallsData = JSON.parse(document.getElementById('walls-data').textContent);
    var presetsById = {};
    JSON.parse(document.getElementById('presets-data').textContent).forEach(function (preset) {
        presetsById[preset.id] = preset;
    });

    var csrftoken = getCookie('csrftoken');
    var canvas = new fabric.Canvas('plan-canvas', { selection: true });
    var activeTool = null;
    var pendingPoints = [];        // clicks accumulated for the in-progress shape
    var previewObject = null;      // rubber-band preview while drawing
    var selectedTrace = null;
    var linkedTraceIds = [];
    var vertexEditObj = null;      // the line/polyline trace currently showing drag handles
    var vertexHandles = [];
    var vertexGhost = null;        // live dashed preview rebuilt while a handle is dragged
    var hoveredTraceIds = [];
    var activeMaterialSummary = null;
    var activeLinkedTraceIndex = -1;
    var materialSummaryPageOnly = false;
    var focusLinkedMode = false;
    var materialSelectedOnly = false;
    var materialCategoryOnly = false;
    var lastDeletedTraceSnapshot = null;
    var isPanning = false;         // hand tool: click-drag in progress
    var panStart = null;
    var inspectorSyncing = false;
    var tracePersistTimer = null;
    var tracePersistNonce = 0;
    var pendingPageHandoff = null;

    showPanel('none');

    fabric.Image.fromURL(IMAGE_URL, function (img) {
        imageNaturalWidth = img.width;
        imageNaturalHeight = img.height;
        canvas.setWidth(imageNaturalWidth);
        canvas.setHeight(imageNaturalHeight);
        canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
        initialTraces.forEach(drawTrace);
        applyMaterialVisibility();
        applyInitialZoom();
        focusRequestedTrace();
    });

    // ---------------------------------------------------------- material list

    function refreshMaterialList() {
        if (!MATERIAL_SUMMARY_URL) {
            return;
        }
        var summaryUrl = new URL(MATERIAL_SUMMARY_URL, window.location.origin);
        if (PAGE_ID) {
            summaryUrl.searchParams.set('current_page_id', PAGE_ID);
        }
        if (materialSummaryPageOnly) {
            summaryUrl.searchParams.set('page_only', '1');
        }
        fetch(summaryUrl.toString(), { headers: { 'X-CSRFToken': csrftoken } })
            .then(function (response) { return response.text(); })
            .then(function (html) {
                document.getElementById('material-list-content').innerHTML = html;
                syncMaterialListSelection();
                updateMaterialToolbarState();
                applyMaterialVisibility();
                annotateMaterialCategoryHeaders();
            })
            .catch(function () { /* not on the critical path - the panel just stays stale */ });
    }
    refreshMaterialList();
    updateMaterialToolbarState();

    // ------------------------------------------- material visibility toggles
    // The material list doubles as the visibility sidebar: each linked row has
    // an eye toggle that shows/hides its traces on the canvas. Hidden state is
    // keyed by the row's material label + category (stable across the partial
    // re-render that follows every trace change) and kept in sessionStorage per
    // page, like zoom. A trace linked from several rows (one wall feeds studs
    // AND plates rows) hides while ANY of its rows is hidden; visibility is
    // recomputed from scratch each time, so toggles can never drift.
    var HIDDEN_MATERIALS_KEY = 'plan-viewer-hidden-materials:' + (PAGE_ID || '0');
    var hiddenMaterialKeys = new Set();
    try {
        JSON.parse(window.sessionStorage.getItem(HIDDEN_MATERIALS_KEY) || '[]')
            .forEach(function (key) { hiddenMaterialKeys.add(key); });
    } catch (e) { /* fresh session */ }

    function materialVisibilityKey(row) {
        return (row.dataset.materialLabel || '') + '|' + (row.dataset.categoryLabel || '');
    }

    function persistHiddenMaterials() {
        try {
            window.sessionStorage.setItem(
                HIDDEN_MATERIALS_KEY, JSON.stringify(Array.from(hiddenMaterialKeys))
            );
        } catch (e) { /* storage unavailable */ }
    }

    function applyMaterialVisibility() {
        var hiddenTraceIds = {};
        document.querySelectorAll('#material-list-content .material-summary-row').forEach(function (row) {
            var key = materialVisibilityKey(row);
            var isHidden = hiddenMaterialKeys.has(key);
            row.classList.toggle('is-material-hidden', isHidden);
            var icon = row.querySelector('.mat-vis-toggle i');
            if (icon) {
                icon.className = isHidden ? 'bi bi-eye-slash' : 'bi bi-eye';
            }
            if (isHidden) {
                parseTraceIds(row.dataset.traceIds).forEach(function (traceId) {
                    hiddenTraceIds[traceId] = true;
                });
            }
        });
        canvas.getObjects().forEach(function (obj) {
            if (obj.traceId) {
                obj.visible = !hiddenTraceIds[obj.traceId];
            }
        });
        canvas.requestRenderAll();
    }

    document.getElementById('material-list-content').addEventListener('click', function (event) {
        var toggle = event.target.closest('.mat-vis-toggle');
        if (!toggle) {
            return;
        }
        event.stopImmediatePropagation();
        event.preventDefault();
        var row = toggle.closest('.material-summary-row');
        if (!row) {
            return;
        }
        var key = materialVisibilityKey(row);
        if (hiddenMaterialKeys.has(key)) {
            hiddenMaterialKeys.delete(key);
        } else {
            hiddenMaterialKeys.add(key);
        }
        persistHiddenMaterials();
        applyMaterialVisibility();
    });

    document.getElementById('material-list-content').addEventListener('click', function (event) {
        var row = event.target.closest('.material-summary-row');
        if (!row) {
            return;
        }
        var traceIds = parseTraceIds(row.dataset.traceIds);
        if (!traceIds.length) {
            return;
        }
        if (linkedTraceIds.length && traceIds.length === linkedTraceIds.length && traceIds.every(function (traceId) {
            return linkedTraceIds.indexOf(traceId) !== -1;
        })) {
            clearLinkedSelection();
            return;
        }
        activeMaterialSummary = materialSummaryFromRow(row);
        activateLinkedTraceIds(traceIds);
    });
    // Category headers double as clickable summary cards: one click
    // highlights every traced element feeding that construction system on
    // this page, the same way a single material row does for its own rows.
    document.getElementById('material-list-content').addEventListener('click', function (event) {
        var header = event.target.closest('.material-summary-group-header');
        if (!header) {
            return;
        }
        var group = header.closest('.material-summary-group');
        if (!group) {
            return;
        }
        var traceIds = [];
        group.querySelectorAll('.material-summary-row[data-trace-ids]').forEach(function (row) {
            parseTraceIds(row.dataset.traceIds).forEach(function (traceId) {
                if (traceIds.indexOf(traceId) === -1) {
                    traceIds.push(traceId);
                }
            });
        });
        if (!traceIds.length) {
            return;
        }
        activateLinkedTraceIds(traceIds);
    });

    function annotateMaterialCategoryHeaders() {
        document.querySelectorAll('#material-list-content .material-summary-group').forEach(function (group) {
            var rows = group.querySelectorAll('.material-summary-row');
            var totalQuantity = 0;
            rows.forEach(function (row) {
                totalQuantity += parseFloat(row.dataset.quantity) || 0;
            });
            var badge = group.querySelector('.material-summary-group-count');
            if (badge) {
                badge.textContent = rows.length + ' line' + (rows.length === 1 ? '' : 's')
                    + ' · ' + totalQuantity + ' pcs';
            }
        });
    }

    document.getElementById('material-list-content').addEventListener('mouseover', function (event) {
        var row = event.target.closest('.material-summary-row');
        if (!row) {
            return;
        }
        hoveredTraceIds = parseTraceIds(row.dataset.traceIds);
        updateMaterialHoverState(row);
    });
    document.getElementById('material-list-content').addEventListener('mouseout', function (event) {
        var row = event.target.closest('.material-summary-row');
        if (!row || row.contains(event.relatedTarget)) {
            return;
        }
        hoveredTraceIds = [];
        updateMaterialHoverState(null);
    });

    materialPageScopeButton.addEventListener('click', function () {
        materialSummaryPageOnly = !materialSummaryPageOnly;
        clearLinkedSelection();
        refreshMaterialList();
        updateMaterialToolbarState();
    });

    materialFocusLinkedButton.addEventListener('click', function () {
        if (!linkedTraceIds.length) {
            return;
        }
        focusLinkedMode = !focusLinkedMode;
        refreshLinkedTraceStyling();
        updateMaterialToolbarState();
    });

    materialSelectedOnlyButton.addEventListener('click', function () {
        if (!linkedTraceIds.length) {
            return;
        }
        materialSelectedOnly = !materialSelectedOnly;
        applyMaterialListFilters();
        updateMaterialToolbarState();
    });

    materialCategoryOnlyButton.addEventListener('click', function () {
        if (!activeMaterialSummary || !activeMaterialSummary.categoryLabel) {
            return;
        }
        materialCategoryOnly = !materialCategoryOnly;
        applyMaterialListFilters();
        updateMaterialToolbarState();
    });

    materialClearLinkedButton.addEventListener('click', function () {
        clearLinkedSelection();
    });

    materialApplyToolSetupButton.addEventListener('click', function () {
        applyCurrentToolSetupToLinkedTraces();
    });

    materialDeleteLinkedButton.addEventListener('click', function () {
        deleteLinkedTraces();
    });

    bulkApplyButton.addEventListener('click', function () {
        applyBulkSelectionChanges();
    });

    bulkDeleteButton.addEventListener('click', function () {
        deleteLinkedTraces();
    });

    undoDeleteTraceButton.addEventListener('click', function () {
        undoLastDeletedTrace();
    });

    materialPrevLinkedButton.addEventListener('click', function () {
        cycleLinkedTrace(-1);
    });

    materialNextLinkedButton.addEventListener('click', function () {
        cycleLinkedTrace(1);
    });

    // ------------------------------------------------------------------ zoom
    // Trace geometry is stored in the plan image's natural pixel space.
    // Zooming resizes the canvas's own raster (rather than panning via
    // Fabric's viewportTransform), so canvas.getPointer() keeps returning
    // coordinates in that same natural space at any zoom level - drawing and
    // calibration math elsewhere never need to know the current zoom.
    var imageNaturalWidth = 0;
    var imageNaturalHeight = 0;
    var currentZoom = 1;
    var ZOOM_MIN = 0.25;
    var ZOOM_MAX = 3;
    var ZOOM_STEP = 0.25;
    var canvasWrapEl = document.getElementById('plan-canvas-wrap');
    var zoomLevelLabel = document.getElementById('zoom-level');

    // Persisted per plan page (not globally) so switching pages never leaks
    // one page's zoom onto another. sessionStorage (not localStorage) is a
    // deliberate choice: it survives an ordinary reload of this tab but a
    // fresh navigation combined with the reload-type check below is what
    // actually decides whether to restore it - see applyInitialZoom().
    var ZOOM_STORAGE_KEY = PAGE_ID ? ('plan-viewer-zoom:' + PAGE_ID) : null;

    function storeZoom(zoom) {
        if (!ZOOM_STORAGE_KEY) {
            return;
        }
        try {
            window.sessionStorage.setItem(ZOOM_STORAGE_KEY, String(zoom));
        } catch (e) { /* storage unavailable (private browsing, etc.) - zoom just won't persist */ }
    }

    function getStoredZoom() {
        if (!ZOOM_STORAGE_KEY) {
            return null;
        }
        try {
            var value = window.sessionStorage.getItem(ZOOM_STORAGE_KEY);
            return value ? parseFloat(value) : null;
        } catch (e) {
            return null;
        }
    }

    // Distinguishes an actual browser reload (F5, Ctrl+R) from a fresh
    // navigation to this URL (link click, back/forward, first visit) - only
    // a reload should restore the last zoom; any other kind of arrival at
    // this page is "changing pages" and should fit, per the product ask.
    function isReloadNavigation() {
        if (window.performance && typeof performance.getEntriesByType === 'function') {
            var entries = performance.getEntriesByType('navigation');
            if (entries.length > 0) {
                return entries[0].type === 'reload';
            }
        }
        return Boolean(window.performance && performance.navigation && performance.navigation.type === 1);
    }

    function applyInitialZoom() {
        var stored = isReloadNavigation() ? getStoredZoom() : null;
        if (stored) {
            setZoom(stored);
        } else {
            fitToView();
        }
    }

    function fitToView() {
        if (!imageNaturalWidth || !imageNaturalHeight) {
            return;
        }
        var wrapRect = canvasWrapEl.getBoundingClientRect();
        setZoom(Math.min(wrapRect.width / imageNaturalWidth, wrapRect.height / imageNaturalHeight));
    }

    function setZoom(nextZoom, anchor) {
        if (!imageNaturalWidth || !imageNaturalHeight) {
            return;
        }
        nextZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, nextZoom));
        var wrapRect = canvasWrapEl.getBoundingClientRect();
        var anchorX = anchor ? anchor.x : wrapRect.width / 2;
        var anchorY = anchor ? anchor.y : wrapRect.height / 2;
        var contentX = canvasWrapEl.scrollLeft + anchorX;
        var contentY = canvasWrapEl.scrollTop + anchorY;
        var ratio = nextZoom / currentZoom;

        currentZoom = nextZoom;
        canvas.setZoom(currentZoom);
        canvas.setWidth(imageNaturalWidth * currentZoom);
        canvas.setHeight(imageNaturalHeight * currentZoom);
        canvas.requestRenderAll();

        canvasWrapEl.scrollLeft = contentX * ratio - anchorX;
        canvasWrapEl.scrollTop = contentY * ratio - anchorY;
        zoomLevelLabel.textContent = Math.round(currentZoom * 100) + '%';
        storeZoom(currentZoom);
    }

    document.getElementById('zoom-in').addEventListener('click', function () {
        setZoom(currentZoom + ZOOM_STEP);
    });
    document.getElementById('zoom-out').addEventListener('click', function () {
        setZoom(currentZoom - ZOOM_STEP);
    });
    document.getElementById('zoom-reset').addEventListener('click', function () {
        setZoom(1);
    });
    document.getElementById('zoom-fit').addEventListener('click', fitToView);
    canvasWrapEl.addEventListener('wheel', function (evt) {
        if (!evt.ctrlKey && !evt.metaKey) {
            return; // Plain scroll pans natively; Ctrl/Cmd+wheel zooms.
        }
        evt.preventDefault();
        var rect = canvasWrapEl.getBoundingClientRect();
        var direction = evt.deltaY < 0 ? 1 : -1;
        setZoom(currentZoom + direction * ZOOM_STEP, { x: evt.clientX - rect.left, y: evt.clientY - rect.top });
    }, { passive: false });

    // ------------------------------------------------------------------ tools

    // Semantic construction tools shown above the raw geometry tools in the
    // sidebar - each maps to one of the raw tool_types below and (for
    // Wall/Opening/Beam) narrows the assembly dropdown to matching-tagged
    // assemblies via populateAssemblyOptions's variantFilter param. The raw
    // tools underneath are kept exactly as they were, for flexibility/custom
    // assemblies - semantic tools are additive, not a replacement.
    //
    // settingsFields is an explicit override of which of the raw tool's
    // settings inputs actually apply to this construction element - e.g. a
    // Plate or Rim Board is just a stock-length run (no stud spacing/wall
    // height/layers to configure), even though it shares the 'line' tool_type
    // with Wall, which does need those. Falls back to TOOLS[toolType]'s own
    // full field list only for the raw tool buttons below (no override passed).
    //
    // Wall uses the 'polyline' tool_type (not 'line') so a whole connected
    // wall run can be drawn as one continuous click-each-corner action
    // instead of one 2-point trace per segment - the calc engine and the
    // wall-junction/corner-stud detection already treat an open (non-closed)
    // polyline exactly like a line wall (see plans/framing.py,
    // estimating/calculations.py), so this is purely a drawing-UX change.
    var SEMANTIC_TOOLS = {
        wall: { toolType: 'polyline', label: 'Wall', settingsFields: ['stud-spacing', 'wall-height', 'plate-counts'] },
        opening: { toolType: 'opening', label: 'Opening', settingsFields: ['opening-type', 'opening-size', 'stud-spacing'] },
        beam: { toolType: 'line', label: 'Beam', settingsFields: [] },
        joist: { toolType: 'area', label: 'Joist', settingsFields: ['spacing', 'direction'] },
        column: { toolType: 'count', label: 'Column', settingsFields: [] },
        plate: { toolType: 'line', label: 'Plate', settingsFields: [] },
        rim_board: { toolType: 'line', label: 'Rim Board', settingsFields: [] },
    };
    var activeVariantFilter = null;
    // Which semantic tool (if any) launched the current draw, e.g. 'wall' -
    // lets collectSettings() know a 'polyline' trace being drawn right now is
    // specifically a Wall (needs stud-spacing/wall-height/etc.) rather than a
    // raw custom polyline (which only has the 'closed' toggle). Reset to null
    // whenever a raw tool button is used instead.
    var activeSemanticKey = null;

    document.querySelectorAll(TOOLBAR_SELECTOR + ' .tool-btn[data-tool]').forEach(function (button) {
        button.addEventListener('click', function () {
            var tool = button.dataset.tool;
            var wasActive = activeTool === tool && button.classList.contains('active');
            activeSemanticKey = null;
            activateTool(wasActive ? null : tool, null, null, wasActive ? null : button);
        });
    });

    if (headerCalibrateButton) {
        headerCalibrateButton.addEventListener('click', function () {
            var wasActive = activeTool === 'calibrate' && headerCalibrateButton.classList.contains('active');
            activeSemanticKey = null;
            activateTool(wasActive ? null : 'calibrate', null, null, wasActive ? null : headerCalibrateButton);
        });
    }

    document.querySelectorAll(TOOLBAR_SELECTOR + ' [data-semantic]').forEach(function (button) {
        button.addEventListener('click', function () {
            var config = SEMANTIC_TOOLS[button.dataset.semantic];
            if (!config) {
                return;
            }
            // Clicking the already-active variant again turns the tool off
            // (mirrors the raw tool buttons' toggle behavior) - otherwise,
            // since semantic tools have no other "none" button, there'd be no
            // way back to idle/selectable mode without picking a different
            // tool first.
            if (button.classList.contains('active')) {
                activeSemanticKey = null;
                activateTool(null);
                return;
            }
            activeSemanticKey = button.dataset.semantic;
            var variantFilter = null;
            if (button.dataset.wallSubtype) {
                variantFilter = { wallSubtype: button.dataset.wallSubtype };
            } else if (button.dataset.beamType) {
                variantFilter = { beamType: button.dataset.beamType };
            } else if (button.dataset.openingKind) {
                variantFilter = { openingKind: button.dataset.openingKind };
            } else if (button.dataset.semantic === 'joist') {
                variantFilter = { categoryIn: ['floor_system', 'ceiling', 'roof'] };
            }
            activateTool(config.toolType, variantFilter, config.label, button, config.settingsFields);
            if (variantFilter && variantFilter.openingKind) {
                var openingTypeSelect = document.getElementById('opening-type-select');
                if (openingTypeSelect) {
                    openingTypeSelect.value = variantFilter.openingKind;
                }
            }
            var menu = button.closest('.dropdown-menu');
            if (menu && window.bootstrap) {
                var toggle = menu.previousElementSibling;
                if (toggle) {
                    bootstrap.Dropdown.getOrCreateInstance(toggle).hide();
                }
            }
        });
    });

    // Tools that measure real-world distance are useless without a scale.
    // Arming one on an uncalibrated page redirects to the calibrate tool
    // instead of letting the user draw into a server error; the requested
    // tool is remembered and re-armed automatically once the scale is set.
    var MEASURING_TOOLS = ['line', 'area', 'polyline', 'opening', 'measure'];
    var pendingToolActivation = null;

    function activateTool(tool, variantFilter, variantLabel, sourceButton, settingsFieldsOverride) {
        var rearmRequest = null;
        if (tool && MEASURING_TOOLS.indexOf(tool) !== -1 && !isCalibrated) {
            rearmRequest = {
                tool: tool, variantFilter: variantFilter, variantLabel: variantLabel,
                sourceButton: sourceButton, settingsFieldsOverride: settingsFieldsOverride,
            };
            tool = 'calibrate';
            variantFilter = null;
            variantLabel = null;
            settingsFieldsOverride = null;
            sourceButton = headerCalibrateButton || document.querySelector(TOOLBAR_SELECTOR + ' .tool-btn[data-tool="calibrate"]');
        }
        // Any activation (guarded redirect, direct tool pick, or deactivate)
        // replaces the pending re-arm, so switching tools or hitting Escape
        // never resurrects a stale request later.
        pendingToolActivation = rearmRequest;

        if (tool) {
            dismissOnboardingTip(); // picking any tool once is "first use" - the hint has done its job
        }
        activeTool = tool;
        activeVariantFilter = variantFilter || null;

        document.querySelectorAll(TOOLBAR_SELECTOR + ' .tool-btn, ' + TOOLBAR_SELECTOR + ' .dropdown-item, .viewer-page-tools .tool-btn').forEach(function (button) {
            button.classList.remove('active');
        });
        if (sourceButton) {
            sourceButton.classList.add('active');
            var parentDropdown = sourceButton.closest('.dropdown');
            if (parentDropdown) {
                var toggle = parentDropdown.querySelector('.dropdown-toggle');
                if (toggle) {
                    toggle.classList.add('active');
                }
            }
        }

        canvas.selection = tool === null;
        // Any active drawing tool disables hit-testing on existing traces -
        // otherwise clicking to place a point right on/near a previously
        // drawn trace (e.g. continuing a wall from where the last one ended)
        // would hover a "move" cursor and select that trace instead of
        // placing a point, which also silently deactivates the tool (see
        // onTraceSelected -> activateTool(null)). Only idle (tool === null)
        // leaves traces selectable, for inspection/editing.
        canvas.skipTargetFind = Boolean(tool);
        canvas.defaultCursor = tool === 'hand' ? 'grab' : (tool ? 'crosshair' : 'default');
        resetPending();
        canvas.discardActiveObject();
        canvas.requestRenderAll();

        if (tool === 'measure') {
            toolHint.textContent = TOOLS.measure.hint;
            updateToolMemoryUi(null, null, null);
            showPanel('none');
        } else if (tool && TOOLS[tool]) {
            configureToolPanel(tool, variantLabel, settingsFieldsOverride);
            showPanel('tool-settings');
        } else if (tool === 'calibrate') {
            if (pendingToolActivation) {
                var pendingName = pendingToolActivation.variantLabel
                    || (TOOLS[pendingToolActivation.tool] && TOOLS[pendingToolActivation.tool].label)
                    || 'drawing';
                toolHint.textContent = 'This page has no scale yet. Set it below and the '
                    + pendingName + ' tool will arm automatically.';
            } else {
                toolHint.textContent = 'Click both ends of a line with a known real-world length.';
            }
            scalePresetSelect.value = '';
            showPanel('calibrate');
        } else if (tool === 'hand') {
            toolHint.textContent = 'Click and drag to pan the view.';
            updateToolMemoryUi(null, null, null);
            showPanel('none');
        } else {
            toolHint.textContent = '';
            updateToolMemoryUi(null, null, null);
            showPanel('none');
        }
    }

    function configureToolPanel(tool, variantLabel, settingsFieldsOverride) {
        var config = TOOLS[tool];
        var fields = settingsFieldsOverride || config.settingsFields;
        toolPanelTitle.textContent = (variantLabel || config.label) + ' Tool';
        toolHint.textContent = config.hint;
        document.querySelectorAll('#tool-settings-panel [data-field]').forEach(function (wrap) {
            wrap.style.display = fields.indexOf(wrap.dataset.field) === -1 ? 'none' : '';
        });
        populateAssemblyOptions(assemblySelect, tool, collectSettings(tool, ''), activeVariantFilter, Boolean(activeSemanticKey));
        populatePresetOptions(tool);
        colorInput.value = config.color;
        restoreToolMemory(tool, activeVariantFilter, activeSemanticKey);
        updateToolMemoryUi(tool, activeVariantFilter, activeSemanticKey);
    }

    function populateAssemblyOptions(select, toolType, settings, variantFilter, preferDefault) {
        select.innerHTML = '<option value="">-- none (display only) --</option>';
        var candidates = assembliesData.filter(function (assembly) {
            if (assembly.tool_type === toolType) {
                return true;
            }
            if (toolType === 'polyline') {
                return assembly.tool_type === ((settings || {}).closed ? 'area' : 'line');
            }
            return false;
        });
        if (variantFilter) {
            var filtered = candidates.filter(function (assembly) {
                if (variantFilter.wallSubtype) {
                    return assembly.wall_subtype === variantFilter.wallSubtype;
                }
                if (variantFilter.beamType) {
                    return assembly.beam_type === variantFilter.beamType;
                }
                if (variantFilter.openingKind) {
                    return assembly.opening_kind === variantFilter.openingKind;
                }
                if (variantFilter.categoryIn) {
                    return variantFilter.categoryIn.indexOf(assembly.category) !== -1;
                }
                return true;
            });
            // Never show an empty dropdown just because nothing's tagged yet
            // for this variant - fall back to the full tool_type-compatible list.
            if (filtered.length > 0) {
                candidates = filtered;
            }
        }
        candidates.forEach(function (assembly) {
            var option = document.createElement('option');
            option.value = assembly.id;
            option.textContent = assembly.name;
            select.appendChild(option);
        });
        // Auto-select so drawing produces a material list with no extra click.
        // Priority: the single default in this candidate set (only when a tool
        // asks for it, e.g. a semantic tool), else the sole candidate. If more
        // than one default is in scope (an ambiguous set like the raw line
        // tool) leave it on "none" rather than guess.
        var defaults = candidates.filter(function (assembly) { return assembly.is_default; });
        if (preferDefault && defaults.length === 1) {
            select.value = defaults[0].id;
        } else if (variantFilter && candidates.length === 1) {
            select.value = candidates[0].id;
        }
    }

    function populateParentWallOptions(select, excludeTraceId) {
        select.innerHTML = '<option value="">-- none --</option>';
        wallsData.filter(function (wall) {
            return wall.id !== excludeTraceId;
        }).forEach(function (wall) {
            var option = document.createElement('option');
            option.value = wall.id;
            option.textContent = (wall.tool_type === 'polyline' ? 'Polyline' : 'Line') + ' wall #' + wall.id;
            select.appendChild(option);
        });
    }

    function populatePresetOptions(toolType) {
        presetSelect.innerHTML = '<option value="">-- load a preset --</option>';
        // Object.keys() on numeric-string ids always iterates in ascending
        // numeric order regardless of insertion order, so favorites need an
        // explicit sort rather than relying on dict iteration.
        var matches = Object.keys(presetsById)
            .map(function (id) { return presetsById[id]; })
            .filter(function (preset) { return preset.tool_type === toolType; });
        matches.sort(function (a, b) {
            if (Boolean(a.is_favorite) !== Boolean(b.is_favorite)) {
                return a.is_favorite ? -1 : 1;
            }
            return a.name.localeCompare(b.name);
        });
        matches.forEach(function (preset) {
            var option = document.createElement('option');
            option.value = preset.id;
            option.textContent = (preset.is_favorite ? '★ ' : '') + preset.name;
            presetSelect.appendChild(option);
        });
        updatePresetFavoriteButton();
    }

    function updatePresetFavoriteButton() {
        var preset = presetsById[presetSelect.value];
        presetFavoriteButton.disabled = !preset;
        var icon = presetFavoriteButton.querySelector('i');
        icon.className = preset && preset.is_favorite ? 'bi bi-star-fill' : 'bi bi-star';
    }

    function collectWallSettings(byId) {
        return {
            stud_spacing_in: parseInt(byId('stud-spacing-input').value, 10) || null,
            // parseFloat (not parseInt) - a real wall height is often
            // fractional (e.g. 97.125" for an 8'-1-1/8" wall using 92-5/8"
            // precut studs), and the calc engine's stud-length lookup needs
            // that fraction to pick the exact precut rather than rounding it away.
            wall_height_in: parseFloat(byId('wall-height-input').value) || null,
            top_plate_count: parseInt(byId('top-plate-count-input').value, 10) || 2,
            bottom_plate_count: parseInt(byId('bottom-plate-count-input').value, 10) || 1,
            interior_drywall: byId('interior-drywall-input').checked,
            exterior_sheathing: byId('exterior-sheathing-input').checked,
            house_wrap: byId('house-wrap-input').checked,
            siding: byId('siding-input').checked,
        };
    }

    function collectSettings(tool, prefix) {
        // Reads the settings inputs relevant to `tool`. `prefix` distinguishes
        // the draw panel ('') from the inspector ('inspector-').
        var byId = function (id) { return document.getElementById(prefix + id); };
        if (tool === 'line') {
            return collectWallSettings(byId);
        }
        if (tool === 'area') {
            return {
                spacing_in: parseInt(byId('spacing-input').value, 10) || null,
                member_direction: byId('direction-select').value || 'horizontal',
            };
        }
        if (tool === 'opening') {
            return {
                opening_type: byId('opening-type-select').value || 'window',
                rough_width_in: parseFloat(byId('rough-width-input').value) || null,
                sill_height_in: parseInt(byId('sill-height-input').value, 10) || null,
                rough_height_in: parseInt(byId('rough-height-input').value, 10) || null,
                header_depth_in: parseFloat(byId('header-depth-input').value) || null,
                stud_spacing_in: parseInt(byId('stud-spacing-input').value, 10) || null,
            };
        }
        if (tool === 'polyline') {
            // The Wall semantic tool draws as an open polyline (see
            // SEMANTIC_TOOLS.wall) - it needs the same settings a 'line'
            // wall does, always non-closed. A raw Polyline trace (drawn via
            // the plain sidebar button, activeSemanticKey null) only has the
            // closed toggle, per its own settings-panel fields.
            if (activeSemanticKey === 'wall') {
                var wallSettings = collectWallSettings(byId);
                wallSettings.closed = false;
                return wallSettings;
            }
            return { closed: byId('closed-input').checked };
        }
        return {};
    }

    // ------------------------------------------------- tool memory (per session)
    // Remembers the last-used settings, assembly, material tag, and color for
    // each tool + variant, so drawing many walls (or joists, openings, etc.)
    // in a row never re-prompts. sessionStorage (like zoom) so it survives a
    // reload of this tab but does not leak across sessions. Scoped per page and
    // per tool-variant, so an exterior wall and a joist keep separate memory.
    function toolMemoryKey(tool, variantFilter, semanticKey) {
        if (!tool || !TOOLS[tool]) {
            return null;
        }
        var variant = '';
        if (variantFilter) {
            if (variantFilter.wallSubtype) {
                variant = 'wall:' + variantFilter.wallSubtype;
            } else if (variantFilter.beamType) {
                variant = 'beam:' + variantFilter.beamType;
            } else if (variantFilter.openingKind) {
                variant = 'open:' + variantFilter.openingKind;
            } else if (variantFilter.categoryIn) {
                variant = 'cat:' + variantFilter.categoryIn.join(',');
            }
        }
        if (!variant && semanticKey) {
            variant = 's:' + semanticKey;
        }
        return 'plan-viewer-tool:' + (PAGE_ID || '0') + ':' + tool + '|' + variant;
    }

    function toolMemoryPauseKey(tool, variantFilter, semanticKey) {
        var key = toolMemoryKey(tool, variantFilter, semanticKey);
        return key ? (key + ':paused') : null;
    }

    function isToolMemoryPaused(tool, variantFilter, semanticKey) {
        var key = toolMemoryPauseKey(tool, variantFilter, semanticKey);
        if (!key) {
            return false;
        }
        try {
            return window.sessionStorage.getItem(key) === '1';
        } catch (e) {
            return false;
        }
    }

    function setToolMemoryPaused(tool, variantFilter, semanticKey, paused) {
        var key = toolMemoryPauseKey(tool, variantFilter, semanticKey);
        if (!key) {
            return;
        }
        try {
            if (paused) {
                window.sessionStorage.setItem(key, '1');
            } else {
                window.sessionStorage.removeItem(key);
            }
        } catch (e) { /* storage unavailable - pause state just won't persist */ }
    }

    function optionExists(select, value) {
        var wanted = value || '';
        return Array.prototype.some.call(select.options, function (option) {
            return option.value === wanted;
        });
    }

    function applyToolSettings(settings) {
        // Inverse of collectSettings: writes remembered values back into the
        // panel inputs. Only keys that are present are applied, so a remembered
        // null never blanks a field that has a sensible default.
        if (!settings) {
            return;
        }
        var setValue = function (id, value) {
            var el = document.getElementById(id);
            if (el && value !== null && value !== undefined) {
                el.value = value;
            }
        };
        var setChecked = function (id, value) {
            var el = document.getElementById(id);
            if (el && typeof value === 'boolean') {
                el.checked = value;
            }
        };
        setValue('stud-spacing-input', settings.stud_spacing_in);
        setValue('wall-height-input', settings.wall_height_in);
        setValue('top-plate-count-input', settings.top_plate_count);
        setValue('bottom-plate-count-input', settings.bottom_plate_count);
        setChecked('interior-drywall-input', settings.interior_drywall);
        setChecked('exterior-sheathing-input', settings.exterior_sheathing);
        setChecked('house-wrap-input', settings.house_wrap);
        setChecked('siding-input', settings.siding);
        setValue('spacing-input', settings.spacing_in);
        setValue('direction-select', settings.member_direction);
        setValue('opening-type-select', settings.opening_type);
        setValue('rough-width-input', settings.rough_width_in);
        setValue('sill-height-input', settings.sill_height_in);
        setValue('rough-height-input', settings.rough_height_in);
        setValue('header-depth-input', settings.header_depth_in);
        setChecked('closed-input', settings.closed);
    }

    function saveToolMemory(tool, variantFilter, semanticKey) {
        var key = toolMemoryKey(tool, variantFilter, semanticKey);
        if (!key || isToolMemoryPaused(tool, variantFilter, semanticKey)) {
            return;
        }
        var memory = {
            settings: collectSettings(tool, ''),
            assemblyId: assemblySelect.value || '',
            materialId: materialSelect.value || '',
            color: colorInput.value || '',
        };
        try {
            window.sessionStorage.setItem(key, JSON.stringify(memory));
        } catch (e) { /* storage unavailable - memory just won't persist */ }
    }

    function restoreToolMemory(tool, variantFilter, semanticKey) {
        // Applied after populateAssemblyOptions, so a remembered assembly
        // intentionally overrides the auto-selected default. When there is no
        // memory yet, the default from populateAssemblyOptions stands.
        var key = toolMemoryKey(tool, variantFilter, semanticKey);
        if (!key || isToolMemoryPaused(tool, variantFilter, semanticKey)) {
            return;
        }
        var raw;
        try {
            raw = window.sessionStorage.getItem(key);
        } catch (e) {
            return;
        }
        if (!raw) {
            return;
        }
        var memory;
        try {
            memory = JSON.parse(raw);
        } catch (e) {
            return;
        }
        applyToolSettings(memory.settings);
        if (memory.color) {
            colorInput.value = memory.color;
        }
        if (optionExists(materialSelect, memory.materialId)) {
            materialSelect.value = memory.materialId || '';
        }
        if (optionExists(assemblySelect, memory.assemblyId)) {
            assemblySelect.value = memory.assemblyId || '';
        }
    }

    function clearToolMemory(tool, variantFilter, semanticKey) {
        var key = toolMemoryKey(tool, variantFilter, semanticKey);
        if (!key) {
            return;
        }
        try {
            window.sessionStorage.removeItem(key);
        } catch (e) { /* storage unavailable - nothing to clear */ }
    }

    function updateToolMemoryUi(tool, variantFilter, semanticKey) {
        if (!toolMemoryStatus || !toolMemoryToggleButton || !toolMemoryClearButton) {
            return;
        }
        var active = Boolean(tool && TOOLS[tool]);
        toolMemoryToggleButton.disabled = !active;
        toolMemoryClearButton.disabled = !active;
        if (!active) {
            toolMemoryStatus.textContent = 'Tool memory is available while a drawing tool is active.';
            toolMemoryToggleButton.textContent = 'Pause memory';
            return;
        }
        var paused = isToolMemoryPaused(tool, variantFilter, semanticKey);
        toolMemoryStatus.textContent = paused
            ? 'Remembered setup is paused for this tool on this page.'
            : 'This tool remembers your last setup for this page.';
        toolMemoryToggleButton.textContent = paused ? 'Resume memory' : 'Pause memory';
    }

    // Persist as soon as the user adjusts the panel, so a picked assembly or
    // spacing sticks even if they switch tools before drawing the first trace.
    toolSettingsPanel.addEventListener('change', function () {
        if (activeTool && TOOLS[activeTool]) {
            saveToolMemory(activeTool, activeVariantFilter, activeSemanticKey);
            updateToolMemoryUi(activeTool, activeVariantFilter, activeSemanticKey);
        }
    });

    toolMemoryToggleButton.addEventListener('click', function () {
        if (!activeTool || !TOOLS[activeTool]) {
            return;
        }
        var paused = isToolMemoryPaused(activeTool, activeVariantFilter, activeSemanticKey);
        setToolMemoryPaused(activeTool, activeVariantFilter, activeSemanticKey, !paused);
        updateToolMemoryUi(activeTool, activeVariantFilter, activeSemanticKey);
    });

    toolMemoryClearButton.addEventListener('click', function () {
        if (!activeTool || !TOOLS[activeTool]) {
            return;
        }
        clearToolMemory(activeTool, activeVariantFilter, activeSemanticKey);
        updateToolMemoryUi(activeTool, activeVariantFilter, activeSemanticKey);
    });

    // ---------------------------------------------------- drawing assists
    // Four click-savers for the measuring tools (line / polyline / opening /
    // measure):
    //   1. Endpoint snap: land exactly on a nearby existing trace endpoint.
    //   2. Segment snap: land on nearby traced linework, not just endpoints.
    //   3. Ortho snap: within a few degrees of square (45-degree steps) the
    //      segment locks to the exact angle. Hold Shift to draw free angles.
    //   4. A live length readout follows the cursor while drawing.
    var SNAP_SCREEN_PX = 12;
    var ORTHO_TOLERANCE_RAD = 8 * Math.PI / 180;
    var SNAPPING_TOOLS = ['line', 'polyline', 'opening', 'measure'];

    function snapRadiusCanvasPx() {
        return SNAP_SCREEN_PX / (canvas.getZoom() || 1);
    }

    function endpointSnapCandidates() {
        var points = [];
        canvas.getObjects().forEach(function (obj) {
            if (!obj.traceId || obj.visible === false) {
                return;
            }
            if (SNAPPING_TOOLS.indexOf(obj.traceToolType) === -1) {
                return;
            }
            var geometry = obj.traceGeometry || [];
            if (geometry.length >= 2) {
                points.push(geometry[0]);
                points.push(geometry[geometry.length - 1]);
            }
        });
        if (pendingPoints.length > 2) {
            points.push(pendingPoints[0]);
        }
        return points;
    }

    function snapToEndpoint(pointer) {
        return viewerHelpers.nearestPointWithin(
            endpointSnapCandidates(), pointer, snapRadiusCanvasPx()
        );
    }

    function snapToSegment(pointer) {
        var geometries = [];
        canvas.getObjects().forEach(function (obj) {
            if (!obj.traceId || obj.visible === false) {
                return;
            }
            if (SNAPPING_TOOLS.indexOf(obj.traceToolType) === -1) {
                return;
            }
            geometries.push(obj.traceGeometry || []);
        });
        var projection = viewerHelpers.nearestSegmentProjection(geometries, pointer, snapRadiusCanvasPx());
        return projection ? { x: projection.point.x, y: projection.point.y } : null;
    }

    function snapToOrtho(previous, pointer) {
        return viewerHelpers.snapToOrtho(previous, pointer, ORTHO_TOLERANCE_RAD);
    }

    function applyDrawingSnaps(pointer, domEvent) {
        if (SNAPPING_TOOLS.indexOf(activeTool) === -1) {
            return pointer;
        }
        if (domEvent && domEvent.shiftKey) {
            return pointer;
        }
        var endpoint = snapToEndpoint(pointer);
        if (endpoint) {
            return endpoint;
        }
        var segment = snapToSegment(pointer);
        if (segment) {
            return segment;
        }
        if (pendingPoints.length > 0) {
            return snapToOrtho(pendingPoints[pendingPoints.length - 1], pointer);
        }
        return pointer;
    }

    // ---- live length readout ----
    var measureReadout = document.createElement('div');
    measureReadout.id = 'draw-measure-readout';
    measureReadout.hidden = true;
    canvasWrapEl.appendChild(measureReadout);

    function updateMeasureReadout(pointer, domEvent) {
        var measuring = isCalibrated && scalePixelsPerFoot
            && SNAPPING_TOOLS.indexOf(activeTool) !== -1 && pendingPoints.length > 0;
        if (!measuring) {
            measureReadout.hidden = true;
            return;
        }
        var previous = pendingPoints[pendingPoints.length - 1];
        var distPx = Math.hypot(pointer.x - previous.x, pointer.y - previous.y);
        measureReadout.textContent = formatFeetInches(distPx / scalePixelsPerFoot);
        var rect = canvasWrapEl.getBoundingClientRect();
        measureReadout.style.left = (domEvent.clientX - rect.left + canvasWrapEl.scrollLeft + 16) + 'px';
        measureReadout.style.top = (domEvent.clientY - rect.top + canvasWrapEl.scrollTop + 16) + 'px';
        measureReadout.hidden = false;
    }

    // ---- floating quick-edit HUD ----
    // A small canvas-anchored popover for the handful of fields worth
    // editing without leaving the drawing surface (material + the one or two
    // settings that matter most for the selected trace's type). It mirrors
    // values into the real sidebar inspector fields and dispatches their
    // native events, so the existing auto-save pipeline (scheduleSelectedTracePersist)
    // is the only place persistence logic lives - the HUD has none of its own.
    var quickHud = document.createElement('div');
    quickHud.id = 'trace-quick-hud';
    var quickHudMaterialWrap = document.createElement('div');
    var quickHudMaterialLabel = document.createElement('label');
    quickHudMaterialLabel.textContent = 'Material';
    var quickHudMaterialSelect = document.createElement('select');
    quickHudMaterialWrap.appendChild(quickHudMaterialLabel);
    quickHudMaterialWrap.appendChild(quickHudMaterialSelect);
    var quickHudFieldsWrap = document.createElement('div');
    quickHud.appendChild(quickHudMaterialWrap);
    quickHud.appendChild(quickHudFieldsWrap);
    canvasWrapEl.appendChild(quickHud);

    var QUICK_HUD_FIELD_ID_MAP = {
        stud_spacing_in: 'inspector-stud-spacing-input',
        wall_height_in: 'inspector-wall-height-input',
        spacing_in: 'inspector-spacing-input',
    };

    function quickHudPrimaryFields(toolType, settings) {
        var isOpenPolyline = toolType === 'polyline' && !(settings || {}).closed;
        if (toolType === 'line' || isOpenPolyline) {
            return [
                { key: 'stud_spacing_in', label: 'Stud spacing (in)', step: '1', value: (settings || {}).stud_spacing_in },
                { key: 'wall_height_in', label: 'Wall height (in)', step: '0.125', value: (settings || {}).wall_height_in },
            ];
        }
        if (toolType === 'area') {
            return [{ key: 'spacing_in', label: 'Spacing (in)', step: '1', value: (settings || {}).spacing_in }];
        }
        return [];
    }

    function canvasPointToWrapCoords(point) {
        var canvasRect = canvas.upperCanvasEl.getBoundingClientRect();
        var wrapRect = canvasWrapEl.getBoundingClientRect();
        var scaleX = canvasRect.width / canvas.width;
        var scaleY = canvasRect.height / canvas.height;
        return {
            x: canvasRect.left + point.x * scaleX - wrapRect.left + canvasWrapEl.scrollLeft,
            y: canvasRect.top + point.y * scaleY - wrapRect.top + canvasWrapEl.scrollTop,
        };
    }

    function positionQuickHud(obj) {
        var anchor = obj.traceGeometry && obj.traceGeometry[0];
        if (!anchor) {
            return;
        }
        var coords = canvasPointToWrapCoords(anchor);
        quickHud.style.left = (coords.x + 14) + 'px';
        quickHud.style.top = (coords.y - 14) + 'px';
    }

    function showQuickHud(obj) {
        if (!obj) {
            return;
        }
        quickHudMaterialSelect.innerHTML = materialSelect.innerHTML;
        quickHudMaterialSelect.value = obj.traceMaterialId || '';
        quickHudFieldsWrap.innerHTML = '';
        quickHudPrimaryFields(obj.traceToolType, obj.traceSettings).forEach(function (field) {
            var wrap = document.createElement('div');
            wrap.className = 'quick-hud-field';
            var label = document.createElement('label');
            label.textContent = field.label;
            var input = document.createElement('input');
            input.type = 'number';
            input.step = field.step;
            input.value = field.value || '';
            input.dataset.settingsKey = field.key;
            wrap.appendChild(label);
            wrap.appendChild(input);
            quickHudFieldsWrap.appendChild(wrap);
        });
        positionQuickHud(obj);
        quickHud.style.display = 'block';
    }

    function hideQuickHud() {
        quickHud.style.display = 'none';
    }

    quickHudMaterialSelect.addEventListener('change', function () {
        inspectorMaterialSelect.value = quickHudMaterialSelect.value;
        inspectorMaterialSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });
    quickHudFieldsWrap.addEventListener('input', function (event) {
        var input = event.target.closest('input[data-settings-key]');
        if (!input) {
            return;
        }
        var sidebarInput = document.getElementById(QUICK_HUD_FIELD_ID_MAP[input.dataset.settingsKey]);
        if (!sidebarInput) {
            return;
        }
        sidebarInput.value = input.value;
        sidebarInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    // ---- one-click opening placement ----
    function nearestWallSegment(pointer, maxDist) {
        var geometries = [];
        canvas.getObjects().forEach(function (obj) {
            if (!obj.traceId || obj.visible === false) {
                return;
            }
            if (obj.traceToolType !== 'line' && obj.traceToolType !== 'polyline') {
                return;
            }
            geometries.push(obj.traceGeometry || []);
        });
        return viewerHelpers.nearestSegmentProjection(geometries, pointer, maxDist);
    }

    function tryPlaceOpeningAtClick(pointer) {
        // One click on a wall = a full opening: centered at the click, aligned
        // to the wall, sized by the Width (in) setting. Falls back to the
        // classic two-click flow when uncalibrated, width is blank, or the
        // click is not near a wall.
        var widthInput = document.getElementById('rough-width-input');
        var widthIn = widthInput ? parseFloat(widthInput.value) : NaN;
        if (!scalePixelsPerFoot || !widthIn || widthIn <= 0) {
            return false;
        }
        var segment = nearestWallSegment(pointer, snapRadiusCanvasPx() * 2);
        if (!segment) {
            return false;
        }
        var halfPx = (widthIn / 12) * scalePixelsPerFoot / 2;
        finishTrace([
            { x: segment.point.x - segment.ux * halfPx, y: segment.point.y - segment.uy * halfPx },
            { x: segment.point.x + segment.ux * halfPx, y: segment.point.y + segment.uy * halfPx },
        ]);
        return true;
    }

    // ---------------------------------------------------------------- drawing

    canvas.on('mouse:down', function (opt) {
        if (activeTool === 'hand') {
            isPanning = true;
            panStart = {
                x: opt.e.clientX, y: opt.e.clientY,
                scrollLeft: canvasWrapEl.scrollLeft, scrollTop: canvasWrapEl.scrollTop,
            };
            canvas.defaultCursor = 'grabbing';
            canvas.setCursor('grabbing');
            return;
        }
        if (!activeTool) {
            return;
        }
        var pointer = canvas.getPointer(opt.e);
        if (activeTool === 'calibrate') {
            handleCalibrateClick(pointer);
            return;
        }
        var config = TOOLS[activeTool];
        if (activeTool === 'opening' && pendingPoints.length === 0 && tryPlaceOpeningAtClick(pointer)) {
            return;
        }
        pointer = applyDrawingSnaps(pointer, opt.e);
        pendingPoints.push({ x: pointer.x, y: pointer.y });
        drawPendingMarkers();

        if (activeTool === 'area' && pendingPoints.length === 2) {
            // Two opposite corners -> closed rectangle
            var a = pendingPoints[0];
            var b = pendingPoints[1];
            finishTrace([a, { x: b.x, y: a.y }, b, { x: a.x, y: b.y }]);
        } else if (config.maxPoints && pendingPoints.length >= config.maxPoints) {
            finishTrace(pendingPoints.slice());
        }
    });

    canvas.on('mouse:move', function (opt) {
        if (activeTool === 'hand') {
            if (isPanning && panStart) {
                canvasWrapEl.scrollLeft = panStart.scrollLeft - (opt.e.clientX - panStart.x);
                canvasWrapEl.scrollTop = panStart.scrollTop - (opt.e.clientY - panStart.y);
            }
            return;
        }
        if (!activeTool || pendingPoints.length === 0 || activeTool === 'count') {
            return;
        }
        var pointer = applyDrawingSnaps(canvas.getPointer(opt.e), opt.e);
        updateMeasureReadout(pointer, opt.e);
        var start = pendingPoints[0];
        removePreview();
        if (activeTool === 'area') {
            previewObject = new fabric.Rect({
                left: Math.min(start.x, pointer.x), top: Math.min(start.y, pointer.y),
                width: Math.abs(pointer.x - start.x), height: Math.abs(pointer.y - start.y),
                fill: 'rgba(111, 66, 193, 0.15)', stroke: '#6f42c1', strokeDashArray: [6, 4],
                selectable: false, evented: false,
            });
        } else if (activeTool === 'polyline') {
            previewObject = new fabric.Polyline(pendingPoints.concat([{ x: pointer.x, y: pointer.y }]), {
                fill: '', stroke: colorInput.value, strokeDashArray: [6, 4], strokeWidth: 2,
                selectable: false, evented: false,
            });
        } else {
            previewObject = new fabric.Line([start.x, start.y, pointer.x, pointer.y], {
                stroke: '#6c757d', strokeDashArray: [6, 4], strokeWidth: 2,
                selectable: false, evented: false,
            });
        }
        canvas.add(previewObject);
        canvas.requestRenderAll();
    });

    canvas.on('mouse:dblclick', function () {
        finishMultiPointIfPending();
    });

    canvas.on('mouse:up', function () {
        if (activeTool === 'hand') {
            isPanning = false;
            panStart = null;
            canvas.defaultCursor = 'grab';
            canvas.setCursor('grab');
        }
    });

    // ------------------------------------------------- context menu
    // Right-click on a trace surfaces the handful of actions that already
    // have buttons/shortcuts elsewhere (duplicate, select similar, apply the
    // armed tool setup, delete), directly under the cursor.
    var traceContextMenu = document.getElementById('trace-context-menu');
    var contextMenuTarget = null;

    function hideTraceContextMenu() {
        traceContextMenu.style.display = 'none';
        contextMenuTarget = null;
    }

    function selectSimilarTraces(obj) {
        var matches = canvas.getObjects().filter(function (candidate) {
            return candidate.traceId
                && candidate.traceToolType === obj.traceToolType
                && String(candidate.traceMaterialId || '') === String(obj.traceMaterialId || '');
        }).map(function (candidate) { return candidate.traceId; });
        activateLinkedTraceIds(matches);
    }

    function showTraceContextMenu(clientX, clientY, target) {
        contextMenuTarget = target;
        var isGroupTarget = linkedTraceIds.length > 1 && linkedTraceIds.indexOf(target.traceId) !== -1;
        var duplicateItem = traceContextMenu.querySelector('[data-action="duplicate"]');
        var selectSimilarItem = traceContextMenu.querySelector('[data-action="select-similar"]');
        var applyToolItem = traceContextMenu.querySelector('[data-action="apply-tool-setup"]');
        var deleteItem = traceContextMenu.querySelector('[data-action="delete"]');
        duplicateItem.style.display = isGroupTarget ? 'none' : '';
        selectSimilarItem.style.display = isGroupTarget ? 'none' : '';
        applyToolItem.style.display = canApplyToolSetupToLinked() ? '' : 'none';
        deleteItem.textContent = isGroupTarget ? 'Delete linked (' + linkedTraceIds.length + ')' : 'Delete';

        traceContextMenu.style.display = 'block';
        // Clamp so the menu never renders past the viewport edge.
        var menuRect = traceContextMenu.getBoundingClientRect();
        var left = Math.min(clientX, window.innerWidth - menuRect.width - 8);
        var top = Math.min(clientY, window.innerHeight - menuRect.height - 8);
        traceContextMenu.style.left = Math.max(8, left) + 'px';
        traceContextMenu.style.top = Math.max(8, top) + 'px';
    }

    canvas.upperCanvasEl.addEventListener('contextmenu', function (event) {
        event.preventDefault();
        // Tools stay armed between draws (persistent draw mode), so "a tool
        // is active" is the normal state, not a reason to suppress the menu.
        // Only an in-progress multi-point shape (mid-polyline, etc.) should
        // block it, the same way Escape treats a pending shape specially.
        if (pendingPoints.length > 0) {
            return;
        }
        var target = canvas.findTarget(event, false);
        if (!target || !target.traceId) {
            hideTraceContextMenu();
            return;
        }
        var currentSelectionIds = canvasSelectionTraceObjects(canvas.getActiveObject())
            .map(function (obj) { return obj.traceId; });
        if (currentSelectionIds.indexOf(target.traceId) === -1) {
            selectTraceObject(target);
        }
        showTraceContextMenu(event.clientX, event.clientY, target);
    });

    document.addEventListener('click', function (event) {
        if (traceContextMenu.style.display !== 'none' && !traceContextMenu.contains(event.target)) {
            hideTraceContextMenu();
        }
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            hideTraceContextMenu();
        }
    });

    traceContextMenu.addEventListener('click', function (event) {
        var button = event.target.closest('[data-action]');
        if (!button || !contextMenuTarget) {
            return;
        }
        var action = button.dataset.action;
        var target = contextMenuTarget;
        var wasGroupTarget = linkedTraceIds.length > 1 && linkedTraceIds.indexOf(target.traceId) !== -1;
        hideTraceContextMenu();
        if (action === 'duplicate') {
            duplicateTrace(target);
        } else if (action === 'select-similar') {
            selectSimilarTraces(target);
        } else if (action === 'apply-tool-setup') {
            applyCurrentToolSetupToLinkedTraces();
        } else if (action === 'delete') {
            if (wasGroupTarget) {
                deleteLinkedTraces();
            } else {
                deleteTrace(target);
            }
        }
    });

    // ------------------------------------------------- keyboard shortcuts
    // Single keys arm tools without mousing to the sidebar. Keys with several
    // variants cycle on repeat press (W: exterior -> interior bearing ->
    // interior non-bearing, O: window -> door, B: flush -> dropped); a repeat
    // press of a single-variant key toggles the tool off, matching the
    // buttons' own toggle behavior. All of it reuses the buttons' click
    // handlers, so variant filters, default assemblies, and tool memory all
    // apply exactly as if clicked.
    var SHORTCUT_CYCLES = {
        w: TOOLBAR_SELECTOR + ' [data-semantic="wall"]',
        o: TOOLBAR_SELECTOR + ' [data-semantic="opening"]',
        b: TOOLBAR_SELECTOR + ' [data-semantic="beam"]',
    };
    var SHORTCUT_SINGLES = {
        m: '#measure-tool-button',
        j: TOOLBAR_SELECTOR + ' [data-semantic="joist"]',
        c: TOOLBAR_SELECTOR + ' [data-semantic="column"]',
        p: TOOLBAR_SELECTOR + ' [data-semantic="plate"]',
        r: TOOLBAR_SELECTOR + ' [data-semantic="rim_board"]',
        h: TOOLBAR_SELECTOR + ' .tool-btn[data-tool="hand"]',
    };

    function isTypingTarget(target) {
        if (!target) {
            return false;
        }
        var tag = (target.tagName || '').toLowerCase();
        return tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable;
    }

    function handleToolShortcut(key) {
        if (SHORTCUT_CYCLES[key]) {
            var buttons = document.querySelectorAll(SHORTCUT_CYCLES[key]);
            if (!buttons.length) {
                return false;
            }
            var activeIndex = -1;
            buttons.forEach(function (button, index) {
                if (button.classList.contains('active')) {
                    activeIndex = index;
                }
            });
            buttons[(activeIndex + 1) % buttons.length].click();
            return true;
        }
        if (SHORTCUT_SINGLES[key]) {
            var button = document.querySelector(SHORTCUT_SINGLES[key]);
            if (button) {
                button.click();
                return true;
            }
        }
        return false;
    }

    function toolSourceButton(tool, semanticKey, variantFilter) {
        if (semanticKey === 'wall' && variantFilter && variantFilter.wallSubtype) {
            return document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="wall"][data-wall-subtype="' + variantFilter.wallSubtype + '"]');
        }
        if (semanticKey === 'opening' && variantFilter && variantFilter.openingKind) {
            return document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="opening"][data-opening-kind="' + variantFilter.openingKind + '"]');
        }
        if (semanticKey === 'beam' && variantFilter && variantFilter.beamType) {
            return document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="beam"][data-beam-type="' + variantFilter.beamType + '"]');
        }
        if (semanticKey) {
            return document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="' + semanticKey + '"]');
        }
        if (tool === 'calibrate') {
            return headerCalibrateButton;
        }
        return document.querySelector(TOOLBAR_SELECTOR + ' .tool-btn[data-tool="' + tool + '"]');
    }

    function toolSettingsFieldsForHandoff(tool, semanticKey) {
        if (semanticKey && SEMANTIC_TOOLS[semanticKey]) {
            return SEMANTIC_TOOLS[semanticKey].settingsFields;
        }
        return null;
    }

    function pageHandoffKey() {
        return PROJECT_ID ? ('plan-viewer-page-handoff:' + PROJECT_ID) : null;
    }

    function currentToolHandoffState() {
        if (!activeTool) {
            return null;
        }
        return {
            tool: activeTool,
            semanticKey: activeSemanticKey || null,
            variantFilter: activeVariantFilter || null,
            variantLabel: activeSemanticKey && SEMANTIC_TOOLS[activeSemanticKey]
                ? SEMANTIC_TOOLS[activeSemanticKey].label
                : null,
            settings: TOOLS[activeTool] ? collectSettings(activeTool, '') : {},
            assemblyId: assemblySelect.value || '',
            materialId: materialSelect.value || '',
            color: colorInput.value || '',
        };
    }

    function storePageHandoffState() {
        var key = pageHandoffKey();
        var payload = currentToolHandoffState();
        if (!key) {
            return;
        }
        try {
            if (payload) {
                window.sessionStorage.setItem(key, JSON.stringify(payload));
            } else {
                window.sessionStorage.removeItem(key);
            }
        } catch (e) { /* storage unavailable */ }
    }

    function clearPageHandoffState() {
        var key = pageHandoffKey();
        if (!key) {
            return;
        }
        try {
            window.sessionStorage.removeItem(key);
        } catch (e) { /* storage unavailable */ }
    }

    function loadPageHandoffState() {
        var key = pageHandoffKey();
        if (!key) {
            return null;
        }
        try {
            var raw = window.sessionStorage.getItem(key);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    function applyHandoffSetupValues(payload) {
        if (!payload) {
            return;
        }
        applyToolSettings(payload.settings || {});
        if (payload.color) {
            colorInput.value = payload.color;
        }
        if (optionExists(materialSelect, payload.materialId)) {
            materialSelect.value = payload.materialId || '';
        }
        if (optionExists(assemblySelect, payload.assemblyId)) {
            assemblySelect.value = payload.assemblyId || '';
        }
        if (activeTool && TOOLS[activeTool]) {
            saveToolMemory(activeTool, activeVariantFilter, activeSemanticKey);
            updateToolMemoryUi(activeTool, activeVariantFilter, activeSemanticKey);
        }
        lastMeasurement.textContent = 'Continued your last tool setup on this page.';
    }

    function applyPageHandoffState() {
        var payload = loadPageHandoffState();
        if (!payload || !payload.tool) {
            return;
        }
        pendingPageHandoff = null;
        activeSemanticKey = payload.semanticKey || null;
        activateTool(
            payload.tool,
            payload.variantFilter || null,
            payload.variantLabel || null,
            toolSourceButton(payload.tool, payload.semanticKey, payload.variantFilter),
            toolSettingsFieldsForHandoff(payload.tool, payload.semanticKey)
        );
        if (activeTool === 'calibrate') {
            pendingPageHandoff = payload;
            return;
        }
        applyHandoffSetupValues(payload);
        clearPageHandoffState();
    }

    function navigateToSiblingPage(direction) {
        var current = document.querySelector('#page-strip .page-strip-item.is-current');
        if (!current) {
            return false;
        }
        var sibling = direction < 0 ? current.previousElementSibling : current.nextElementSibling;
        if (!sibling || !sibling.href) {
            return false;
        }
        storePageHandoffState();
        window.location.href = sibling.href;
        return true;
    }

    function syncPageNavButtons() {
        var current = document.querySelector('#page-strip .page-strip-item.is-current');
        if (!current) {
            if (prevPageButton) {
                prevPageButton.disabled = true;
            }
            if (nextPageButton) {
                nextPageButton.disabled = true;
            }
            return;
        }
        if (prevPageButton) {
            prevPageButton.disabled = !current.previousElementSibling;
        }
        if (nextPageButton) {
            nextPageButton.disabled = !current.nextElementSibling;
        }
    }

    document.addEventListener('keydown', function (event) {
        // Backspace while drawing: undo the last vertex instead of losing the
        // whole in-progress shape (a misclick no longer costs the wall).
        if (event.key === 'Backspace' && !isTypingTarget(event.target) && pendingPoints.length > 0) {
            event.preventDefault();
            pendingPoints.pop();
            var lastMarker = pendingMarkers.pop();
            if (lastMarker) {
                canvas.remove(lastMarker);
            }
            removePreview();
            measureReadout.hidden = true;
            canvas.requestRenderAll();
            return;
        }
        // Tool shortcuts: plain single keys only. Never while typing in a
        // field, and never when a modifier is held (Ctrl+R, Cmd+W, etc. stay
        // browser shortcuts).
        if (!isTypingTarget(event.target) && !event.ctrlKey && !event.metaKey && !event.altKey) {
            if (event.key.toLowerCase() === 'd' && selectedTrace) {
                event.preventDefault();
                duplicateTrace(selectedTrace);
                return;
            }
            if (handleToolShortcut(event.key.toLowerCase())) {
                event.preventDefault();
                return;
            }
        }
        if (event.key === 'Escape') {
            // Escape finishes the in-progress shape (keeping every point
            // already placed) wherever that's meaningful - e.g. a multi-
            // segment wall polyline - falling back to a full cancel when
            // there's nothing yet worth keeping (below the tool's minimum
            // point count). Leaving a draw tool drops into Hand mode so the
            // user can pan immediately without another click.
            if (finishMultiPointIfPending()) {
                if (activeTool && activeTool !== 'hand') {
                    switchToHandTool();
                }
            } else if (pendingPoints.length > 0) {
                resetPending();
                if (activeTool && activeTool !== 'hand') {
                    switchToHandTool();
                }
            } else if (activeTool) {
                switchToHandTool();
            } else if (linkedTraceIds.length) {
                clearLinkedSelection();
            }
        } else if (!isTypingTarget(event.target) && event.key === '[') {
            if (linkedTraceIds.length > 1) {
                event.preventDefault();
                cycleLinkedTrace(-1);
            }
        } else if (!isTypingTarget(event.target) && event.key === ']') {
            if (linkedTraceIds.length > 1) {
                event.preventDefault();
                cycleLinkedTrace(1);
            }
        } else if (!isTypingTarget(event.target) && event.key === 'PageUp') {
            if (navigateToSiblingPage(-1)) {
                event.preventDefault();
            }
        } else if (!isTypingTarget(event.target) && event.key === 'PageDown') {
            if (navigateToSiblingPage(1)) {
                event.preventDefault();
            }
        } else if (event.key === 'Enter') {
            finishMultiPointIfPending();
        }
    });

    if (prevPageButton) {
        prevPageButton.addEventListener('click', function () {
            if (ZOOM_STORAGE_KEY) {
                window.sessionStorage.removeItem(ZOOM_STORAGE_KEY);
            }
            navigateToSiblingPage(-1);
        });
    }

    if (nextPageButton) {
        nextPageButton.addEventListener('click', function () {
            if (ZOOM_STORAGE_KEY) {
                window.sessionStorage.removeItem(ZOOM_STORAGE_KEY);
            }
            navigateToSiblingPage(1);
        });
    }

    document.querySelectorAll('#page-strip .page-strip-item').forEach(function (link) {
        link.addEventListener('click', function () {
            storePageHandoffState();
        });
    });

    syncPageNavButtons();

    function finishMultiPointIfPending() {
        if (activeTool === 'count' && pendingPoints.length >= 1) {
            finishTrace(pendingPoints.slice());
            return true;
        } else if (activeTool === 'polyline') {
            // A Wall-flavored polyline is always open (see collectSettings) -
            // the raw closed-area checkbox only applies to a plain Polyline trace.
            var isClosed = activeSemanticKey !== 'wall' && closedInput.checked;
            var minimum = isClosed ? 3 : 2;
            if (pendingPoints.length >= minimum) {
                finishTrace(pendingPoints.slice());
                return true;
            }
        }
        return false;
    }

    function switchToHandTool() {
        activeSemanticKey = null;
        activateTool('hand', null, null, toolSourceButton('hand'));
    }

    function finishTrace(geometry) {
        var tool = activeTool;
        resetPending();
        if (tool === 'measure') {
            showMeasuredDimension(geometry);
            return;
        }
        createTrace(tool, geometry);
    }

    function showMeasuredDimension(geometry) {
        if (!geometry || geometry.length < 2 || !scalePixelsPerFoot) {
            return;
        }
        var start = geometry[0];
        var end = geometry[geometry.length - 1];
        var feet = Math.hypot(end.x - start.x, end.y - start.y) / scalePixelsPerFoot;
        var decimalFeet = (Math.round(feet * 100) / 100).toFixed(2);
        lastMeasurement.textContent = 'Verified: ' + formatFeetInches(feet) + ' (' + decimalFeet + ' ft)';
    }

    var pendingMarkers = [];

    function drawPendingMarkers() {
        var point = pendingPoints[pendingPoints.length - 1];
        var marker = new fabric.Circle({
            left: point.x - 4, top: point.y - 4, radius: 4,
            fill: activeTool === 'count' ? '#fd7e14' : (activeTool === 'measure' ? '#6c757d' : colorInput.value),
            selectable: false, evented: false,
        });
        pendingMarkers.push(marker);
        canvas.add(marker);
        canvas.requestRenderAll();
    }

    function resetPending() {
        pendingPoints = [];
        measureReadout.hidden = true;
        removePreview();
        pendingMarkers.forEach(function (marker) { canvas.remove(marker); });
        pendingMarkers = [];
        canvas.requestRenderAll();
    }

    function removePreview() {
        if (previewObject) {
            canvas.remove(previewObject);
            previewObject = null;
        }
    }

    // ------------------------------------------------------------- calibrate

    var calibratePoints = [];

    function onCalibrated(data) {
        isCalibrated = true;
        if (data && data.scale_pixels_per_foot) {
            scalePixelsPerFoot = parseFloat(data.scale_pixels_per_foot) || scalePixelsPerFoot;
        }
        calibrationStatus.textContent = 'Calibrated';
        calibrationStatus.classList.remove('badge-status-archived');
        calibrationStatus.classList.add('badge-status-active');
        // If the calibrate panel was reached via the guard (user armed a
        // measuring tool on an uncalibrated page), pick up right where they
        // meant to be: re-arm that tool with its original variant. isCalibrated
        // is now true, so this activation passes straight through the guard.
        if (pendingToolActivation) {
            var pending = pendingToolActivation;
            pendingToolActivation = null;
            activateTool(
                pending.tool, pending.variantFilter, pending.variantLabel,
                pending.sourceButton, pending.settingsFieldsOverride,
            );
            if (pendingPageHandoff && activeTool && TOOLS[activeTool]) {
                applyHandoffSetupValues(pendingPageHandoff);
                pendingPageHandoff = null;
                clearPageHandoffState();
            }
            return;
        }
        activateTool(null);
        if (pendingPageHandoff) {
            pendingPageHandoff = null;
            clearPageHandoffState();
        }
    }

    function handleCalibrateClick(pointer) {
        calibratePoints.push({ x: pointer.x, y: pointer.y });
        if (calibratePoints.length < 2) {
            return;
        }
        var geometry = calibratePoints.slice();
        calibratePoints = [];
        var knownLengthFt = window.prompt('What is the real-world length of that line, in feet?');
        if (!knownLengthFt) {
            return;
        }
        fetch(CALIBRATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ geometry: geometry, known_length_ft: knownLengthFt }),
        })
            .then(handleJsonResponse)
            .then(onCalibrated)
            .catch(showError);
    }

    // Alternative to drawing a line: pick the drawing's stated print scale
    // directly (e.g. "1/4 in = 1 ft") - the backend derives pixels-per-foot
    // from that plus the page's known rasterization DPI, no line needed.
    // Only accurate for pages imported from a PDF at native scale (see the
    // panel copy and PlanPageCalibrateView's docstring).
    if (applyScalePresetButton) {
        applyScalePresetButton.addEventListener('click', function () {
            var scaleInchesPerFoot = scalePresetSelect.value;
            if (!scaleInchesPerFoot) {
                return;
            }
            fetch(CALIBRATE_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                body: JSON.stringify({ scale_inches_per_foot: scaleInchesPerFoot }),
            })
                .then(handleJsonResponse)
                .then(onCalibrated)
                .catch(showError);
        });
    }

    // ------------------------------------------------------------- selection

    canvas.on('selection:created', onTraceSelected);
    canvas.on('selection:updated', onTraceSelected);
    canvas.on('selection:cleared', onTraceDeselected);

    function canvasSelectionTraceObjects(obj) {
        if (!obj) {
            return [];
        }
        if (obj.traceId) {
            return [obj];
        }
        if (typeof obj.getObjects === 'function') {
            return obj.getObjects().filter(function (item) {
                return item && item.traceId;
            });
        }
        return [];
    }

    function traceTypeSummary(objects) {
        var labels = {};
        objects.forEach(function (obj) {
            var label = ((TOOLS[obj.traceToolType] || TOOLS.line).label || 'Trace');
            labels[label] = true;
        });
        return Object.keys(labels);
    }

    function renderBulkSelectionPanel(objects) {
        if (!objects || !objects.length) {
            return;
        }
        var count = objects.length;
        var labels = traceTypeSummary(objects);
        var sameType = labels.length === 1;
        bulkSelectionTitle.textContent = 'Bulk edit ' + count + ' trace' + (count === 1 ? '' : 's');
        bulkSelectionSummary.textContent = sameType
            ? ('All selected traces are ' + labels[0].toLowerCase() + ' elements.')
            : ('Mixed trace types selected: ' + labels.join(', ') + '.');

        var materialIds = objects.map(function (obj) { return String(obj.traceMaterialId || ''); });
        var uniqueMaterialIds = Array.from(new Set(materialIds));
        bulkMaterialSelect.value = uniqueMaterialIds.length === 1 ? uniqueMaterialIds[0] : '';
        bulkMaterialToggle.checked = uniqueMaterialIds.length === 1 && Boolean(uniqueMaterialIds[0]);

        var colors = objects.map(function (obj) {
            return obj.traceColor || ((TOOLS[obj.traceToolType] || TOOLS.line).color);
        });
        var uniqueColors = Array.from(new Set(colors));
        bulkColorInput.value = uniqueColors[0] || '#0d6efd';
        bulkColorToggle.checked = uniqueColors.length === 1;

        if (sameType) {
            var first = objects[0];
            bulkAssemblyWrap.style.display = '';
            populateAssemblyOptions(bulkAssemblySelect, first.traceToolType, first.traceSettings || {});
            var assemblyIds = objects.map(function (obj) { return String(obj.traceAssemblyId || ''); });
            var uniqueAssemblyIds = Array.from(new Set(assemblyIds));
            bulkAssemblySelect.value = uniqueAssemblyIds.length === 1 ? uniqueAssemblyIds[0] : '';
            bulkAssemblyToggle.checked = uniqueAssemblyIds.length === 1 && Boolean(uniqueAssemblyIds[0]);
        } else {
            bulkAssemblyWrap.style.display = 'none';
            bulkAssemblyToggle.checked = false;
            bulkAssemblySelect.innerHTML = '';
        }
    }

    // --------------------------------------------------- vertex drag editing
    // Selecting a line/polyline trace shows small draggable grips at each of
    // its points. Dragging rebuilds a dashed ghost preview live (reusing
    // buildTraceObject rather than mutating the real Fabric shape's own
    // points array, which is fragile for Polyline); the real trace is only
    // PATCHed - and its Fabric object rebuilt from the server's answer -
    // once a grip is released.

    function clearVertexHandles() {
        vertexHandles.forEach(function (handle) { canvas.remove(handle); });
        vertexHandles = [];
        if (vertexGhost) {
            canvas.remove(vertexGhost);
            vertexGhost = null;
        }
    }

    function exitVertexEditMode() {
        if (vertexEditObj) {
            vertexEditObj.set({ opacity: 1 });
        }
        clearVertexHandles();
        vertexEditObj = null;
        canvas.requestRenderAll();
    }

    function enterVertexEditMode(obj) {
        exitVertexEditMode();
        if (!obj || (obj.traceToolType !== 'line' && obj.traceToolType !== 'polyline')) {
            return;
        }
        vertexEditObj = obj;
        obj.set({ opacity: 0.3 });
        vertexHandles = (obj.traceGeometry || []).map(function (point, index) {
            var handle = new fabric.Circle({
                left: point.x, top: point.y, radius: 6, fill: '#ffffff',
                stroke: '#0d6efd', strokeWidth: 2, originX: 'center', originY: 'center',
                hasControls: false, hasBorders: false, selectable: true, hoverCursor: 'move',
                lockScalingX: true, lockScalingY: true, lockRotation: true,
                traceVertexHandle: true, vertexIndex: index,
            });
            canvas.add(handle);
            return handle;
        });
        canvas.requestRenderAll();
    }

    function rebuildVertexGhost() {
        if (!vertexEditObj) {
            return;
        }
        if (vertexGhost) {
            canvas.remove(vertexGhost);
        }
        var geometry = vertexHandles.map(function (handle) { return { x: handle.left, y: handle.top }; });
        vertexGhost = buildTraceObject({
            tool_type: vertexEditObj.traceToolType, geometry: geometry,
            settings: vertexEditObj.traceSettings || {},
            color: vertexEditObj.traceColor || TOOLS[vertexEditObj.traceToolType].color,
        });
        vertexGhost.set({ selectable: false, evented: false, strokeDashArray: [8, 4] });
        canvas.add(vertexGhost);
        vertexHandles.forEach(function (handle) { canvas.bringToFront(handle); });
        canvas.requestRenderAll();
    }

    function finishVertexDrag() {
        if (!vertexEditObj) {
            return;
        }
        var obj = vertexEditObj;
        var geometry = vertexHandles.map(function (handle) {
            return { x: Math.round(handle.left), y: Math.round(handle.top) };
        });
        var payload = {
            material_id: obj.traceMaterialId || null,
            assembly_id: obj.traceAssemblyId || null,
            parent_wall_id: obj.traceParentWallId || null,
            color: obj.traceColor || '',
            settings: obj.traceSettings || {},
            geometry: geometry,
        };
        persistTraceUpdate(obj, payload)
            .then(function (trace) {
                exitVertexEditMode();
                canvas.remove(obj);
                var fresh = drawTrace(trace);
                refreshMaterialList();
                selectTraceObject(fresh);
            })
            .catch(function (error) {
                exitVertexEditMode();
                showError(error);
            });
    }

    canvas.on('object:moving', function (opt) {
        if (opt.target && opt.target.traceVertexHandle) {
            rebuildVertexGhost();
        }
    });
    canvas.on('object:modified', function (opt) {
        if (opt.target && opt.target.traceVertexHandle) {
            finishVertexDrag();
        }
    });

    // ------------------------------------------------- automatic wall joining
    // The calc engine already treats wall endpoints within JUNCTION_TOLERANCE_FT
    // (0.5 ft, plans/wall_junctions.py) as touching for corner/T-stud counting,
    // but a small drafting gap still looks wrong on screen. This is a purely
    // cosmetic snap - it never changes a material quantity that wasn't already
    // being counted as joined.
    var WALL_JOIN_TOLERANCE_FT = 0.5;

    function wallEndpoints() {
        var points = [];
        canvas.getObjects().forEach(function (obj) {
            if (!obj.traceId || (obj.traceToolType !== 'line' && obj.traceToolType !== 'polyline')) {
                return;
            }
            var geometry = obj.traceGeometry || [];
            if (geometry.length < 2) {
                return;
            }
            points.push({ obj: obj, pointIndex: 0, x: geometry[0].x, y: geometry[0].y });
            var lastIndex = geometry.length - 1;
            points.push({ obj: obj, pointIndex: lastIndex, x: geometry[lastIndex].x, y: geometry[lastIndex].y });
        });
        return points;
    }

    function findNearbyWallGaps() {
        if (!scalePixelsPerFoot) {
            return [];
        }
        var toleranceInPx = WALL_JOIN_TOLERANCE_FT * scalePixelsPerFoot;
        var points = wallEndpoints();
        var claimed = {};
        var merges = [];
        for (var i = 0; i < points.length; i++) {
            var a = points[i];
            var aKey = a.obj.traceId + ':' + a.pointIndex;
            if (claimed[aKey]) {
                continue;
            }
            for (var j = i + 1; j < points.length; j++) {
                var b = points[j];
                if (b.obj.traceId === a.obj.traceId) {
                    continue;
                }
                var bKey = b.obj.traceId + ':' + b.pointIndex;
                if (claimed[bKey]) {
                    continue;
                }
                var dist = Math.hypot(a.x - b.x, a.y - b.y);
                if (dist > 0 && dist <= toleranceInPx) {
                    merges.push({ a: a, b: b, x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
                    claimed[aKey] = true;
                    claimed[bKey] = true;
                    break;
                }
            }
        }
        return merges;
    }

    function fixNearbyWallJoints() {
        var merges = findNearbyWallGaps();
        if (!merges.length) {
            lastMeasurement.textContent = 'No nearby wall gaps found on this page.';
            return;
        }
        var updatesByTraceId = {};
        merges.forEach(function (merge) {
            [merge.a, merge.b].forEach(function (endpoint) {
                var id = endpoint.obj.traceId;
                if (!updatesByTraceId[id]) {
                    updatesByTraceId[id] = {
                        obj: endpoint.obj,
                        geometry: (endpoint.obj.traceGeometry || []).map(function (p) { return { x: p.x, y: p.y }; }),
                    };
                }
                updatesByTraceId[id].geometry[endpoint.pointIndex] = { x: Math.round(merge.x), y: Math.round(merge.y) };
            });
        });
        // Sequential, not Promise.all: two walls that both end up on each
        // other's junction-regen pass (_regenerate_sibling_walls) can
        // deadlock in Postgres if their UPDATE transactions overlap - each
        // one locks its own LineItems first, then reaches for the other's.
        // Running the requests one at a time means each transaction commits
        // before the next starts, so the lock order can never cross.
        var traceIds = Object.keys(updatesByTraceId);
        var chain = Promise.resolve();
        traceIds.forEach(function (id) {
            chain = chain.then(function () {
                var entry = updatesByTraceId[id];
                var obj = entry.obj;
                var payload = {
                    material_id: obj.traceMaterialId || null,
                    assembly_id: obj.traceAssemblyId || null,
                    parent_wall_id: obj.traceParentWallId || null,
                    color: obj.traceColor || '',
                    settings: obj.traceSettings || {},
                    geometry: entry.geometry,
                };
                return persistTraceUpdate(obj, payload).then(function (trace) {
                    canvas.remove(obj);
                    drawTrace(trace);
                });
            });
        });
        chain
            .then(function () {
                canvas.requestRenderAll();
                refreshMaterialList();
                lastMeasurement.textContent = 'Closed ' + merges.length + ' nearby wall gap' + (merges.length === 1 ? '' : 's') + '.';
            })
            .catch(showError);
    }

    var fixWallJointsButton = document.getElementById('fix-wall-joints-button');
    if (fixWallJointsButton) {
        fixWallJointsButton.addEventListener('click', fixNearbyWallJoints);
    }

    function onTraceSelected() {
        var obj = canvas.getActiveObject();
        var selectedObjects = canvasSelectionTraceObjects(obj);
        if (!selectedObjects.length) {
            return;
        }
        if (selectedObjects.length > 1) {
            activateTool(null);
            exitVertexEditMode();
            hideQuickHud();
            selectedTrace = null;
            if (tracePersistTimer) {
                clearTimeout(tracePersistTimer);
                tracePersistTimer = null;
            }
            linkedTraceIds = selectedObjects.map(function (item) { return item.traceId; });
            activeMaterialSummary = null;
            activeLinkedTraceIndex = 0;
            syncMaterialListSelection();
            scrollMaterialRowIntoView(linkedTraceIds);
            updateMaterialToolbarState();
            renderBulkSelectionPanel(selectedObjects);
            showPanel('bulk');
            return;
        }
        obj = selectedObjects[0];
        activateTool(null);
        selectedTrace = obj;
        if (tracePersistTimer) {
            clearTimeout(tracePersistTimer);
            tracePersistTimer = null;
        }
        var config = TOOLS[obj.traceToolType] || TOOLS.line;
        inspectorSyncing = true;
        inspectorTitle.textContent = 'Selected ' + config.label;
        inspectorMeasurement.textContent = obj.traceMeasurement || '';
        var confidenceReason = incompleteReason(obj);
        inspectorConfidenceStatus.style.display = confidenceReason ? '' : 'none';
        inspectorConfidenceText.textContent = confidenceReason;
        inspectorMaterialSelect.value = obj.traceMaterialId || '';
        populateAssemblyOptions(inspectorAssemblySelect, obj.traceToolType, obj.traceSettings || {});
        inspectorAssemblySelect.value = obj.traceAssemblyId || '';
        inspectorParentWallWrap.style.display = obj.traceToolType === 'opening' ? '' : 'none';
        if (obj.traceToolType === 'opening') {
            populateParentWallOptions(inspectorParentWallSelect, obj.traceId);
            inspectorParentWallSelect.value = obj.traceParentWallId || '';
        }
        inspectorColorInput.value = obj.traceColor || config.color;
        viewWallElevationButton.style.display = (obj.traceToolType === 'line' || obj.traceToolType === 'polyline') ? '' : 'none';
        renderInspectorSettings(obj.traceToolType, obj.traceSettings || {});
        updateInspectorSaveStatus('Changes save automatically.');
        inspectorSyncing = false;
        linkedTraceIds = [obj.traceId];
        activeLinkedTraceIndex = 0;
        syncMaterialListSelection();
        scrollMaterialRowIntoView(linkedTraceIds);
        updateMaterialToolbarState();
        showPanel('inspector');
        enterVertexEditMode(obj);
        showQuickHud(obj);
    }

    function renderInspectorSettings(toolType, settings) {
        // An open (non-closed) polyline is a Wall drawn via the polyline
        // tool (see SEMANTIC_TOOLS.wall) - it needs the exact same fields as
        // a 'line' wall. Only a closed polyline (area-type assembly) is
        // still just the plain "closed" toggle with no extra settings.
        var isOpenPolyline = toolType === 'polyline' && !settings.closed;
        var fields = [];
        if (toolType === 'line' || isOpenPolyline) {
            fields = [
                { id: 'inspector-stud-spacing-input', label: 'Stud spacing (in, OC)', value: settings.stud_spacing_in },
                {
                    id: 'inspector-wall-height-input', label: 'Wall height (in)',
                    value: settings.wall_height_in, step: '0.125',
                },
                { id: 'inspector-top-plate-count-input', label: 'Top plates', value: settings.top_plate_count || 2 },
                { id: 'inspector-bottom-plate-count-input', label: 'Bottom plates', value: settings.bottom_plate_count || 1 },
            ];
        } else if (toolType === 'area') {
            fields = [
                { id: 'inspector-spacing-input', label: 'Member spacing (in, OC)', value: settings.spacing_in },
            ];
        } else if (toolType === 'opening') {
            fields = [
                { id: 'inspector-sill-height-input', label: 'Sill height (in)', value: settings.sill_height_in },
                { id: 'inspector-rough-height-input', label: 'Rough height (in)', value: settings.rough_height_in },
                { id: 'inspector-header-depth-input', label: 'Header depth (in)', value: settings.header_depth_in },
                { id: 'inspector-stud-spacing-input', label: 'Cripple spacing (in, OC)', value: settings.stud_spacing_in },
            ];
        } else if (toolType === 'polyline') {
            inspectorSettingsWrap.innerHTML = '';
            appendPolylineClosedToggle(settings);
            return;
        }
        inspectorSettingsWrap.innerHTML = '';
        fields.forEach(function (field) {
            var wrap = document.createElement('div');
            wrap.className = 'mb-2';
            var label = document.createElement('label');
            label.className = 'form-label';
            label.htmlFor = field.id;
            label.textContent = field.label;
            var input = document.createElement('input');
            input.type = 'number';
            input.className = 'form-control';
            input.id = field.id;
            input.value = field.value || '';
            if (field.step) {
                input.step = field.step;
            }
            wrap.appendChild(label);
            wrap.appendChild(input);
            inspectorSettingsWrap.appendChild(wrap);
        });
        if (toolType === 'line' || isOpenPolyline) {
            var layerWrap = document.createElement('div');
            layerWrap.className = 'border rounded p-2 mb-2';
            layerWrap.innerHTML = '<p class="small fw-bold mb-1">Visible layers</p>' +
                inspectorCheckboxHtml('interior-drywall-input', 'Interior drywall', settings.interior_drywall !== false) +
                inspectorCheckboxHtml('exterior-sheathing-input', 'Exterior sheathing', settings.exterior_sheathing !== false) +
                inspectorCheckboxHtml('house-wrap-input', 'House wrap / WRB', settings.house_wrap !== false) +
                inspectorCheckboxHtml('siding-input', 'Siding / finish', settings.siding !== false);
            inspectorSettingsWrap.appendChild(layerWrap);
        }
        if (toolType === 'opening') {
            var typeWrap = document.createElement('div');
            typeWrap.className = 'mb-2';
            typeWrap.innerHTML = '<label class="form-label" for="inspector-opening-type-select">Opening type</label>' +
                '<select id="inspector-opening-type-select" class="form-select"><option value="window">Window</option><option value="door">Door</option></select>';
            inspectorSettingsWrap.insertBefore(typeWrap, inspectorSettingsWrap.firstChild);
            document.getElementById('inspector-opening-type-select').value = settings.opening_type || 'window';
        }
        if (toolType === 'area') {
            var wrap = document.createElement('div');
            wrap.className = 'mb-2';
            wrap.innerHTML = '<label class="form-label" for="inspector-direction-select">Members run</label>' +
                '<select id="inspector-direction-select" class="form-select">' +
                '<option value="horizontal">Horizontally (left-right)</option>' +
                '<option value="vertical">Vertically (up-down)</option></select>';
            inspectorSettingsWrap.appendChild(wrap);
            document.getElementById('inspector-direction-select').value = settings.member_direction || 'horizontal';
        }
        if (isOpenPolyline) {
            appendPolylineClosedToggle(settings);
        }
    }

    // Shared by both polyline branches above - lets a user flip a polyline
    // trace between wall-like (open) and area-like (closed), re-rendering
    // the settings panel immediately so the right fields show either way.
    function appendPolylineClosedToggle(settings) {
        var wrap = document.createElement('div');
        wrap.className = 'form-check mb-2';
        wrap.innerHTML = '<input type="checkbox" id="inspector-closed-input" class="form-check-input">' +
            '<label class="form-check-label" for="inspector-closed-input">Closed area (switch to an area-type assembly)</label>';
        inspectorSettingsWrap.appendChild(wrap);
        var checkbox = document.getElementById('inspector-closed-input');
        checkbox.checked = Boolean(settings.closed);
        checkbox.addEventListener('change', function () {
            var updated = collectInspectorSettings('polyline');
            populateAssemblyOptions(inspectorAssemblySelect, 'polyline', updated);
            renderInspectorSettings('polyline', updated);
        });
    }

    function inspectorCheckboxHtml(id, label, checked) {
        return '<div class="form-check"><input class="form-check-input" type="checkbox" id="inspector-' + id + '"' + (checked ? ' checked' : '') + '>' +
            '<label class="form-check-label" for="inspector-' + id + '">' + label + '</label></div>';
    }

    function checkboxValue(id) {
        var el = document.getElementById(id);
        return el ? el.checked : false;
    }

    function collectInspectorSettings(toolType) {
        var value = function (id) {
            var el = document.getElementById(id);
            return el ? parseInt(el.value, 10) || null : null;
        };
        var decimalValue = function (id) {
            var el = document.getElementById(id);
            return el ? parseFloat(el.value) || null : null;
        };
        var closedCheckbox = document.getElementById('inspector-closed-input');
        var isOpenPolyline = toolType === 'polyline' && closedCheckbox && !closedCheckbox.checked;
        if (toolType === 'line' || isOpenPolyline) {
            var wallSettings = {
                stud_spacing_in: value('inspector-stud-spacing-input'),
                wall_height_in: decimalValue('inspector-wall-height-input'),
                top_plate_count: value('inspector-top-plate-count-input') || 2,
                bottom_plate_count: value('inspector-bottom-plate-count-input') || 1,
                interior_drywall: checkboxValue('inspector-interior-drywall-input'),
                exterior_sheathing: checkboxValue('inspector-exterior-sheathing-input'),
                house_wrap: checkboxValue('inspector-house-wrap-input'),
                siding: checkboxValue('inspector-siding-input'),
                wall_member_overrides: (selectedTrace && selectedTrace.traceSettings && selectedTrace.traceSettings.wall_member_overrides) || {},
            };
            if (toolType === 'polyline') {
                wallSettings.closed = false;
            }
            return wallSettings;
        }
        if (toolType === 'area') {
            var direction = document.getElementById('inspector-direction-select');
            return { spacing_in: value('inspector-spacing-input'), member_direction: direction ? direction.value : 'horizontal' };
        }
        if (toolType === 'opening') {
            var openingType = document.getElementById('inspector-opening-type-select');
            return {
                opening_type: openingType ? openingType.value : 'window',
                sill_height_in: value('inspector-sill-height-input'),
                rough_height_in: value('inspector-rough-height-input'),
                header_depth_in: decimalValue('inspector-header-depth-input'),
                stud_spacing_in: value('inspector-stud-spacing-input'),
            };
        }
        if (toolType === 'polyline') {
            return { closed: closedCheckbox ? closedCheckbox.checked : true };
        }
        return {};
    }

    function onTraceDeselected() {
        if (tracePersistTimer) {
            clearTimeout(tracePersistTimer);
            tracePersistTimer = null;
        }
        exitVertexEditMode();
        hideQuickHud();
        selectedTrace = null;
        linkedTraceIds = [];
        activeMaterialSummary = null;
        activeLinkedTraceIndex = -1;
        syncMaterialListSelection();
        focusLinkedMode = false;
        updateMaterialToolbarState();
        showPanel(activeTool && TOOLS[activeTool] ? 'tool-settings' : 'none');
    }

    deleteButton.addEventListener('click', function () {
        var activeObj = canvas.getActiveObject();
        var selectedObjects = canvasSelectionTraceObjects(activeObj);
        if (selectedObjects.length > 1) {
            linkedTraceIds = selectedObjects.map(function (obj) { return obj.traceId; });
            deleteLinkedTraces();
            return;
        }
        deleteTrace(activeObj);
    });

    deleteInspectedButton.addEventListener('click', function () {
        deleteTrace(selectedTrace);
    });

    useTraceForNewButton.addEventListener('click', function () {
        useTraceForNewTraces(selectedTrace);
    });

    duplicateInspectedButton.addEventListener('click', function () {
        duplicateTrace(selectedTrace);
    });

    selectSimilarInspectedButton.addEventListener('click', function () {
        if (selectedTrace) {
            selectSimilarTraces(selectedTrace);
        }
    });

    viewWallElevationButton.addEventListener('click', function () {
        if (!selectedTrace) {
            return;
        }
        fetch(WALL_DETAIL_URL_BASE.replace('0', selectedTrace.traceId), {
            headers: { 'X-CSRFToken': csrftoken },
        })
            .then(handleJsonResponse)
            .then(showWallElevation)
            .catch(showError);
    });

    closeWallElevationButton.addEventListener('click', hideWallElevation);
    wallElevationBackdrop.addEventListener('click', hideWallElevation);

    // Detaching a wall clears the assembly selection too - otherwise a
    // previously auto-resolved (or manually picked) assembly would keep
    // getting resent as if it were still a deliberate choice, even though
    // the wall it was matched against no longer applies.
    inspectorParentWallSelect.addEventListener('change', function () {
        if (!inspectorParentWallSelect.value) {
            inspectorAssemblySelect.value = '';
        }
    });

    saveTraceChangesButton.addEventListener('click', function () {
        persistSelectedTraceChanges(true);
    });

    traceInspectorPanel.addEventListener('input', function (event) {
        if (inspectorSyncing || !selectedTrace || !isInspectorAutoSaveTarget(event.target)) {
            return;
        }
        scheduleSelectedTracePersist();
    });
    traceInspectorPanel.addEventListener('change', function (event) {
        if (inspectorSyncing || !selectedTrace || !isInspectorAutoSaveTarget(event.target)) {
            return;
        }
        scheduleSelectedTracePersist();
    });

    function isInspectorAutoSaveTarget(target) {
        return Boolean(target && target.id && (
            target.id.indexOf('inspector-') === 0 ||
            target.id === 'inspector-material-select' ||
            target.id === 'inspector-assembly-select' ||
            target.id === 'inspector-parent-wall-select' ||
            target.id === 'inspector-color-input'
        ));
    }

    function scheduleSelectedTracePersist() {
        if (!selectedTrace) {
            return;
        }
        if (tracePersistTimer) {
            clearTimeout(tracePersistTimer);
        }
        updateInspectorSaveStatus('Auto-save pending...');
        tracePersistTimer = setTimeout(function () {
            persistSelectedTraceChanges(false);
        }, 450);
    }

    function persistSelectedTraceChanges(force) {
        if (!selectedTrace) {
            return;
        }
        if (tracePersistTimer) {
            clearTimeout(tracePersistTimer);
            tracePersistTimer = null;
        }
        var nonce = ++tracePersistNonce;
        var toolType = selectedTrace.traceToolType;
        updateInspectorSaveStatus(force ? 'Saving now...' : 'Saving...');
        fetch(TRACE_UPDATE_URL_BASE.replace('0', selectedTrace.traceId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({
                material_id: inspectorMaterialSelect.value || null,
                assembly_id: inspectorAssemblySelect.value || null,
                parent_wall_id: toolType === 'opening' ? (inspectorParentWallSelect.value || null) : null,
                color: inspectorColorInput.value,
                settings: collectInspectorSettings(toolType),
            }),
        })
            .then(handleJsonResponse)
            .then(function (trace) {
                if (!selectedTrace || nonce !== tracePersistNonce) {
                    return;
                }
                selectedTrace.traceMaterialId = trace.material_id;
                selectedTrace.traceAssemblyId = trace.assembly_id;
                selectedTrace.traceParentWallId = trace.parent_wall_id;
                selectedTrace.traceColor = trace.color;
                selectedTrace.traceSettings = trace.settings || {};
                selectedTrace.traceMeasurement = trace.measurement_display || selectedTrace.traceMeasurement;
                restyleTrace(selectedTrace);
                updateIncompleteMarker(selectedTrace);
                canvas.requestRenderAll();
                inspectorMeasurement.textContent = selectedTrace.traceMeasurement || '';
                var confidenceReason = incompleteReason(selectedTrace);
                inspectorConfidenceStatus.style.display = confidenceReason ? '' : 'none';
                inspectorConfidenceText.textContent = confidenceReason;
                updateInspectorSaveStatus('Saved.');
                refreshMaterialList();
            })
            .catch(function (error) {
                updateInspectorSaveStatus('Auto-save failed. Use Save now to retry.');
                showError(error);
            });
    }

    function updateInspectorSaveStatus(message) {
        if (inspectorSaveStatus) {
            inspectorSaveStatus.textContent = message;
        }
    }

    function focusRequestedTrace() {
        var params = new URLSearchParams(window.location.search);
        var traceId = parseInt(params.get('trace'), 10);
        if (!traceId) {
            return;
        }
        var match = canvas.getObjects().find(function (obj) {
            return obj.traceId === traceId;
        });
        if (!match) {
            return;
        }
        canvas.setActiveObject(match);
        canvas.requestRenderAll();
        onTraceSelected();
    }

    function nearestWallSegment(pointer, maxDist) {
        var geometries = [];
        canvas.getObjects().forEach(function (obj) {
            if (!obj.traceId || obj.visible === false) {
                return;
            }
            if (obj.traceToolType !== 'line' && obj.traceToolType !== 'polyline') {
                return;
            }
            geometries.push(obj.traceGeometry || []);
        });
        return viewerHelpers.nearestSegmentProjection(geometries, pointer, maxDist);
    }    function getTraceObjectsByIds(traceIds) {
        return canvas.getObjects().filter(function (obj) {
            return obj.traceId && traceIds.indexOf(obj.traceId) !== -1;
        });
    }

    function traceSnapshotFromObject(obj) {
        if (!obj || !obj.traceId) {
            return null;
        }
        return {
            traceId: obj.traceId,
            toolType: obj.traceToolType,
            geometry: obj.traceGeometry || [],
            materialId: obj.traceMaterialId || null,
            assemblyId: obj.traceAssemblyId || null,
            parentWallId: obj.traceParentWallId || null,
            color: obj.traceColor || '',
            settings: JSON.parse(JSON.stringify(obj.traceSettings || {})),
            label: (TOOLS[obj.traceToolType] && TOOLS[obj.traceToolType].label) || 'Trace',
        };
    }

    function linkedTraceObjects() {
        return getTraceObjectsByIds(linkedTraceIds);
    }

    function canApplyToolSetupToLinked() {
        if (!activeTool || !TOOLS[activeTool] || !linkedTraceIds.length) {
            return false;
        }
        var matches = linkedTraceObjects();
        if (!matches.length) {
            return false;
        }
        return matches.every(function (obj) {
            return obj.traceToolType === activeTool;
        });
    }

    function persistTraceUpdate(obj, payload) {
        return fetch(TRACE_UPDATE_URL_BASE.replace('0', obj.traceId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify(payload),
        })
            .then(handleJsonResponse)
            .then(function (trace) {
                obj.traceMaterialId = trace.material_id;
                obj.traceAssemblyId = trace.assembly_id;
                obj.traceParentWallId = trace.parent_wall_id;
                obj.traceColor = trace.color;
                obj.traceSettings = trace.settings || {};
                obj.traceGeometry = trace.geometry || obj.traceGeometry;
                obj.traceMeasurement = trace.measurement_display || obj.traceMeasurement;
                restyleTrace(obj);
                updateIncompleteMarker(obj);
                canvas.requestRenderAll();
                return trace;
            });
    }

    function applyTracePayloadToObject(obj, trace) {
        obj.traceMaterialId = trace.material_id;
        obj.traceAssemblyId = trace.assembly_id;
        obj.traceParentWallId = trace.parent_wall_id;
        obj.traceColor = trace.color;
        obj.traceSettings = trace.settings || {};
        obj.traceMeasurement = trace.measurement_display || obj.traceMeasurement;
        restyleTrace(obj);
        updateIncompleteMarker(obj);
    }

    function persistTraceBatchUpdate(traceIds, payload) {
        return fetch(TRACE_BATCH_UPDATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify(Object.assign({ trace_ids: traceIds }, payload)),
        })
            .then(handleJsonResponse)
            .then(function (data) {
                var tracesById = {};
                (data.traces || []).forEach(function (trace) {
                    tracesById[trace.id] = trace;
                });
                canvas.getObjects().forEach(function (obj) {
                    if (obj.traceId && tracesById[obj.traceId]) {
                        applyTracePayloadToObject(obj, tracesById[obj.traceId]);
                    }
                });
                return data.traces || [];
            });
    }

    function persistTraceBatchDelete(traceIds) {
        return fetch(TRACE_BATCH_DELETE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ trace_ids: traceIds }),
        }).then(handleJsonResponse);
    }

    function applyCurrentToolSetupToLinkedTraces() {
        if (!canApplyToolSetupToLinked()) {
            return;
        }
        var matches = linkedTraceObjects();
        var settings = collectSettings(activeTool, '');
        persistTraceBatchUpdate(linkedTraceIds.slice(), {
            apply_material: true,
            material_id: materialSelect.value || null,
            apply_assembly: true,
            assembly_id: assemblySelect.value || null,
            apply_color: true,
            color: colorInput.value,
            apply_settings: true,
            settings: settings,
        })
            .then(function () {
                canvas.requestRenderAll();
                refreshMaterialList();
                lastMeasurement.textContent = 'Applied current tool setup to ' + matches.length + ' linked trace' + (matches.length === 1 ? '' : 's') + '.';
            })
            .catch(showError);
    }

    function applyBulkSelectionChanges() {
        var matches = linkedTraceObjects();
        if (!matches.length) {
            return;
        }
        persistTraceBatchUpdate(linkedTraceIds.slice(), {
            apply_material: bulkMaterialToggle.checked,
            material_id: bulkMaterialSelect.value || null,
            apply_assembly: bulkAssemblyWrap.style.display !== 'none' && bulkAssemblyToggle.checked,
            assembly_id: bulkAssemblySelect.value || null,
            apply_color: bulkColorToggle.checked,
            color: bulkColorInput.value,
            apply_settings: false,
        })
            .then(function () {
                canvas.requestRenderAll();
                refreshMaterialList();
                renderBulkSelectionPanel(linkedTraceObjects());
                lastMeasurement.textContent = 'Applied bulk changes to ' + matches.length + ' selected trace' + (matches.length === 1 ? '' : 's') + '.';
            })
            .catch(showError);
    }

    function assemblyById(assemblyId) {
        if (!assemblyId) {
            return null;
        }
        for (var i = 0; i < assembliesData.length; i += 1) {
            if (String(assembliesData[i].id) === String(assemblyId)) {
                return assembliesData[i];
            }
        }
        return null;
    }

    function isWallLikeTrace(snapshot, assembly) {
        var settings = snapshot.settings || {};
        return Boolean(
            (assembly && assembly.wall_subtype) ||
            (snapshot.toolType === 'polyline' && settings.closed === false) ||
            settings.wall_height_in || settings.top_plate_count || settings.bottom_plate_count
        );
    }

    function inferTraceToolSetup(snapshot) {
        var assembly = assemblyById(snapshot.assemblyId);
        var settings = snapshot.settings || {};
        var openingKind = (settings.opening_type || (assembly && assembly.opening_kind) || '').toLowerCase();
        if (snapshot.toolType === 'opening' && (openingKind === 'window' || openingKind === 'door')) {
            return {
                tool: 'opening',
                variantFilter: { openingKind: openingKind },
                variantLabel: 'Opening',
                sourceButton: document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="opening"][data-opening-kind="' + openingKind + '"]'),
                semanticKey: 'opening',
                settingsFieldsOverride: SEMANTIC_TOOLS.opening.settingsFields,
            };
        }
        if ((snapshot.toolType === 'line' || snapshot.toolType === 'polyline') && assembly && assembly.beam_type) {
            return {
                tool: 'line',
                variantFilter: { beamType: assembly.beam_type },
                variantLabel: 'Beam',
                sourceButton: document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="beam"][data-beam-type="' + assembly.beam_type + '"]'),
                semanticKey: 'beam',
                settingsFieldsOverride: SEMANTIC_TOOLS.beam.settingsFields,
            };
        }
        if ((snapshot.toolType === 'line' || snapshot.toolType === 'polyline') && isWallLikeTrace(snapshot, assembly) && assembly && assembly.wall_subtype) {
            return {
                tool: 'polyline',
                variantFilter: { wallSubtype: assembly.wall_subtype },
                variantLabel: 'Wall',
                sourceButton: document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="wall"][data-wall-subtype="' + assembly.wall_subtype + '"]'),
                semanticKey: 'wall',
                settingsFieldsOverride: SEMANTIC_TOOLS.wall.settingsFields,
            };
        }
        if (snapshot.toolType === 'area' && assembly && ['floor_system', 'ceiling', 'roof'].indexOf(assembly.category) !== -1) {
            return {
                tool: 'area',
                variantFilter: { categoryIn: ['floor_system', 'ceiling', 'roof'] },
                variantLabel: 'Joist',
                sourceButton: document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="joist"]'),
                semanticKey: 'joist',
                settingsFieldsOverride: SEMANTIC_TOOLS.joist.settingsFields,
            };
        }
        if (snapshot.toolType === 'count' && assembly) {
            return {
                tool: 'count',
                variantFilter: null,
                variantLabel: 'Column',
                sourceButton: document.querySelector(TOOLBAR_SELECTOR + ' [data-semantic="column"]'),
                semanticKey: 'column',
                settingsFieldsOverride: SEMANTIC_TOOLS.column.settingsFields,
            };
        }
        return {
            tool: snapshot.toolType,
            variantFilter: null,
            variantLabel: null,
            sourceButton: document.querySelector(TOOLBAR_SELECTOR + ' .tool-btn[data-tool="' + snapshot.toolType + '"]'),
            semanticKey: null,
            settingsFieldsOverride: null,
        };
    }

    function useTraceForNewTraces(obj) {
        var snapshot = traceSnapshotFromObject(obj);
        if (!snapshot) {
            return;
        }
        var setup = inferTraceToolSetup(snapshot);
        activeSemanticKey = setup.semanticKey || null;
        activateTool(
            setup.tool,
            setup.variantFilter || null,
            setup.variantLabel || null,
            setup.sourceButton || null,
            setup.settingsFieldsOverride || null
        );
        applyToolSettings(snapshot.settings || {});
        if (snapshot.color) {
            colorInput.value = snapshot.color;
        }
        if (optionExists(materialSelect, snapshot.materialId)) {
            materialSelect.value = snapshot.materialId || '';
        }
        if (optionExists(assemblySelect, snapshot.assemblyId)) {
            assemblySelect.value = snapshot.assemblyId || '';
        }
        if (activeTool && TOOLS[activeTool]) {
            saveToolMemory(activeTool, activeVariantFilter, activeSemanticKey);
            updateToolMemoryUi(activeTool, activeVariantFilter, activeSemanticKey);
        }
        lastMeasurement.textContent = 'Using selected ' + snapshot.label.toLowerCase() + ' setup for new traces.';
    }

    function clampPointToImage(point) {
        if (!point) {
            return point;
        }
        var clamped = { x: point.x, y: point.y };
        if (imageNaturalWidth) {
            clamped.x = Math.max(0, Math.min(imageNaturalWidth, clamped.x));
        }
        if (imageNaturalHeight) {
            clamped.y = Math.max(0, Math.min(imageNaturalHeight, clamped.y));
        }
        return clamped;
    }

    function cloneGeometryWithOffset(geometry, offsetX, offsetY) {
        return (geometry || []).map(function (point) {
            return clampPointToImage({
                x: Number(point.x || 0) + offsetX,
                y: Number(point.y || 0) + offsetY,
            });
        });
    }

    function selectTraceObject(obj) {
        if (!obj) {
            return;
        }
        canvas.discardActiveObject();
        canvas.setActiveObject(obj);
        canvas.requestRenderAll();
        scrollCanvasObjectsIntoView([obj]);
        onTraceSelected();
    }

    function createTraceFromSnapshot(snapshot, options) {
        if (!snapshot) {
            return Promise.resolve(null);
        }
        var opts = options || {};
        return fetch(TRACE_CREATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({
                tool_type: snapshot.toolType,
                geometry: opts.geometry || snapshot.geometry,
                material_id: snapshot.materialId,
                assembly_id: snapshot.assemblyId,
                parent_wall_id: snapshot.parentWallId,
                color: snapshot.color,
                settings: snapshot.settings || {},
            }),
        })
            .then(handleJsonResponse)
            .then(function (trace) {
                var obj = drawTrace(trace);
                refreshMaterialList();
                if (opts.selectCreated !== false) {
                    selectTraceObject(obj);
                }
                return trace;
            });
    }

    function duplicateTrace(obj) {
        var snapshot = traceSnapshotFromObject(obj);
        if (!snapshot) {
            return;
        }
        createTraceFromSnapshot(snapshot, {
            geometry: cloneGeometryWithOffset(snapshot.geometry, 24, 24),
            selectCreated: true,
        })
            .then(function (trace) {
                lastMeasurement.textContent = trace && trace.measurement_display
                    ? ('Duplicated trace: ' + trace.measurement_display)
                    : 'Duplicated selected trace.';
            })
            .catch(showError);
    }

    function updateUndoDeleteUi() {
        if (!deleteUndoBanner || !deleteUndoText) {
            return;
        }
        if (!lastDeletedTraceSnapshot) {
            deleteUndoBanner.style.display = 'none';
            return;
        }
        if (Array.isArray(lastDeletedTraceSnapshot)) {
            deleteUndoText.textContent = lastDeletedTraceSnapshot.length + ' traces deleted. Undo restores them to this page.';
        } else {
            deleteUndoText.textContent = lastDeletedTraceSnapshot.label + ' deleted. Undo restores it to this page.';
        }
        deleteUndoBanner.style.display = '';
    }

    function undoLastDeletedTrace() {
        if (!lastDeletedTraceSnapshot) {
            return;
        }
        var snapshots = Array.isArray(lastDeletedTraceSnapshot)
            ? lastDeletedTraceSnapshot.slice()
            : [lastDeletedTraceSnapshot];
        Promise.all(snapshots.map(function (snapshot) {
            return createTraceFromSnapshot(snapshot, { selectCreated: false });
        }))
            .then(function () {
                lastDeletedTraceSnapshot = null;
                updateUndoDeleteUi();
            })
            .catch(showError);
    }

    function activateLinkedTraceIds(traceIds) {
        var matches = getTraceObjectsByIds(traceIds);
        if (!matches.length) {
            return;
        }
        if (matches.length === 1) {
            canvas.discardActiveObject();
            canvas.setActiveObject(matches[0]);
            canvas.requestRenderAll();
            scrollCanvasObjectsIntoView(matches);
            onTraceSelected();
            return;
        }
        canvas.discardActiveObject();
        selectedTrace = null;
        linkedTraceIds = traceIds.slice();
        activeLinkedTraceIndex = 0;
        syncMaterialListSelection();
        renderBulkSelectionPanel(matches);
        showPanel('bulk');
        scrollMaterialRowIntoView(linkedTraceIds);
        scrollCanvasObjectsIntoView(matches);
        updateMaterialToolbarState();
    }

    function clearLinkedSelection() {
        linkedTraceIds = [];
        hoveredTraceIds = [];
        activeMaterialSummary = null;
        activeLinkedTraceIndex = -1;
        focusLinkedMode = false;
        materialSelectedOnly = false;
        materialCategoryOnly = false;
        canvas.discardActiveObject();
        selectedTrace = null;
        syncMaterialListSelection();
        showPanel(activeTool && TOOLS[activeTool] ? 'tool-settings' : 'none');
        updateMaterialToolbarState();
    }

    function findFirstMaterialRowForTraceIds(traceIds) {
        if (!traceIds || !traceIds.length) {
            return null;
        }
        var rows = document.querySelectorAll('.material-summary-row[data-trace-ids]');
        for (var i = 0; i < rows.length; i++) {
            var rowTraceIds = parseTraceIds(rows[i].dataset.traceIds);
            if (rowTraceIds.some(function (traceId) { return traceIds.indexOf(traceId) !== -1; })) {
                return rows[i];
            }
        }
        return null;
    }

    function scrollMaterialRowIntoView(traceIds) {
        var row = findFirstMaterialRowForTraceIds(traceIds);
        if (!row || row.style.display === 'none') {
            return;
        }
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    function cycleLinkedTrace(direction) {
        if (linkedTraceIds.length < 2) {
            return;
        }
        if (activeLinkedTraceIndex < 0) {
            activeLinkedTraceIndex = 0;
        } else {
            activeLinkedTraceIndex = (activeLinkedTraceIndex + direction + linkedTraceIds.length) % linkedTraceIds.length;
        }
        focusSpecificLinkedTrace();
    }

    function focusSpecificLinkedTrace() {
        if (activeLinkedTraceIndex < 0 || activeLinkedTraceIndex >= linkedTraceIds.length) {
            return;
        }
        var targetId = linkedTraceIds[activeLinkedTraceIndex];
        var match = getTraceObjectsByIds([targetId])[0];
        if (!match) {
            return;
        }
        canvas.discardActiveObject();
        canvas.setActiveObject(match);
        canvas.requestRenderAll();
        scrollCanvasObjectsIntoView([match]);
        onTraceSelected();
        updateMaterialToolbarState();
    }

    function materialSummaryFromRow(row) {
        if (!row) {
            return null;
        }
        return {
            label: row.dataset.materialLabel || 'Material row',
            categoryLabel: row.dataset.categoryLabel || '',
            quantity: row.dataset.quantity || '',
            visibleTraceCount: parseInt(row.dataset.visibleTraceCount || '0', 10) || 0,
            totalTraceCount: parseInt(row.dataset.totalTraceCount || '0', 10) || 0,
        };
    }

    function updateMaterialHoverState(activeRow) {
        document.querySelectorAll('.material-summary-row').forEach(function (row) {
            row.classList.toggle('is-hovered', Boolean(activeRow && row === activeRow));
        });
        refreshLinkedTraceStyling();
        updateMaterialToolbarState();
    }

    function syncMaterialListSelection() {
        var rows = document.querySelectorAll('.material-summary-row[data-trace-ids]');
        rows.forEach(function (row) {
            var traceIds = parseTraceIds(row.dataset.traceIds);
            var isLinked = linkedTraceIds.length && traceIds.some(function (traceId) {
                return linkedTraceIds.indexOf(traceId) !== -1;
            });
            row.classList.toggle('is-linked', Boolean(isLinked));
        });
        if (!linkedTraceIds.length) {
            activeMaterialSummary = null;
            materialSelectedOnly = false;
            materialCategoryOnly = false;
        }
        applyMaterialListFilters();
        refreshLinkedTraceStyling();
        updateMaterialToolbarState();
    }

    function applyMaterialListFilters() {
        var rows = document.querySelectorAll('.material-summary-row');
        rows.forEach(function (row) {
            var visible = true;
            if (materialSelectedOnly && linkedTraceIds.length) {
                var traceIds = parseTraceIds(row.dataset.traceIds);
                visible = traceIds.some(function (traceId) {
                    return linkedTraceIds.indexOf(traceId) !== -1;
                });
            }
            if (visible && materialCategoryOnly && activeMaterialSummary && activeMaterialSummary.categoryLabel) {
                visible = row.dataset.categoryLabel === activeMaterialSummary.categoryLabel;
            }
            row.style.display = visible ? '' : 'none';
        });
        document.querySelectorAll('.material-summary-group').forEach(function (group) {
            var hasVisibleRow = Array.prototype.some.call(group.querySelectorAll('.material-summary-row'), function (row) {
                return row.style.display !== 'none';
            });
            group.style.display = hasVisibleRow ? '' : 'none';
        });
    }

    function updateMaterialToolbarState() {
        var hasLinked = linkedTraceIds.length > 0;
        var hasHover = hoveredTraceIds.length > 0;
        var anyFilterActive = materialSummaryPageOnly || focusLinkedMode || materialSelectedOnly || materialCategoryOnly;
        if (materialControlsTrigger) {
            materialControlsTrigger.classList.toggle('btn-primary', anyFilterActive);
            materialControlsTrigger.classList.toggle('btn-outline-secondary', !anyFilterActive);
        }
        if (materialPageScopeButton) {
            materialPageScopeButton.textContent = 'This page only: ' + (materialSummaryPageOnly ? 'On' : 'Off');
            materialPageScopeButton.classList.toggle('btn-primary', materialSummaryPageOnly);
            materialPageScopeButton.classList.toggle('btn-outline-secondary', !materialSummaryPageOnly);
        }
        if (materialFocusLinkedButton) {
            materialFocusLinkedButton.disabled = !hasLinked;
            materialFocusLinkedButton.textContent = 'Focus linked: ' + (focusLinkedMode ? 'On' : 'Off');
            materialFocusLinkedButton.classList.toggle('btn-primary', hasLinked && focusLinkedMode);
            materialFocusLinkedButton.classList.toggle('btn-outline-secondary', !focusLinkedMode);
        }
        if (materialSelectedOnlyButton) {
            materialSelectedOnlyButton.disabled = !hasLinked;
            materialSelectedOnlyButton.textContent = 'Selected only: ' + (materialSelectedOnly ? 'On' : 'Off');
            materialSelectedOnlyButton.classList.toggle('btn-primary', hasLinked && materialSelectedOnly);
            materialSelectedOnlyButton.classList.toggle('btn-outline-secondary', !materialSelectedOnly);
        }
        if (materialCategoryOnlyButton) {
            materialCategoryOnlyButton.disabled = !(activeMaterialSummary && activeMaterialSummary.categoryLabel);
            materialCategoryOnlyButton.textContent = 'Current category: ' + (materialCategoryOnly ? 'On' : 'Off');
            materialCategoryOnlyButton.classList.toggle('btn-primary', Boolean(activeMaterialSummary && activeMaterialSummary.categoryLabel && materialCategoryOnly));
            materialCategoryOnlyButton.classList.toggle('btn-outline-secondary', !materialCategoryOnly);
        }
        if (materialPrevLinkedButton) {
            materialPrevLinkedButton.disabled = linkedTraceIds.length < 2;
        }
        if (materialNextLinkedButton) {
            materialNextLinkedButton.disabled = linkedTraceIds.length < 2;
        }
        if (materialApplyToolSetupButton) {
            materialApplyToolSetupButton.disabled = !canApplyToolSetupToLinked();
        }
        if (materialDeleteLinkedButton) {
            materialDeleteLinkedButton.disabled = !hasLinked;
        }
        if (materialClearLinkedButton) {
            materialClearLinkedButton.disabled = !hasLinked;
        }
        if (materialListStatus) {
            if (hasHover && !hasLinked) {
                materialListStatus.textContent = hoveredTraceIds.length + ' trace' + (hoveredTraceIds.length === 1 ? '' : 's') + ' in hover preview.';
            } else if (!hasLinked) {
                materialListStatus.textContent = materialSummaryPageOnly
                    ? 'Showing only materials generated from traces on this page.'
                    : 'Showing all estimate rows. Select a material row to highlight matching traces on this page.';
            } else if (materialSelectedOnly || materialCategoryOnly) {
                materialListStatus.textContent = 'Filtered to ' +
                    (materialSelectedOnly ? 'selected rows' : 'all rows') +
                    (materialSelectedOnly && materialCategoryOnly ? ' and ' : '') +
                    (materialCategoryOnly ? 'the current category' : '') + '.';
            } else if (focusLinkedMode) {
                materialListStatus.textContent = linkedTraceIds.length + ' linked trace' + (linkedTraceIds.length === 1 ? '' : 's') + ' focused on the plan.';
            } else {
                materialListStatus.textContent = linkedTraceIds.length + ' linked trace' + (linkedTraceIds.length === 1 ? '' : 's') + ' highlighted on this page.';
            }
        }
        if (selectionSummary) {
            if (hasLinked && activeMaterialSummary) {
                selectionSummary.innerHTML = '<strong>' + escapeHtml(activeMaterialSummary.label) + '</strong> • ' +
                    linkedTraceIds.length + ' linked trace' + (linkedTraceIds.length === 1 ? '' : 's') +
                    (linkedTraceIds.length > 1 ? ' • match ' + escapeHtml(String(activeLinkedTraceIndex + 1)) + ' of ' + escapeHtml(String(linkedTraceIds.length)) : '') +
                    (activeMaterialSummary.quantity ? ' • qty ' + escapeHtml(String(activeMaterialSummary.quantity)) : '') +
                    (focusLinkedMode ? ' • focus mode on' : '');
            } else if (hasLinked) {
                selectionSummary.textContent = linkedTraceIds.length + ' trace' + (linkedTraceIds.length === 1 ? '' : 's') + ' selected on the canvas.';
            } else if (selectedTrace) {
                selectionSummary.innerHTML = '<strong>' + escapeHtml((TOOLS[selectedTrace.traceToolType] || TOOLS.line).label) + '</strong>' +
                    (selectedTrace.traceMeasurement ? ' • ' + escapeHtml(selectedTrace.traceMeasurement) : '') +
                    (selectedTrace.traceAssemblyId ? ' • assembly assigned' : ' • no assembly assigned');
            } else if (hasHover) {
                selectionSummary.textContent = hoveredTraceIds.length + ' source trace' + (hoveredTraceIds.length === 1 ? '' : 's') + ' previewed on hover.';
            } else {
                selectionSummary.textContent = 'Hover a material row to preview its source traces. Click a row to keep those traces selected.';
            }
        }
    }

    function refreshLinkedTraceStyling() {
        canvas.getObjects().forEach(function (obj) {
            if (obj.traceId) {
                restyleTrace(obj);
            }
        });
        canvas.requestRenderAll();
    }

    function scrollCanvasObjectsIntoView(objects) {
        if (!objects.length) {
            return;
        }
        var bounds = objects.reduce(function (acc, obj) {
            var rect = obj.getBoundingRect();
            if (!acc) {
                return {
                    left: rect.left,
                    top: rect.top,
                    right: rect.left + rect.width,
                    bottom: rect.top + rect.height,
                };
            }
            acc.left = Math.min(acc.left, rect.left);
            acc.top = Math.min(acc.top, rect.top);
            acc.right = Math.max(acc.right, rect.left + rect.width);
            acc.bottom = Math.max(acc.bottom, rect.top + rect.height);
            return acc;
        }, null);
        if (!bounds) {
            return;
        }
        var centerX = (bounds.left + bounds.right) / 2 * currentZoom;
        var centerY = (bounds.top + bounds.bottom) / 2 * currentZoom;
        var wrapRect = canvasWrapEl.getBoundingClientRect();
        canvasWrapEl.scrollLeft = Math.max(centerX - (wrapRect.width / 2), 0);
        canvasWrapEl.scrollTop = Math.max(centerY - (wrapRect.height / 2), 0);
    }

    // -------------------------------------------------------- wall elevation

    function showWallElevation(model) {
        wallElevationMeta.textContent = (model.assembly_name || 'No assembly') +
            ' • ' + model.length_ft + ' ft long • ' + model.height_in + ' in high • ' +
            model.stud_spacing_in + ' in OC';
        var roles = Object.keys(model.summary.roles).map(function (role) {
            return role + ': ' + model.summary.roles[role];
        }).join(' | ');
        wallElevationSummary.textContent = model.summary.member_count + ' generated members • ' +
            model.summary.opening_count + ' attached openings' + (roles ? ' • ' + roles : '');
        currentWallModel = model;
        wallElevationCanvas.innerHTML = buildWallSvg(model);
        wall3dCanvas.innerHTML = buildWall3dSvg(model);
        wallLayerList.innerHTML = buildLayerList(model);
        wallCutList.innerHTML = buildCutList(model);
        selectedWallMemberId = null;
        wallMemberDetail.style.display = 'none';
        setWallEditMode('select');
        updateWallEditStatus('Drag members or blue grips. Changes auto-save.');
        wallElevationBackdrop.classList.add('open');
        wallElevationModal.classList.add('open');
    }

    function hideWallElevation() {
        wallElevationBackdrop.classList.remove('open');
        wallElevationModal.classList.remove('open');
    }

    function buildWallSvg(model) {
        var pad = 24;
        var scale = Math.min(10, Math.max(2, 900 / Math.max(model.length_in, 1)));
        var width = Math.ceil(model.length_in * scale) + (pad * 2);
        var height = Math.ceil(model.height_in * scale) + (pad * 2);
        wallSvgState = { pad: pad, scale: scale };
        var svg = ['<svg id="wall-elevation-svg" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">'];
        svg.push('<defs><filter id="member-shadow"><feDropShadow dx="0.8" dy="0.8" stdDeviation="0.6" flood-opacity="0.25"/></filter></defs>');
        svg.push('<rect x="' + pad + '" y="' + pad + '" width="' + (model.length_in * scale) + '" height="' + (model.height_in * scale) + '" fill="#ffffff" stroke="#adb5bd"/>');
        model.members.forEach(function (member) {
            svg.push(memberRectSvg(member, model, scale, pad, member.id === selectedWallMemberId));
        });
        model.openings.forEach(function (opening) {
            var x = pad + (opening.left_in * scale);
            var y = pad + ((model.height_in - opening.top_in) * scale);
            var w = opening.width_in * scale;
            var h = opening.rough_height_in * scale;
            svg.push('<rect x="' + x.toFixed(2) + '" y="' + y.toFixed(2) + '" width="' + w.toFixed(2) + '" height="' + h.toFixed(2) + '" fill="rgba(13,110,253,0.12)" stroke="#0d6efd" stroke-dasharray="5 4" pointer-events="none"/>');
            svg.push('<text x="' + (x + 4).toFixed(2) + '" y="' + (y + 14).toFixed(2) + '" font-size="12">' + escapeHtml(opening.opening_type) + ' ' + Math.round(opening.width_in) + 'in</text>');
        });
        svg.push('</svg>');
        return svg.join('');
    }

    function memberRectSvg(member, model, scale, pad, selected) {
        var x = pad + (member.x * scale);
        var y = pad + ((model.height_in - member.y - member.height) * scale);
        var w = Math.max(1, member.width * scale);
        var h = Math.max(1, member.height * scale);
        var stroke = selected ? '#0d6efd' : '#5c4033';
        var html = ['<g class="wall-member-row" data-member-id="' + escapeHtml(member.id) + '">'];
        html.push('<rect data-member-id="' + escapeHtml(member.id) + '" x="' + x.toFixed(2) + '" y="' + y.toFixed(2) + '" width="' + w.toFixed(2) + '" height="' + h.toFixed(2) + '" fill="' + memberFill(member.role) + '" stroke="' + stroke + '" stroke-width="' + (selected ? '2' : '0.8') + '" filter="url(#member-shadow)"><title>' + escapeHtml(member.role) + '</title></rect>');
        if (selected) {
            html.push(gripSvg('move', x + (w / 2), y + (h / 2)));
            html.push(gripSvg('top', x + (w / 2), y));
            html.push(gripSvg('bottom', x + (w / 2), y + h));
            html.push(gripSvg('left', x, y + (h / 2)));
            html.push(gripSvg('right', x + w, y + (h / 2)));
        }
        html.push('</g>');
        return html.join('');
    }

    function gripSvg(action, x, y) {
        return '<circle class="wall-member-grip" data-grip="' + action + '" cx="' + x.toFixed(2) + '" cy="' + y.toFixed(2) + '" r="5" fill="#fff" stroke="#0d6efd" stroke-width="2"><title>' + action + '</title></circle>';
    }

    function buildWall3dSvg(model) {
        var pad = 38;
        var lengthScale = Math.min(7.5, Math.max(2, 760 / Math.max(model.length_in, 1)));
        var heightScale = Math.min(5.2, Math.max(1.4, 430 / Math.max(model.height_in, 1)));
        var depth = Math.max(28, (model.wall_thickness_in || 5.5) * 6);
        var skewX = depth * 0.72;
        var skewY = depth * -0.42;
        var wallW = model.length_in * lengthScale;
        var wallH = model.height_in * heightScale;
        var width = Math.ceil(wallW + skewX + 120);
        var height = Math.ceil(wallH + Math.abs(skewY) + 95);
        var x0 = pad;
        var y0 = pad + Math.abs(skewY);
        var svg = ['<svg id="wall-3d-svg" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">'];
        svg.push('<defs>' +
            '<linearGradient id="wood-front" x1="0" x2="1"><stop offset="0%" stop-color="#d9b27c"/><stop offset="45%" stop-color="#c99355"/><stop offset="100%" stop-color="#b8793f"/></linearGradient>' +
            '<linearGradient id="wood-side" x1="0" x2="1"><stop offset="0%" stop-color="#a56a34"/><stop offset="100%" stop-color="#7f4f27"/></linearGradient>' +
            '<linearGradient id="wood-top" x1="0" x2="1"><stop offset="0%" stop-color="#efcf96"/><stop offset="100%" stop-color="#c48c4f"/></linearGradient>' +
            '<filter id="wall3d-shadow"><feDropShadow dx="2" dy="3" stdDeviation="2" flood-opacity="0.22"/></filter>' +
            '</defs>');
        svg.push('<rect x="0" y="0" width="100%" height="100%" fill="#f4f1eb"/>');
        svg.push('<polygon points="' + x0 + ',' + (y0 + wallH + 22) + ' ' + (x0 + wallW + skewX + 35) + ',' + (y0 + wallH + skewY + 22) + ' ' + (x0 + wallW + skewX + 55) + ',' + (y0 + wallH + skewY + 38) + ' ' + (x0 + 20) + ',' + (y0 + wallH + 42) + '" fill="rgba(0,0,0,0.08)"/>');
        svg.push('<polygon points="' + x0 + ',' + y0 + ' ' + (x0 + skewX) + ',' + (y0 + skewY) + ' ' + (x0 + wallW + skewX) + ',' + (y0 + skewY) + ' ' + (x0 + wallW) + ',' + y0 + '" fill="rgba(193,133,69,0.22)" stroke="#8a5a31"/>');
        svg.push('<polygon points="' + (x0 + wallW) + ',' + y0 + ' ' + (x0 + wallW + skewX) + ',' + (y0 + skewY) + ' ' + (x0 + wallW + skewX) + ',' + (y0 + wallH + skewY) + ' ' + (x0 + wallW) + ',' + (y0 + wallH) + '" fill="rgba(142,92,48,0.18)" stroke="#8a5a31"/>');
        svg.push('<rect x="' + x0 + '" y="' + y0 + '" width="' + wallW + '" height="' + wallH + '" fill="rgba(255,255,255,0.10)" stroke="#8a5a31"/>');

        model.members.slice().sort(function (a, b) { return (a.y - b.y) || (a.x - b.x); }).forEach(function (member) {
            var x = x0 + (member.x * lengthScale);
            var y = y0 + ((model.height_in - member.y - member.height) * heightScale);
            var w = Math.max(2, member.width * lengthScale);
            var h = Math.max(2, member.height * heightScale);
            drawBoard(svg, x, y, w, h, skewX * 0.45, skewY * 0.45, member.role);
        });
        model.openings.forEach(function (opening) {
            var x = x0 + (opening.left_in * lengthScale);
            var y = y0 + ((model.height_in - opening.top_in) * heightScale);
            var w = opening.width_in * lengthScale;
            var h = opening.rough_height_in * heightScale;
            svg.push('<rect x="' + x.toFixed(2) + '" y="' + y.toFixed(2) + '" width="' + w.toFixed(2) + '" height="' + h.toFixed(2) + '" fill="rgba(180,220,255,0.28)" stroke="#0d6efd" stroke-width="1.2" stroke-dasharray="6 4"/>');
        });
        svg.push('<text x="' + x0 + '" y="' + (height - 18) + '" font-size="12" fill="#5c4033">Pseudo-3D framing preview - member edits update this view live.</text>');
        svg.push('</svg>');
        return svg.join('');
    }

    function drawBoard(svg, x, y, w, h, dx, dy, role) {
        var right = x + w;
        var bottom = y + h;
        svg.push('<g filter="url(#wall3d-shadow)">');
        svg.push('<polygon points="' + x + ',' + y + ' ' + (x + dx) + ',' + (y + dy) + ' ' + (right + dx) + ',' + (y + dy) + ' ' + right + ',' + y + '" fill="url(#wood-top)" stroke="#6f4727" stroke-width="0.55"/>');
        svg.push('<polygon points="' + right + ',' + y + ' ' + (right + dx) + ',' + (y + dy) + ' ' + (right + dx) + ',' + (bottom + dy) + ' ' + right + ',' + bottom + '" fill="url(#wood-side)" stroke="#6f4727" stroke-width="0.55"/>');
        svg.push('<rect x="' + x.toFixed(2) + '" y="' + y.toFixed(2) + '" width="' + w.toFixed(2) + '" height="' + h.toFixed(2) + '" fill="url(#wood-front)" stroke="#6f4727" stroke-width="0.65"><title>' + escapeHtml(role) + '</title></rect>');
        var grainEvery = Math.max(8, Math.min(26, h / 4));
        for (var gy = y + grainEvery; gy < bottom - 3; gy += grainEvery) {
            svg.push('<path d="M' + (x + 2).toFixed(1) + ' ' + gy.toFixed(1) + ' C ' + (x + w * 0.35).toFixed(1) + ' ' + (gy - 2).toFixed(1) + ', ' + (x + w * 0.65).toFixed(1) + ' ' + (gy + 2).toFixed(1) + ', ' + (right - 2).toFixed(1) + ' ' + gy.toFixed(1) + '" stroke="rgba(90,54,25,0.23)" stroke-width="0.6" fill="none"/>');
        }
        svg.push('</g>');
    }

    function buildLayerList(model) {
        var rows = (model.layers || []).map(function (layer) {
            return '<tr><td>' + escapeHtml(layer.label) + '</td><td>' + layer.thickness_in + ' in</td><td>' + layer.offset_in + ' in</td></tr>';
        }).join('');
        return '<table class="table table-sm"><thead><tr><th>Layer</th><th>Thickness</th><th>Offset</th></tr></thead><tbody>' + rows + '</tbody></table>';
    }

    function buildCutList(model) {
        var rows = (model.cut_list || []).map(function (row) {
            return '<tr><td>' + escapeHtml(row.role) + '</td><td>' + row.quantity + '</td><td>' + row.length_in + ' in</td><td>' + row.length_ft + ' ft</td></tr>';
        }).join('');
        return '<table class="table table-sm table-striped"><thead><tr><th>Role</th><th>Qty</th><th>Cut length</th><th>Feet</th></tr></thead><tbody>' + rows + '</tbody></table>';
    }

    function layerFill(key) {
        if (key === 'framing') { return '#dee2e6'; }
        if (key === 'drywall') { return '#f8f9fa'; }
        if (key === 'sheathing') { return '#ffe8a1'; }
        if (key === 'wrap') { return '#cff4fc'; }
        if (key === 'siding') { return '#d1e7dd'; }
        return '#e9ecef';
    }

    wallElevationCanvas.addEventListener('click', function (event) {
        var target = event.target;
        if (!target || !target.dataset || !currentWallModel || wallDrag) { return; }
        if (target.dataset.memberId) {
            selectedWallMemberId = target.dataset.memberId;
            renderWallEditors();
        }
    });

    wallElevationCanvas.addEventListener('pointerdown', function (event) {
        if (!currentWallModel || !wallSvgState) { return; }
        var target = event.target;
        var point = wallPointFromEvent(event);
        if (!point) { return; }

        if (wallEditMode === 'add-stud' || wallEditMode === 'add-block') {
            event.preventDefault();
            var member = makeDrawnMember(point, point, wallEditMode);
            currentWallModel.members.push(member);
            selectedWallMemberId = member.id;
            wallDrag = { kind: 'draw', start: point, memberId: member.id, mode: wallEditMode };
            renderWallEditors();
            return;
        }

        if (target && target.dataset && target.dataset.grip && selectedWallMemberId) {
            event.preventDefault();
            wallDrag = beginWallDrag('grip', selectedWallMemberId, point, target.dataset.grip);
            return;
        }
        if (target && target.dataset && target.dataset.memberId) {
            event.preventDefault();
            selectedWallMemberId = target.dataset.memberId;
            wallDrag = beginWallDrag('move', selectedWallMemberId, point, 'move');
            renderWallEditors();
        }
    });

    window.addEventListener('pointermove', function (event) {
        if (!wallDrag || !currentWallModel) { return; }
        var point = wallPointFromEvent(event);
        if (!point) { return; }
        var member = currentWallModel.members.find(function (item) { return item.id === wallDrag.memberId; });
        if (!member) { return; }

        if (wallDrag.kind === 'draw') {
            applyDrawnMemberGeometry(member, wallDrag.start, point, wallDrag.mode);
            applyMemberOverride(member, { skipPersist: true, skipRender: true });
            refreshWallViewsOnly();
            updateWallFormFields(member);
            return;
        }

        var next = geometryFromDrag(wallDrag, point);
        if (!next) { return; }
        applyMemberOverride(next, { skipPersist: true, skipRender: true });
        refreshWallViewsOnly();
        updateWallFormFields(next);
    });

    window.addEventListener('pointerup', function () {
        if (!wallDrag) { return; }
        var member = currentWallModel && currentWallModel.members.find(function (item) { return item.id === wallDrag.memberId; });
        wallDrag = null;
        if (member) {
            applyMemberOverride(member, { skipRender: true });
            refreshWallViewsOnly();
            renderWallEditors();
            scheduleWallPersist(true);
        }
    });

    if (wallEditToolbar) {
        wallEditToolbar.addEventListener('click', function (event) {
            var tool = event.target && event.target.dataset ? event.target.dataset.wallTool : null;
            if (tool) { setWallEditMode(tool); }
        });
    }

    if (deleteWallMemberInline) {
        deleteWallMemberInline.addEventListener('click', deleteSelectedMember);
    }

    wallMemberDetail.addEventListener('click', function (event) {
        var action = event.target && event.target.dataset ? event.target.dataset.wallMemberAction : null;
        if (!action) { return; }
        if (action === 'delete') { deleteSelectedMember(); }
        if (action === 'add') { addCustomMember(); }
    });

    wallMemberDetail.addEventListener('input', function (event) {
        if (!event.target || !event.target.dataset || !event.target.dataset.memberField) { return; }
        applyMemberFormLive();
    });

    function setWallEditMode(mode) {
        wallEditMode = mode || 'select';
        if (wallEditToolbar) {
            wallEditToolbar.querySelectorAll('[data-wall-tool]').forEach(function (button) {
                button.classList.toggle('active', button.dataset.wallTool === wallEditMode);
            });
        }
        if (wallEditMode === 'add-stud') {
            updateWallEditStatus('Draw mode: click-drag vertically to add a stud/custom vertical member.');
        } else if (wallEditMode === 'add-block') {
            updateWallEditStatus('Draw mode: click-drag a rectangle to add blocking or a custom member.');
        } else {
            updateWallEditStatus('Select mode: drag members, drag blue grips, or edit fields. Auto-save is on.');
        }
    }

    function updateWallEditStatus(message) {
        if (wallEditStatus) { wallEditStatus.textContent = message; }
    }

    function renderWallEditors() {
        refreshWallViewsOnly();
        if (deleteWallMemberInline) { deleteWallMemberInline.disabled = !selectedWallMemberId; }
        var member = currentWallModel.members.find(function (item) { return item.id === selectedWallMemberId; });
        if (!member) {
            wallMemberDetail.style.display = 'none';
            return;
        }
        wallMemberDetail.innerHTML = '<div class="d-flex justify-content-between align-items-start gap-2">' +
            '<div><strong>' + escapeHtml(member.role) + '</strong><br><span class="small text-muted">' + escapeHtml(member.id) + ' • ' + escapeHtml(member.source || 'generated') + '</span></div>' +
            '<button type="button" class="btn btn-sm btn-outline-danger" data-wall-member-action="delete">Delete member now</button></div>' +
            '<div class="row g-2 mt-2">' +
            numberInputHtml('member-x-input', 'X from left', member.x, 'x') +
            numberInputHtml('member-y-input', 'Y from bottom', member.y, 'y') +
            numberInputHtml('member-width-input', 'Width', member.width, 'width') +
            numberInputHtml('member-height-input', 'Height', member.height, 'height') +
            '</div>' +
            '<div class="mt-2"><label class="form-label" for="member-role-input">Role</label><input id="member-role-input" data-member-field="role" class="form-control" value="' + escapeHtml(member.role) + '"></div>' +
            '<div class="d-flex gap-2 mt-3"><button type="button" class="btn btn-outline-secondary btn-sm" data-wall-member-action="add">Clone as new member</button></div>' +
            '<p class="small text-muted mt-2 mb-0">No separate save is required. Field edits and drag edits update the wall immediately and auto-save.</p>';
        wallMemberDetail.style.display = '';
    }

    function refreshWallViewsOnly() {
        if (!currentWallModel) { return; }
        currentWallModel.cut_list = buildCutListRowsFromMembers(currentWallModel.members);
        wallElevationCanvas.innerHTML = buildWallSvg(currentWallModel);
        wall3dCanvas.innerHTML = buildWall3dSvg(currentWallModel);
        wallCutList.innerHTML = buildCutList(currentWallModel);
    }

    function numberInputHtml(id, label, value, field) {
        return '<div class="col-md-3"><label class="form-label" for="' + id + '">' + label + ' (in)</label>' +
            '<input type="number" step="0.25" data-member-field="' + field + '" class="form-control form-control-sm" id="' + id + '" value="' + round3(value) + '"></div>';
    }

    function updateWallFormFields(member) {
        setInputValue('member-x-input', member.x);
        setInputValue('member-y-input', member.y);
        setInputValue('member-width-input', member.width);
        setInputValue('member-height-input', member.height);
        var roleInput = document.getElementById('member-role-input');
        if (roleInput && roleInput.value !== member.role) { roleInput.value = member.role; }
    }

    function setInputValue(id, value) {
        var input = document.getElementById(id);
        if (input) { input.value = round3(value); }
    }

    function beginWallDrag(kind, memberId, point, grip) {
        var member = currentWallModel.members.find(function (item) { return item.id === memberId; });
        return member ? { kind: kind, memberId: memberId, start: point, original: Object.assign({}, member), grip: grip } : null;
    }

    function geometryFromDrag(drag, point) {
        var m = Object.assign({}, drag.original);
        if (drag.kind === 'move') {
            var dx = point.x - drag.start.x;
            var dy = point.y - drag.start.y;
            m.x = clampInches(drag.original.x + dx, 0, currentWallModel.length_in - drag.original.width);
            m.y = clampInches(drag.original.y + dy, 0, currentWallModel.height_in - drag.original.height);
            return m;
        }
        var right = drag.original.x + drag.original.width;
        var top = drag.original.y + drag.original.height;
        if (drag.grip === 'top') {
            m.height = Math.max(0.25, point.y - drag.original.y);
        } else if (drag.grip === 'bottom') {
            m.y = clampInches(point.y, 0, top - 0.25);
            m.height = Math.max(0.25, top - m.y);
        } else if (drag.grip === 'left') {
            m.x = clampInches(point.x, 0, right - 0.25);
            m.width = Math.max(0.25, right - m.x);
        } else if (drag.grip === 'right') {
            m.width = Math.max(0.25, Math.min(point.x, currentWallModel.length_in) - drag.original.x);
        } else if (drag.grip === 'move') {
            var dx2 = point.x - drag.start.x;
            var dy2 = point.y - drag.start.y;
            m.x = clampInches(drag.original.x + dx2, 0, currentWallModel.length_in - drag.original.width);
            m.y = clampInches(drag.original.y + dy2, 0, currentWallModel.height_in - drag.original.height);
        }
        m.height = Math.min(m.height, currentWallModel.height_in - m.y);
        m.width = Math.min(m.width, currentWallModel.length_in - m.x);
        return m;
    }

    function wallPointFromEvent(event) {
        var svg = document.getElementById('wall-elevation-svg');
        if (!svg || !wallSvgState) { return null; }
        var rect = svg.getBoundingClientRect();
        if (!rect.width || !rect.height) { return null; }
        var viewBox = svg.viewBox.baseVal;
        var sx = ((event.clientX - rect.left) / rect.width) * viewBox.width;
        var sy = ((event.clientY - rect.top) / rect.height) * viewBox.height;
        var x = (sx - wallSvgState.pad) / wallSvgState.scale;
        var y = currentWallModel.height_in - ((sy - wallSvgState.pad) / wallSvgState.scale);
        return {
            x: clampInches(x, 0, currentWallModel.length_in),
            y: clampInches(y, 0, currentWallModel.height_in),
        };
    }

    function makeDrawnMember(start, end, mode) {
        var id = 'custom_' + Date.now();
        var member = { id: id, source: 'custom', role: mode === 'add-stud' ? 'Custom stud' : 'Custom blocking', x: 0, y: 0, width: 1.5, height: 1.5 };
        applyDrawnMemberGeometry(member, start, end, mode);
        return member;
    }

    function applyDrawnMemberGeometry(member, start, end, mode) {
        if (mode === 'add-stud') {
            member.x = clampInches(start.x - 0.75, 0, Math.max(0, currentWallModel.length_in - 1.5));
            member.y = Math.min(start.y, end.y);
            member.width = 1.5;
            member.height = Math.max(1.5, Math.abs(end.y - start.y));
        } else {
            member.x = Math.min(start.x, end.x);
            member.y = Math.min(start.y, end.y);
            member.width = Math.max(1.5, Math.abs(end.x - start.x));
            member.height = Math.max(1.5, Math.abs(end.y - start.y));
        }
        member.y = clampInches(member.y, 0, currentWallModel.height_in - member.height);
        member.x = clampInches(member.x, 0, currentWallModel.length_in - member.width);
    }

    function applyMemberFormLive() {
        var member = currentWallModel.members.find(function (item) { return item.id === selectedWallMemberId; });
        if (!member) { return; }
        var next = Object.assign({}, member, {
            role: (document.getElementById('member-role-input') || {}).value || member.role,
            x: numericField('member-x-input', member.x),
            y: numericField('member-y-input', member.y),
            width: numericField('member-width-input', member.width),
            height: numericField('member-height-input', member.height),
        });
        next.width = Math.max(0.25, Math.min(next.width, currentWallModel.length_in - next.x));
        next.height = Math.max(0.25, Math.min(next.height, currentWallModel.height_in - next.y));
        applyMemberOverride(next, { skipRender: true });
        refreshWallViewsOnly();
        scheduleWallPersist();
    }

    function numericField(id, fallback) {
        var value = parseFloat(document.getElementById(id).value);
        return Number.isFinite(value) ? Math.max(0, value) : fallback;
    }

    function addCustomMember() {
        var template = currentWallModel.members.find(function (item) { return item.id === selectedWallMemberId; }) || { x: 0, y: 1.5, width: 1.5, height: currentWallModel.height_in - 4.5 };
        var member = Object.assign({}, template, {
            id: 'custom_' + Date.now(),
            source: 'custom',
            role: template.role.indexOf('blocking') !== -1 ? 'Custom blocking' : 'Custom stud',
            x: clampInches(template.x + 3, 0, currentWallModel.length_in - template.width),
        });
        currentWallModel.members.push(member);
        selectedWallMemberId = member.id;
        applyMemberOverride(member, { skipRender: true });
        renderWallEditors();
        scheduleWallPersist(true);
    }

    function deleteSelectedMember() {
        var member = currentWallModel.members.find(function (item) { return item.id === selectedWallMemberId; });
        if (!member) { return; }
        var overrides = wallOverrides();
        if (member.source === 'custom') {
            overrides.added = (overrides.added || []).filter(function (item) { return item.id !== member.id; });
        } else {
            overrides.deleted = overrides.deleted || [];
            if (overrides.deleted.indexOf(member.id) === -1) { overrides.deleted.push(member.id); }
            if (overrides.edited) { delete overrides.edited[member.id]; }
        }
        setWallOverrides(overrides);
        currentWallModel.members = currentWallModel.members.filter(function (item) { return item.id !== member.id; });
        selectedWallMemberId = null;
        renderWallEditors();
        scheduleWallPersist(true);
        updateWallEditStatus('Member deleted. Change auto-saved.');
    }

    function applyMemberOverride(member, options) {
        options = options || {};
        var overrides = wallOverrides();
        if (member.source === 'custom') {
            overrides.added = overrides.added || [];
            var found = false;
            overrides.added = overrides.added.map(function (item) {
                if (item.id === member.id) { found = true; return memberPayload(member); }
                return item;
            });
            if (!found) { overrides.added.push(memberPayload(member)); }
        } else {
            overrides.edited = overrides.edited || {};
            overrides.edited[member.id] = memberPayload(member);
        }
        setWallOverrides(overrides);
        currentWallModel.members = currentWallModel.members.map(function (item) {
            return item.id === member.id ? Object.assign({}, member, { source: member.source === 'custom' ? 'custom' : 'edited' }) : item;
        });
        currentWallModel.cut_list = buildCutListRowsFromMembers(currentWallModel.members);
        if (!options.skipRender) { renderWallEditors(); }
        if (!options.skipPersist) { scheduleWallPersist(); }
    }

    function memberPayload(member) {
        return { id: member.id, role: member.role, x: round3(member.x), y: round3(member.y), width: round3(member.width), height: round3(member.height) };
    }

    function round3(value) { return Math.round(parseFloat(value) * 1000) / 1000; }
    function clampInches(value, min, max) { return Math.max(min, Math.min(max, Number.isFinite(value) ? value : min)); }

    function wallOverrides() {
        var settings = (selectedTrace && selectedTrace.traceSettings) || {};
        return JSON.parse(JSON.stringify(settings.wall_member_overrides || { edited: {}, deleted: [], added: [] }));
    }

    function setWallOverrides(overrides) {
        if (!selectedTrace.traceSettings) { selectedTrace.traceSettings = {}; }
        selectedTrace.traceSettings.wall_member_overrides = overrides;
        currentWallModel.member_overrides = overrides;
    }

    function scheduleWallPersist(immediate) {
        if (wallPersistTimer) { clearTimeout(wallPersistTimer); }
        updateWallEditStatus('Editing live… auto-save pending.');
        wallPersistTimer = setTimeout(persistWallOverrides, immediate ? 25 : 450);
    }

    function persistWallOverrides() {
        if (!selectedTrace) { return; }
        updateWallEditStatus('Saving wall edits…');
        fetch(TRACE_UPDATE_URL_BASE.replace('0', selectedTrace.traceId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({
                material_id: selectedTrace.traceMaterialId || null,
                assembly_id: selectedTrace.traceAssemblyId || null,
                color: selectedTrace.traceColor || '#0d6efd',
                settings: selectedTrace.traceSettings || {},
            }),
        })
            .then(handleJsonResponse)
            .then(function (trace) {
                selectedTrace.traceSettings = trace.settings || selectedTrace.traceSettings;
                updateWallEditStatus('Saved. Keep dragging, resizing, or drawing members.');
            })
            .catch(function (error) {
                updateWallEditStatus('Save failed. Your onscreen edit remains visible; retry by editing again.');
                showError(error);
            });
    }

    function buildCutListRowsFromMembers(members) {
        var grouped = {};
        members.forEach(function (member) {
            var length = Math.round(Math.max(member.width, member.height) * 10) / 10;
            var key = member.role + '|' + length;
            grouped[key] = grouped[key] || { role: member.role, quantity: 0, length_in: length, length_ft: Math.round((length / 12) * 100) / 100 };
            grouped[key].quantity += 1;
        });
        return Object.keys(grouped).sort().map(function (key) { return grouped[key]; });
    }

    document.querySelectorAll('[data-wall-tab]').forEach(function (button) {
        button.addEventListener('click', function () {
            document.querySelectorAll('[data-wall-tab]').forEach(function (tabButton) { tabButton.classList.remove('active'); });
            document.querySelectorAll('.wall-modal-tab').forEach(function (panel) { panel.classList.remove('active'); });
            button.classList.add('active');
            document.getElementById('wall-tab-' + button.dataset.wallTab).classList.add('active');
        });
    });

    function memberFill(role) {
        if (role.indexOf('Plate') !== -1 || role.indexOf('plate') !== -1) { return '#e9ecef'; }
        if (role.indexOf('Header') !== -1) { return '#ffe8a1'; }
        if (role.indexOf('King') !== -1) { return '#d1e7dd'; }
        if (role.indexOf('Jack') !== -1) { return '#cff4fc'; }
        if (role.indexOf('cripple') !== -1 || role.indexOf('Cripple') !== -1) { return '#f8d7da'; }
        return '#dee2e6';
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, function (char) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
        });
    }

    // --------------------------------------------------------------- presets

    presetSelect.addEventListener('change', function () {
        var preset = presetsById[presetSelect.value];
        if (!preset) {
            updatePresetFavoriteButton();
            return;
        }
        materialSelect.value = preset.material_id || '';
        var settings = preset.settings || {};
        if (settings.stud_spacing_in) { studSpacingInput.value = settings.stud_spacing_in; }
        if (settings.wall_height_in) { wallHeightInput.value = settings.wall_height_in; }
        if (settings.spacing_in) { spacingInput.value = settings.spacing_in; }
        if (settings.member_direction) { directionSelect.value = settings.member_direction; }
        if (typeof settings.closed !== 'undefined') { closedInput.checked = settings.closed; }
        colorInput.value = preset.color || TOOLS[activeTool].color;
        populateAssemblyOptions(assemblySelect, activeTool, collectSettings(activeTool, ''));
        if (optionExists(assemblySelect, preset.assembly_id)) {
            assemblySelect.value = preset.assembly_id || '';
        }
        updatePresetFavoriteButton();
    });

    presetFavoriteButton.addEventListener('click', function () {
        var preset = presetsById[presetSelect.value];
        if (!preset) {
            return;
        }
        fetch(PRESET_FAVORITE_URL_BASE.replace('0', preset.id), {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
        })
            .then(handleJsonResponse)
            .then(function (data) {
                preset.is_favorite = data.is_favorite;
                populatePresetOptions(activeTool);
                presetSelect.value = preset.id;
                updatePresetFavoriteButton();
            })
            .catch(showError);
    });

    closedInput.addEventListener('change', function () {
        if (activeTool === 'polyline') {
            populateAssemblyOptions(assemblySelect, activeTool, collectSettings(activeTool, ''));
        }
    });

    document.getElementById('save-preset').addEventListener('click', function () {
        var name = presetNameInput.value.trim();
        if (!name || !activeTool || !TOOLS[activeTool]) {
            return;
        }
        fetch(PRESETS_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({
                name: name,
                tool_type: activeTool,
                material_id: materialSelect.value || null,
                assembly_id: assemblySelect.value || null,
                color: colorInput.value,
                settings: collectSettings(activeTool, ''),
            }),
        })
            .then(handleJsonResponse)
            .then(function (preset) {
                preset.tool_type = preset.tool_type || activeTool;
                presetsById[preset.id] = preset;
                populatePresetOptions(activeTool);
                presetSelect.value = preset.id;
                updatePresetFavoriteButton();
                presetNameInput.value = '';
            })
            .catch(showError);
    });

    // -------------------------------------------------------- trace CRUD/draw

    function createTrace(tool, geometry) {
        // Snapshot the tool + variant now: the async response resolves later,
        // by which point the user may have switched tools.
        var variantFilter = activeVariantFilter;
        var semanticKey = activeSemanticKey;
        createTraceFromSnapshot({
            toolType: tool,
            geometry: geometry,
            materialId: materialSelect.value || null,
            assemblyId: assemblySelect.value || null,
            parentWallId: null,
            color: colorInput.value,
            settings: collectSettings(tool, ''),
        })
            .then(function (trace) {
                if (trace.measurement_display) {
                    lastMeasurement.textContent = 'Last trace: ' + trace.measurement_display;
                }
                saveToolMemory(tool, variantFilter, semanticKey);
            })
            .catch(showError);
    }

    function deleteTrace(obj) {
        if (!obj || !obj.traceId) {
            return;
        }
        lastDeletedTraceSnapshot = traceSnapshotFromObject(obj);
        fetch(TRACE_DELETE_URL_BASE.replace('0', obj.traceId), {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
        }).then(function (response) {
            if (response.ok) {
                canvas.remove(obj);
                removeIncompleteMarker(obj.traceId);
                canvas.discardActiveObject();
                canvas.requestRenderAll();
                selectedTrace = null;
                showPanel(activeTool && TOOLS[activeTool] ? 'tool-settings' : 'none');
                refreshMaterialList();
                updateUndoDeleteUi();
            } else {
                lastDeletedTraceSnapshot = null;
                updateUndoDeleteUi();
            }
        });
    }

    function deleteLinkedTraces() {
        var matches = linkedTraceObjects();
        if (!matches.length) {
            return;
        }
        lastDeletedTraceSnapshot = matches.map(traceSnapshotFromObject).filter(Boolean);
        persistTraceBatchDelete(linkedTraceIds.slice())
            .then(function () {
                matches.forEach(function (obj) {
                    canvas.remove(obj);
                    removeIncompleteMarker(obj.traceId);
                });
            })
            .then(function () {
                canvas.discardActiveObject();
                selectedTrace = null;
                linkedTraceIds = [];
                activeMaterialSummary = null;
                activeLinkedTraceIndex = -1;
                focusLinkedMode = false;
                materialSelectedOnly = false;
                materialCategoryOnly = false;
                canvas.requestRenderAll();
                refreshMaterialList();
                updateUndoDeleteUi();
                updateMaterialToolbarState();
                showPanel(activeTool && TOOLS[activeTool] ? 'tool-settings' : 'none');
                lastMeasurement.textContent = 'Deleted linked traces.';
            })
            .catch(function (error) {
                lastDeletedTraceSnapshot = null;
                updateUndoDeleteUi();
                showError(error);
            });
    }

    function drawTrace(trace) {
        var obj = buildTraceObject(trace);
        obj.traceId = trace.id;
        obj.traceToolType = trace.tool_type;
        obj.traceMaterialId = trace.material_id;
        obj.traceAssemblyId = trace.assembly_id;
        obj.traceParentWallId = trace.parent_wall_id;
        obj.traceGeometry = trace.geometry || [];
        obj.traceColor = trace.color || '';
        obj.traceSettings = trace.settings || {};
        obj.traceMeasurement = trace.measurement_display || '';
        canvas.add(obj);
        updateIncompleteMarker(obj);
        canvas.requestRenderAll();
        return obj;
    }

    // ---------------------------------------------- confidence indicators
    // A small "!" badge over any trace missing the info it needs to
    // contribute to the material list, so incompleteness is visible without
    // opening the inspector for every trace. Kept separate from the
    // assembly-assigned green/default color (that signal already exists but
    // doesn't say *why* a trace is incomplete).
    var incompleteMarkers = {};

    function traceIsIncomplete(obj) {
        if (!obj.traceAssemblyId) {
            return true;
        }
        if (obj.traceToolType === 'opening' && !obj.traceParentWallId) {
            return true;
        }
        return false;
    }

    function incompleteReason(obj) {
        if (!obj.traceAssemblyId) {
            return 'No assembly assigned - this trace will not generate any materials.';
        }
        if (obj.traceToolType === 'opening' && !obj.traceParentWallId) {
            return 'Not attached to a wall - header/king/jack sizing may not auto-resolve.';
        }
        return '';
    }

    function removeIncompleteMarker(traceId) {
        var existing = incompleteMarkers[traceId];
        if (existing) {
            canvas.remove(existing);
            delete incompleteMarkers[traceId];
        }
    }

    function updateIncompleteMarker(obj) {
        removeIncompleteMarker(obj.traceId);
        if (!traceIsIncomplete(obj)) {
            return;
        }
        var anchor = obj.traceGeometry && obj.traceGeometry[0];
        if (!anchor) {
            return;
        }
        var marker = new fabric.Group([
            new fabric.Circle({
                radius: 8, fill: '#fd7e14', stroke: '#ffffff', strokeWidth: 1.5,
                originX: 'center', originY: 'center',
            }),
            new fabric.Text('!', {
                fontSize: 12, fontWeight: 'bold', fill: '#ffffff', fontFamily: 'sans-serif',
                originX: 'center', originY: 'center', top: -1,
            }),
        ], {
            left: anchor.x, top: anchor.y, selectable: false, evented: false,
        });
        incompleteMarkers[obj.traceId] = marker;
        canvas.add(marker);
    }

    function buildTraceObject(trace) {
        var config = TOOLS[trace.tool_type] || TOOLS.line;
        var color = trace.color || (trace.assembly_id ? config.activeColor : config.color);
        var points = trace.geometry;
        var common = { selectable: true, hasControls: false, lockMovementX: true, lockMovementY: true };

        if (trace.tool_type === 'area') {
            return new fabric.Polygon(points, Object.assign({
                fill: hexToRgba(color, 0.18), stroke: color, strokeWidth: 3,
            }, common));
        }
        if (trace.tool_type === 'polyline') {
            var PolyShape = trace.settings && trace.settings.closed ? fabric.Polygon : fabric.Polyline;
            return new PolyShape(points, Object.assign({
                fill: trace.settings && trace.settings.closed ? hexToRgba(color, 0.18) : '',
                stroke: color, strokeWidth: 4,
            }, common));
        }
        if (trace.tool_type === 'count') {
            var circles = points.map(function (point) {
                return new fabric.Circle({
                    left: point.x - 7, top: point.y - 7, radius: 7,
                    fill: hexToRgba(color, 0.6), stroke: color, strokeWidth: 2,
                });
            });
            return new fabric.Group(circles, common);
        }
        var line = new fabric.Line(
            [points[0].x, points[0].y, points[1].x, points[1].y],
            Object.assign({ stroke: color, strokeWidth: 4 }, common),
        );
        if (trace.tool_type === 'opening') {
            line.set({ strokeDashArray: [10, 6], strokeWidth: 6 });
        }
        return line;
    }

    function restyleTrace(obj) {
        var config = TOOLS[obj.traceToolType] || TOOLS.line;
        var color = obj.traceColor || (obj.traceAssemblyId ? config.activeColor : config.color);
        var isLinked = linkedTraceIds.indexOf(obj.traceId) !== -1;
        var isHovered = hoveredTraceIds.indexOf(obj.traceId) !== -1;
        var lineWidth = isLinked ? 7 : 4;
        var fillAlpha = isLinked ? 0.28 : (isHovered ? 0.24 : 0.18);
        var opacity = focusLinkedMode && linkedTraceIds.length ? (isLinked ? 1 : 0.12) : (isHovered ? 0.95 : 1);
        if (!isLinked && isHovered) {
            lineWidth = 6;
        }
        if (obj.traceToolType === 'area' || obj.traceToolType === 'polyline') {
            obj.set({ stroke: color, strokeWidth: lineWidth, fill: hexToRgba(color, fillAlpha), opacity: opacity });
            if (obj.traceToolType === 'polyline' && !(obj.traceSettings || {}).closed) {
                obj.set({ fill: '' });
            }
        } else if (obj.traceToolType === 'count') {
            obj.set({ opacity: opacity });
            obj.getObjects().forEach(function (circle) {
                circle.set({
                    stroke: color,
                    strokeWidth: isLinked ? 4 : (isHovered ? 3 : 2),
                    fill: hexToRgba(color, isLinked ? 0.8 : (isHovered ? 0.72 : 0.6)),
                });
            });
        } else {
            obj.set({
                stroke: color,
                strokeWidth: obj.traceToolType === 'opening' ? (isLinked ? 8 : (isHovered ? 7 : 6)) : lineWidth,
                opacity: opacity,
            });
        }
    }

    function hexToRgba(hex, alpha) {
        var r = parseInt(hex.slice(1, 3), 16);
        var g = parseInt(hex.slice(3, 5), 16);
        var b = parseInt(hex.slice(5, 7), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    // ------------------------------------------------------------------ misc

    // A one-time onboarding tip ("select a tool to draw...") - shown until the
    // user dismisses it or picks any tool for the first time (see
    // activateTool), whichever comes first, then never again on any project.
    // Persisted in localStorage (not sessionStorage) since this is about the
    // user's familiarity with the app, not any one page/session.
    var ONBOARDING_TIP_KEY = 'planViewerOnboardingTipDismissed';
    var onboardingTipTimer = null;

    function onboardingTipDismissed() {
        try {
            if (window.localStorage.getItem(ONBOARDING_TIP_KEY) === '1') {
                return true;
            }
        } catch (e) { /* storage unavailable */ }
        return document.cookie.indexOf(ONBOARDING_TIP_KEY + '=1') !== -1;
    }

    function persistOnboardingTipDismissal() {
        try {
            window.localStorage.setItem(ONBOARDING_TIP_KEY, '1');
        } catch (e) { /* storage unavailable */ }
        document.cookie = ONBOARDING_TIP_KEY + '=1; path=/; max-age=' + (60 * 60 * 24 * 365);
    }

    function dismissOnboardingTip() {
        if (onboardingTipTimer) {
            window.clearTimeout(onboardingTipTimer);
            onboardingTipTimer = null;
        }
        persistOnboardingTipDismissal();
        noSelectionPanel.style.display = 'none';
        refreshToolPanelVisibility();
    }

    function scheduleOnboardingTipAutoDismiss() {
        if (onboardingTipTimer || onboardingTipDismissed()) {
            return;
        }
        onboardingTipTimer = window.setTimeout(function () {
            onboardingTipTimer = null;
            dismissOnboardingTip();
        }, 5000);
    }

    if (dismissOnboardingTipButton) {
        dismissOnboardingTipButton.addEventListener('click', dismissOnboardingTip);
    }

    // The tool panel is a real box (border/padding) only while it has
    // something to show - the tool-settings form, the trace inspector, a
    // tool-specific hint (Calibrate/Hand), or the one-time onboarding tip.
    // Otherwise it collapses away entirely rather than sitting there empty.
    function refreshToolPanelVisibility() {
        var anyVisible = noSelectionPanel.style.display !== 'none' ||
            calibratePanel.style.display !== 'none' ||
            toolSettingsPanel.style.display !== 'none' ||
            traceInspectorPanel.style.display !== 'none' ||
            bulkSelectionPanel.style.display !== 'none' ||
            Boolean(toolHint.textContent);
        toolPanelEl.style.display = anyVisible ? '' : 'none';
    }

    function showPanel(name) {
        noSelectionPanel.style.display = (name === 'none' && !onboardingTipDismissed()) ? '' : 'none';
        calibratePanel.style.display = name === 'calibrate' ? '' : 'none';
        toolSettingsPanel.style.display = name === 'tool-settings' ? '' : 'none';
        traceInspectorPanel.style.display = name === 'inspector' ? '' : 'none';
        bulkSelectionPanel.style.display = name === 'bulk' ? '' : 'none';
        if (noSelectionPanel.style.display !== 'none') {
            scheduleOnboardingTipAutoDismiss();
        } else if (onboardingTipTimer) {
            window.clearTimeout(onboardingTipTimer);
            onboardingTipTimer = null;
        }
        refreshToolPanelVisibility();
    }

    function handleJsonResponse(response) {
        return response.json().then(function (data) {
            if (!response.ok) {
                throw new Error(data.error || 'Something went wrong.');
            }
            return data;
        });
    }

    function showError(err) {
        window.alert(err.message);
    }

    function getCookie(name) {
        var match = document.cookie.match('(^|;\\s*)' + name + '=([^;]*)');
        return match ? decodeURIComponent(match[2]) : null;
    }

    // Set panel defaults from JobSettings
    studSpacingInput.value = defaultStudSpacing;
    spacingInput.value = defaultStudSpacing;
    wallHeightInput.value = defaultWallHeight;
    applyPageHandoffState();
});
