import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const fixture = JSON.parse(fs.readFileSync('tests/fixtures/cf031-technical-boundary-read.json', 'utf8'));
const registry = new Map();
function load(file) {
  const compiled = {exports: {}};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS},
  }).outputText, {module: compiled, exports: compiled.exports, structuredClone, Object, Array, Set, Date,
    require(name) {assert.ok(registry.has(name), 'Closed pure registry'); return registry.get(name);}}, {timeout: 100});
  return compiled.exports;
}
const projection = load('src/features/technical/lib/boundary-preview.ts');
// Separate VM modules have separate object-literal prototypes. Transfer already
// validated props into the projection's input realm, as structuredClone does at
// a real realm boundary; the decoder still checks every untrusted input first.
registry.set('./boundary-preview', {boundaryPreview(value) {return projection.boundaryPreview(structuredClone(value));}});
const {decodeTechnicalBoundary: decode} = load('src/features/technical/lib/strict-boundary-read.ts');
const chart = load('src/features/technical/lib/chart.ts');
const clone = value => structuredClone(value);
const reject = (value, expected = fixture.expected) => assert.throws(() => decode(value, expected), /Invalid Technical boundary read/);

test('shared response decodes against independent expected request and retains detached chart props', () => {
  const before = clone(fixture);
  const decoded = decode(fixture.response, fixture.expected);
  assert.equal(decoded.kind, 'success');
  assert.deepEqual(decoded.preview, fixture.expected_preview);
  assert.equal(decoded.coverage.cutoff_validation, 'unverified');
  assert.equal(decoded.coverage.engine_generated_at, null);
  assert.equal(decoded.coverage.source_published_at, null);
  decoded.preview.stock.stock_name = 'detached';
  decoded.coverage.periods[0].count = 999;
  assert.deepEqual(fixture, before);
});

for (const attack of fixture.attacks) test('shared packet rejects ' + attack.name, () => {
  const packet = clone(fixture.response); let target = packet;
  for (const key of attack.path.slice(0, -1)) target = target[key];
  target[attack.path.at(-1)] = attack.value; reject(packet);
});

test('normal safe error envelope remains a typed failure', () => {
  const packet = clone(fixture.response);
  packet.data = null; packet.error = {code: 'BUSY', message: 'Technical boundary unavailable'};
  assert.deepEqual(clone(decode(packet, fixture.expected)), {kind: 'error', error: packet.error});
  packet.error.message = 'private upstream detail'; reject(packet);
  packet.error = null; reject(packet);
  packet.error = {code: 'UNKNOWN'}; reject(packet);
});

test('independent supplied digest and exact raw request snapshot include default omissions', () => {
  const expected = clone(fixture.expected), response = clone(fixture.response);
  delete expected.request.data.conditions; delete response.data.request_snapshot.conditions;
  // No hash is calculated here. The caller supplies its independent opaque digest.
  expected.request_sha256 = 'a'.repeat(64); response.data.request_sha256 = expected.request_sha256;
  assert.equal(decode(response, expected).kind, 'success');
  response.data.request_snapshot.conditions = {}; reject(response, expected);
  response.data.request_snapshot = clone(expected.request.data);
  response.data.request_sha256 = 'A'.repeat(64); reject(response, expected);
  response.data.request_sha256 = fixture.expected.request_sha256; reject(response, expected);
});

test('empty and missing chart coverage must describe the actual result', () => {
  const response = clone(fixture.response); delete response.data.result.charts;
  response.data.coverage.available_periods = [];
  for (const row of response.data.coverage.periods) Object.assign(row, {start: null, end: null, count: 0, status: 'not_provided'});
  assert.deepEqual(decode(response, fixture.expected).preview.charts, []);
  response.data.coverage.periods[0].status = 'empty'; reject(response);
  delete response.data.coverage; reject(response);
});

test('zero, negative zero, null and nested annotation values survive without coercion', () => {
  const response = clone(fixture.response);
  const data = response.data.result.charts[0].chart_data;
  data.candles[0].open = -0;
  data.annotations[0].price = -0;
  data.annotations[0].meta = {zero: 0, negative_zero: -0, null: null, nested: [false, '한글', -0]};
  data.subcharts.rsi.points[0].value = -0;
  data.annotations.find(x => x.kind === 'rsi_oversold').meta.rsi = -0;
  const decoded = decode(response, fixture.expected).preview.charts[0];
  assert.ok(Object.is(decoded.chart_data.candles[0].open, -0));
  assert.ok(Object.is(decoded.annotations[0].price, -0));
  assert.ok(Object.is(decoded.annotations[0].meta.negative_zero, -0));
  assert.ok(Object.is(decoded.annotations[0].meta.nested[2], -0));
  assert.ok(Object.is(chart.getRsiAnnotations(decoded.annotations)[0].rsi, -0));
  assert.equal(decoded.annotations.find(x => x.kind === 'rsi_oversold').price, null);
  assert.ok(Object.is(JSON.parse('{"value":-0}').value, -0));
  for (const raw of fixture.numeric_texts) assert.ok(Object.hasOwn(JSON.parse(raw), 'value'));
  response.data.coverage.periods[1].count = -0; reject(response);
});

const cases = {
  'nonfinite': p => {p.data.result.charts[0].chart_data.candles[0].open = Infinity;},
  'unsafe integer': p => {p.data.result.charts[0].chart_data.candles[0].volume = 2 ** 53;},
  'NaN meta': p => {p.data.result.charts[0].chart_data.annotations[0].meta = {x: NaN};},
  'undefined': p => {p.data.result.charts[0].chart_data.annotations[0].price = undefined;},
  'duplicate period': p => {p.data.result.charts.push(clone(p.data.result.charts[0]));},
  'date order': p => {p.data.result.charts[0].chart_data.candles.reverse();},
  'RSI bound': p => {p.data.result.charts[0].chart_data.subcharts.rsi.points[0].value = 101;},
  'RSI thresholds': p => {p.data.result.charts[0].chart_data.subcharts.rsi.oversold = 80;},
  'unknown annotation': p => {p.data.result.charts[0].chart_data.annotations[0].kind = 'new_signal';},
  'missing annotation': p => {delete p.data.result.charts[0].chart_data.annotations;},
  'array hole': p => {delete p.data.result.charts[0].chart_data.candles[0];},
  'array extra key': p => {p.data.result.charts.extra = 1;},
  'custom prototype': p => {Object.setPrototypeOf(p.data.coverage, {inherited: 1});},
  'null prototype': p => {Object.setPrototypeOf(p.data.coverage, null);},
  'accessor': p => {Object.defineProperty(p.data.coverage, 'extra', {enumerable: true, get() {throw Error('Must not execute getter');}});},
  'symbol': p => {p.data.coverage[Symbol('hidden')] = 0;},
  'nonenumerable': p => {Object.defineProperty(p.data.coverage, 'hidden', {value: 0});},
  'cycle': p => {p.data.coverage.extra = p;},
  'unpaired surrogate': p => {p.data.request_snapshot.original_query = '\ud800';},
  'both success and error': p => {p.error = {code: 'BUSY'};},
};
for (const [name, mutate] of Object.entries(cases)) test('unknown rejects ' + name, () => {
  const response = clone(fixture.response); mutate(response); reject(response);
});

test('expected itself must have exact request fields, IDs, stock and conditions', () => {
  for (const mutate of [
    e => {e.request.data.context.report_id = e.request.request_id;},
    e => {e.request.data.conditions.periods = ['3m'];},
    e => {e.request.data.requested_as_of = '2026-02-30T00:00:00Z';},
    e => {e.request.data.stock.stock_name = '';},
    e => {e.request.data.context.owner = 'not an authentication field';},
    e => {e.request.error = {code: 'BUSY'};},
  ]) {const expected = clone(fixture.expected); mutate(expected); reject(fixture.response, expected);}
});

test('raw text attacks belong to backend restoration, parsed unknown is not a duplicate-key detector', () => {
  assert.ok(fixture.raw_text_attacks.some(raw => raw === '{"a":1,"a":2}'));
  assert.equal(JSON.parse('{"a":1,"a":2}').a, 2);
  for (const raw of fixture.raw_text_attacks) reject(raw);
});
