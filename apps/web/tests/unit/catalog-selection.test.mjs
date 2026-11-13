import assert from 'node:assert/strict';
import test from 'node:test';
import { chooseCatalog } from '../../src/features/intake/catalog-selection.mjs';
const catalogs = [
 { catalog_id: 'older', curriculum_year: 2025 },
 { catalog_id: 'future', curriculum_year: 2027 },
 { catalog_id: 'current', curriculum_year: 2026 },
];
test('empty, single, saved choice, and current academic year priority', () => {
 assert.equal(chooseCatalog([], null, 2026), '');
 assert.equal(chooseCatalog([catalogs[0]], 'removed', 2026), 'older');
 assert.equal(chooseCatalog(catalogs, 'older', 2026), 'older');
 assert.equal(chooseCatalog(catalogs, 'removed', 2026), 'current');
 assert.equal(chooseCatalog(catalogs, null, 2027), 'future');
 assert.equal(chooseCatalog(catalogs, null, 2028), 'future');
 assert.equal(chooseCatalog([...catalogs].reverse(), null, 2026), 'current');
});
test('missing year uses a stable id tie-break without mutating API results', () => {
 const source = [{ catalog_id: 'b', curriculum_year: null }, { catalog_id: 'a', curriculum_year: null }];
 assert.equal(chooseCatalog(source, null, 2026), 'a');
 assert.deepEqual(source.map(c => c.catalog_id), ['b', 'a']);
});
