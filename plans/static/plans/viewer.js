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
    var PRESETS_URL = root.dataset.presetsUrl;

    var noSelectionPanel = document.getElementById('no-selection-panel');
    var toolSettingsPanel = document.getElementById('tool-settings-panel');
    var traceInspectorPanel = document.getElementById('trace-inspector-panel');

    var materialSelect = document.getElementById('material-select');
    var studSpacingInput = document.getElementById('stud-spacing-input');
    var presetSelect = document.getElementById('preset-select');
    var presetNameInput = document.getElementById('preset-name-input');
    var lineToolButton = document.getElementById('tool-line');
    var deleteButton = document.getElementById('delete-selected');

    var inspectorMaterialSelect = document.getElementById('inspector-material-select');
    var inspectorStudSpacingInput = document.getElementById('inspector-stud-spacing-input');
    var saveTraceChangesButton = document.getElementById('save-trace-changes');
    var deleteInspectedButton = document.getElementById('delete-inspected-trace');

    var initialTraces = JSON.parse(document.getElementById('traces-data').textContent);
    var presetsById = {};
    JSON.parse(document.getElementById('presets-data').textContent).forEach(function (preset) {
        presetsById[preset.id] = preset;
    });

    var csrftoken = getCookie('csrftoken');
    var canvas = new fabric.Canvas('plan-canvas', { selection: true });
    var activeTool = null;
    var drawStart = null;
    var selectedTrace = null;

    showPanel('none');

    fabric.Image.fromURL(IMAGE_URL, function (img) {
        canvas.setWidth(img.width);
        canvas.setHeight(img.height);
        canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
        initialTraces.forEach(drawTraceLine);
    });

    lineToolButton.addEventListener('click', function () {
        activeTool = activeTool === 'line' ? null : 'line';
        lineToolButton.classList.toggle('active', activeTool === 'line');
        canvas.selection = activeTool !== 'line';
        canvas.defaultCursor = activeTool === 'line' ? 'crosshair' : 'default';
        drawStart = null;
        canvas.discardActiveObject();
        canvas.requestRenderAll();
        showPanel(activeTool === 'line' ? 'tool-settings' : 'none');
    });

    canvas.on('mouse:down', function (opt) {
        if (activeTool !== 'line') {
            return;
        }
        var pointer = canvas.getPointer(opt.e);
        if (!drawStart) {
            if (opt.target) {
                return;
            }
            drawStart = pointer;
        } else {
            createTrace([{ x: drawStart.x, y: drawStart.y }, { x: pointer.x, y: pointer.y }]);
            drawStart = null;
        }
    });

    canvas.on('selection:created', onTraceSelected);
    canvas.on('selection:updated', onTraceSelected);
    canvas.on('selection:cleared', onTraceDeselected);

    function onTraceSelected() {
        var obj = canvas.getActiveObject();
        if (!obj || !obj.traceId) {
            return;
        }
        activeTool = null;
        lineToolButton.classList.remove('active');
        canvas.defaultCursor = 'default';

        selectedTrace = obj;
        inspectorMaterialSelect.value = obj.traceMaterialId || '';
        inspectorStudSpacingInput.value = (obj.traceSettings && obj.traceSettings.stud_spacing_in) || '';
        showPanel('inspector');
    }

    function onTraceDeselected() {
        selectedTrace = null;
        showPanel(activeTool === 'line' ? 'tool-settings' : 'none');
    }

    deleteButton.addEventListener('click', function () {
        deleteTrace(canvas.getActiveObject());
    });

    deleteInspectedButton.addEventListener('click', function () {
        deleteTrace(selectedTrace);
    });

    saveTraceChangesButton.addEventListener('click', function () {
        if (!selectedTrace) {
            return;
        }
        var materialId = inspectorMaterialSelect.value || null;
        var settings = { stud_spacing_in: parseInt(inspectorStudSpacingInput.value, 10) || null };
        fetch(TRACE_UPDATE_URL_BASE.replace('0', selectedTrace.traceId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ material_id: materialId, settings: settings }),
        })
            .then(function (response) { return response.json(); })
            .then(function (trace) {
                selectedTrace.traceMaterialId = trace.material_id;
                selectedTrace.traceSettings = trace.settings || {};
            });
    });

    presetSelect.addEventListener('change', function () {
        var preset = presetsById[presetSelect.value];
        if (!preset) {
            return;
        }
        materialSelect.value = preset.material_id || '';
        if (preset.settings && preset.settings.stud_spacing_in) {
            studSpacingInput.value = preset.settings.stud_spacing_in;
        }
    });

    document.getElementById('save-preset').addEventListener('click', function () {
        var name = presetNameInput.value.trim();
        if (!name) {
            return;
        }
        fetch(PRESETS_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({
                name: name,
                tool_type: 'line',
                material_id: materialSelect.value || null,
                settings: { stud_spacing_in: parseInt(studSpacingInput.value, 10) || null },
            }),
        })
            .then(function (response) { return response.json(); })
            .then(function (preset) {
                presetsById[preset.id] = preset;
                var existing = presetSelect.querySelector('option[value="' + preset.id + '"]');
                if (!existing) {
                    existing = document.createElement('option');
                    existing.value = preset.id;
                    presetSelect.appendChild(existing);
                }
                existing.textContent = preset.name;
                presetNameInput.value = '';
            });
    });

    function createTrace(geometry) {
        fetch(TRACE_CREATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({
                tool_type: 'line',
                geometry: geometry,
                material_id: materialSelect.value || null,
                settings: { stud_spacing_in: parseInt(studSpacingInput.value, 10) || null },
            }),
        })
            .then(function (response) { return response.json(); })
            .then(drawTraceLine);
    }

    function deleteTrace(obj) {
        if (!obj || !obj.traceId) {
            return;
        }
        fetch(TRACE_DELETE_URL_BASE.replace('0', obj.traceId), {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
        }).then(function (response) {
            if (response.ok) {
                canvas.remove(obj);
                canvas.discardActiveObject();
                canvas.requestRenderAll();
                selectedTrace = null;
                showPanel(activeTool === 'line' ? 'tool-settings' : 'none');
            }
        });
    }

    function drawTraceLine(trace) {
        var points = trace.geometry;
        var line = new fabric.Line(
            [points[0].x, points[0].y, points[1].x, points[1].y],
            { stroke: '#0d6efd', strokeWidth: 4, selectable: true, hasControls: false },
        );
        line.traceId = trace.id;
        line.traceMaterialId = trace.material_id;
        line.traceSettings = trace.settings || {};
        canvas.add(line);
        canvas.requestRenderAll();
    }

    function showPanel(name) {
        noSelectionPanel.style.display = name === 'none' ? '' : 'none';
        toolSettingsPanel.style.display = name === 'tool-settings' ? '' : 'none';
        traceInspectorPanel.style.display = name === 'inspector' ? '' : 'none';
    }

    function getCookie(name) {
        var match = document.cookie.match('(^|;\\s*)' + name + '=([^;]*)');
        return match ? decodeURIComponent(match[2]) : null;
    }
});
