'use strict';
// Unit tests for the plan viewer pure helpers.
// Run with: node --test js_tests/viewer-helpers.test.js
// Also executed by the Django suite via plans/test_js_helpers.py.
const test = require('node:test');
const assert = require('node:assert/strict');

const helpers = require('../plans/static/plans/viewer-helpers.js');

test('formatFeetInches renders whole and fractional feet', () => {
    assert.equal(helpers.formatFeetInches(0), '0\'-0"');
    assert.equal(helpers.formatFeetInches(12.5), '12\'-6"');
    assert.equal(helpers.formatFeetInches(9.25), '9\'-3"');
});

test('formatFeetInches rolls 12 rounded inches into the next foot', () => {
    // 11.99 ft = 11 ft 11.88 in, which rounds to 12 in -> 12'-0"
    assert.equal(helpers.formatFeetInches(11.99), '12\'-0"');
});

test('parseTraceIds tolerates junk and empty input', () => {
    assert.deepEqual(helpers.parseTraceIds('12,34,56'), [12, 34, 56]);
    assert.deepEqual(helpers.parseTraceIds('12,notanumber,,34'), [12, 34]);
    assert.deepEqual(helpers.parseTraceIds(''), []);
    assert.deepEqual(helpers.parseTraceIds(null), []);
});

test('projectPointToSegment projects onto the segment interior', () => {
    const projection = helpers.projectPointToSegment({ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 4, y: 3 });
    assert.deepEqual(projection.point, { x: 4, y: 0 });
    assert.equal(projection.ux, 1);
    assert.equal(projection.uy, 0);
});

test('projectPointToSegment clamps beyond the endpoints', () => {
    const before = helpers.projectPointToSegment({ x: 0, y: 0 }, { x: 10, y: 0 }, { x: -5, y: 2 });
    assert.deepEqual(before.point, { x: 0, y: 0 });
    const after = helpers.projectPointToSegment({ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 15, y: 2 });
    assert.deepEqual(after.point, { x: 10, y: 0 });
});

test('projectPointToSegment returns null for a zero-length segment', () => {
    assert.equal(helpers.projectPointToSegment({ x: 3, y: 3 }, { x: 3, y: 3 }, { x: 0, y: 0 }), null);
});

test('snapToOrtho locks near-square segments and preserves length', () => {
    const tolerance = 8 * Math.PI / 180;
    // 3 degrees off horizontal: snaps onto the axis at the same distance.
    const angled = { x: 100 * Math.cos(0.05), y: 100 * Math.sin(0.05) };
    const snapped = helpers.snapToOrtho({ x: 0, y: 0 }, angled, tolerance);
    assert.ok(Math.abs(snapped.y) < 1e-9, 'snapped onto the horizontal axis');
    assert.ok(Math.abs(Math.hypot(snapped.x, snapped.y) - 100) < 1e-9, 'distance preserved');
});

test('snapToOrtho snaps to 45-degree diagonals too', () => {
    const tolerance = 8 * Math.PI / 180;
    const nearDiagonal = { x: 100 * Math.cos(Math.PI / 4 + 0.05), y: 100 * Math.sin(Math.PI / 4 + 0.05) };
    const snapped = helpers.snapToOrtho({ x: 0, y: 0 }, nearDiagonal, tolerance);
    assert.ok(Math.abs(snapped.x - snapped.y) < 1e-9, 'landed on the 45-degree diagonal');
});

test('snapToOrtho leaves free angles alone', () => {
    const tolerance = 8 * Math.PI / 180;
    const pointer = { x: 100 * Math.cos(0.4), y: 100 * Math.sin(0.4) }; // ~23 degrees
    assert.deepEqual(helpers.snapToOrtho({ x: 0, y: 0 }, pointer, tolerance), pointer);
});

test('snapToOrtho ignores sub-pixel moves', () => {
    const pointer = { x: 0.3, y: 0.2 };
    assert.deepEqual(helpers.snapToOrtho({ x: 0, y: 0 }, pointer, 1), pointer);
});

test('nearestPointWithin picks the closest candidate inside the radius', () => {
    const points = [{ x: 20, y: 0 }, { x: 5, y: 0 }, { x: 9, y: 0 }];
    assert.deepEqual(helpers.nearestPointWithin(points, { x: 0, y: 0 }, 10), { x: 5, y: 0 });
});

test('nearestPointWithin returns null when everything is out of range', () => {
    assert.equal(helpers.nearestPointWithin([{ x: 50, y: 50 }], { x: 0, y: 0 }, 10), null);
    assert.equal(helpers.nearestPointWithin([], { x: 0, y: 0 }, 10), null);
});

test('nearestSegmentProjection finds the closest segment across geometries', () => {
    const geometries = [
        [{ x: 0, y: 100 }, { x: 100, y: 100 }],            // 100 away
        [{ x: 0, y: 10 }, { x: 100, y: 10 }],              // 10 away (winner)
        [{ x: 500, y: 500 }],                              // single point, no segments
    ];
    const projection = helpers.nearestSegmentProjection(geometries, { x: 50, y: 0 }, 25);
    assert.deepEqual(projection.point, { x: 50, y: 10 });
    assert.equal(projection.ux, 1);
});

test('nearestSegmentProjection respects maxDist', () => {
    const geometries = [[{ x: 0, y: 10 }, { x: 100, y: 10 }]];
    assert.equal(helpers.nearestSegmentProjection(geometries, { x: 50, y: 0 }, 5), null);
});
