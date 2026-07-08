/*
 * Pure helpers for the plan viewer: geometry math and formatting with no DOM,
 * canvas, or fabric dependencies. Extracted from viewer.js so they can be
 * unit-tested under node (node --test js_tests/viewer-helpers.test.js) while the browser keeps
 * loading them as a plain script (window.LumberViewerHelpers), no build step.
 */
(function (root, factory) {
    'use strict';
    var helpers = factory();
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = helpers;
    }
    if (root) {
        root.LumberViewerHelpers = helpers;
    }
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    // "12.5" feet -> 12'-6". Inches round to whole; 11.96 ft rolls to 12'-0".
    function formatFeetInches(feet) {
        var wholeFeet = Math.floor(feet);
        var inches = Math.round((feet - wholeFeet) * 12);
        if (inches === 12) {
            wholeFeet += 1;
            inches = 0;
        }
        return wholeFeet + "'-" + inches + '"';
    }

    // "12,34,notanumber," -> [12, 34]. Tolerates null/empty input.
    function parseTraceIds(rawValue) {
        if (!rawValue) {
            return [];
        }
        return String(rawValue).split(',').map(function (value) {
            return parseInt(value, 10);
        }).filter(function (value) {
            return !isNaN(value);
        });
    }

    // Projects p onto the segment a-b, clamped to the segment. Returns the
    // projected point plus the segment's unit vector, or null for a
    // zero-length segment.
    function projectPointToSegment(a, b, p) {
        var abx = b.x - a.x;
        var aby = b.y - a.y;
        var lengthSq = abx * abx + aby * aby;
        if (lengthSq === 0) {
            return null;
        }
        var t = Math.max(0, Math.min(1, ((p.x - a.x) * abx + (p.y - a.y) * aby) / lengthSq));
        return {
            point: { x: a.x + t * abx, y: a.y + t * aby },
            ux: abx / Math.sqrt(lengthSq),
            uy: aby / Math.sqrt(lengthSq),
        };
    }

    // Locks the previous->pointer segment to the nearest 45-degree increment
    // when within toleranceRad of it; otherwise returns the pointer untouched.
    // Distance from the previous point is preserved exactly.
    function snapToOrtho(previous, pointer, toleranceRad) {
        var dx = pointer.x - previous.x;
        var dy = pointer.y - previous.y;
        var dist = Math.hypot(dx, dy);
        if (dist < 1) {
            return pointer;
        }
        var angle = Math.atan2(dy, dx);
        var step = Math.PI / 4;
        var snapped = Math.round(angle / step) * step;
        if (Math.abs(angle - snapped) > toleranceRad) {
            return pointer;
        }
        return { x: previous.x + dist * Math.cos(snapped), y: previous.y + dist * Math.sin(snapped) };
    }

    // Nearest of `points` to `pointer` within `radius`, or null. Ties keep the
    // earliest point, matching the original first-wins iteration order.
    function nearestPointWithin(points, pointer, radius) {
        var bestDist = radius;
        var best = null;
        (points || []).forEach(function (point) {
            var dist = Math.hypot(point.x - pointer.x, point.y - pointer.y);
            if (dist < bestDist || (dist === bestDist && best === null)) {
                best = point;
                bestDist = dist;
            }
        });
        return best ? { x: best.x, y: best.y } : null;
    }

    // Nearest projection of `pointer` onto any segment of any geometry (an
    // array of point arrays) within `maxDist`. Returns {point, ux, uy} or
    // null. Single-point geometries contribute no segments.
    function nearestSegmentProjection(geometries, pointer, maxDist) {
        var best = null;
        var bestDist = maxDist;
        (geometries || []).forEach(function (geometry) {
            var points = geometry || [];
            for (var i = 0; i < points.length - 1; i += 1) {
                var projection = projectPointToSegment(points[i], points[i + 1], pointer);
                if (!projection) {
                    continue;
                }
                var dist = Math.hypot(projection.point.x - pointer.x, projection.point.y - pointer.y);
                if (dist <= bestDist) {
                    best = projection;
                    bestDist = dist;
                }
            }
        });
        return best;
    }

    return {
        formatFeetInches: formatFeetInches,
        parseTraceIds: parseTraceIds,
        projectPointToSegment: projectPointToSegment,
        snapToOrtho: snapToOrtho,
        nearestPointWithin: nearestPointWithin,
        nearestSegmentProjection: nearestSegmentProjection,
    };
});
