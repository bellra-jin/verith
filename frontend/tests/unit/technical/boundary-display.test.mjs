import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import vm from 'node:vm';
import ts from 'typescript';

const cap = JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP, 'utf8'));
const productionFiles = ['react/cjs/react.production.js', 'react/cjs/react-jsx-runtime.production.js',
  'react-dom/cjs/react-dom.production.js', 'react-dom/cjs/react-dom-client.production.js',
  'scheduler/cjs/scheduler.production.js'];
assert.equal(cap.cf032Display, true);
assert.equal(cap.workload, 'unit');
assert.deepEqual(cap.ports, []);
assert.ok(cap.lifetime <= 120);
assert.equal(cap.cf022Core, undefined);
assert.deepEqual(cap.reactProduction.map(record => record.relative), productionFiles);
const production = cap.reactProduction.map(record => {
  const filename = path.join(cap.dependency, record.relative);
  const stat = fs.lstatSync(filename), bytes = fs.readFileSync(filename);
  assert.equal(fs.realpathSync(filename), filename);
  assert.ok(stat.isFile()); assert.equal(stat.nlink, 1); assert.equal(bytes.length, record.size);
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), record.sha256);
  const identity = record.identity.at(-1), actual = fs.lstatSync(filename, {bigint: true});
  for (const [key, field] of [['dev', 'dev'], ['ino', 'ino'], ['mode', 'mode'], ['size', 'size'],
    ['mtime', 'mtimeNs'], ['ctime', 'ctimeNs'], ['nlink', 'nlink']]) assert.equal(identity[key], String(actual[field]));
  return bytes.toString();
});

const registry = new Map();
function evaluate(source) {
  const compiled = {exports: {}};
  vm.runInNewContext(source, {module: compiled, exports: compiled.exports, Object, Array, Set, Date,
    structuredClone, process: {env: {NODE_ENV: 'production'}},
    require(name) {assert.ok(registry.has(name), 'Closed production display registry: ' + name); return registry.get(name);}}, {timeout: 100});
  return compiled.exports;
}
function load(filename) {
  return evaluate(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText);
}
const React = evaluate(production[0]); registry.set('react', React);
assert.equal(React.version, cap.reactProduction[0].version);
registry.set('react/jsx-runtime', evaluate(production[1]));
const projection = load('src/features/technical/lib/boundary-preview.ts');
// Only a cross-VM realm transfer after validation; the real preview still runs.
registry.set('./boundary-preview', {boundaryPreview: value => projection.boundaryPreview(structuredClone(value))});
const decoder = load('src/features/technical/lib/strict-boundary-read.ts');
registry.set('../lib/strict-boundary-read', decoder);
function PanelSentinel() {throw Error('Panel execution is outside element-composition acceptance');}
registry.set('./technical-chart-panel', {TechnicalChartPanel: PanelSentinel});
const {TechnicalBoundaryPreview: view} = load('src/features/technical/components/technical-boundary-preview.tsx');
const fixture = JSON.parse(fs.readFileSync('tests/fixtures/cf031-technical-boundary-read.json', 'utf8'));
const clone = value => structuredClone(value);
const display = (response = fixture.response, expected = fixture.expected) => view({response, expected});
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!React.isValidElement(tree)) return [];
  return [tree, ...nodes(tree.props.children)];
}
function panels(tree) {return nodes(tree).filter(node => node.type === PanelSentinel);}
function dom(tree) {
  if (Array.isArray(tree)) return tree.map(dom).join(' ');
  if (typeof tree === 'string' || typeof tree === 'number') return String(tree);
  if (!React.isValidElement(tree) || typeof tree.type !== 'string') return '';
  const attributes = Object.entries(tree.props).filter(([key]) => key !== 'children').map(([, value]) => String(value));
  return attributes.join(' ') + ' ' + dom(tree.props.children);
}

test('real production wrapper/decoder/React create one panel element with unchanged detached preview', () => {
  const before = clone(fixture), tree = display();
  assert.ok(React.isValidElement(tree)); assert.equal(panels(tree).length, 1);
  assert.deepEqual(panels(tree)[0].props.charts, decoder.decodeTechnicalBoundary(fixture.response, fixture.expected).preview);
  assert.deepEqual(fixture, before);
  panels(tree)[0].props.charts.stock.stock_name = 'detached';
  assert.deepEqual(fixture, before);
});

test('DOM-targeted text/attributes explain synthetic cutoff and missing times, without private binding values', () => {
  const text = dom(display());
  for (const label of ['합성 차트 미리보기', '실제 KIS 조회', '요청 기준시점 적용 미검증',
    '엔진 생성 시각 미보고', '원천 공개 시각 미보고', '3개월', '빈 자료']) assert.ok(text.includes(label));
  const request = fixture.expected.request;
  for (const value of [request.request_id, request.trace_id, request.data.original_query,
    ...Object.values(request.data.context), fixture.expected.request_sha256, fixture.owner_user_id]) {
    assert.ok(!text.includes(value), 'Internal identity and raw question are not DOM content');
  }
});

test('zero, negative zero, null and annotations reach the actual panel element unchanged', () => {
  const packet = clone(fixture.response), chart = packet.data.result.charts[0].chart_data;
  chart.candles[0].open = -0; chart.annotations[0].price = -0;
  chart.annotations[0].meta = {zero: 0, negative: -0, nullable: null};
  const value = panels(display(packet))[0].props.charts.charts[0];
  assert.ok(Object.is(value.chart_data.candles[0].open, -0));
  assert.ok(Object.is(value.annotations[0].price, -0));
  assert.ok(Object.is(value.annotations[0].meta.negative, -0));
  assert.equal(value.annotations[0].meta.zero, 0); assert.equal(value.annotations[0].meta.nullable, null);
});

test('typed failure is an error state with no panel, never a successful empty chart', () => {
  const packet = clone(fixture.response); packet.data = null;
  packet.error = {code: 'BUSY', message: 'Technical boundary unavailable'};
  const tree = display(packet);
  assert.equal(panels(tree).length, 0); assert.equal(tree.props.role, 'alert');
  assert.ok(dom(tree).includes('제공할 수 없습니다')); assert.ok(!dom(tree).includes('표시할 차트 자료가 없습니다'));
});

for (const mutate of [
  p => {p.request_id = 'bad';}, p => {p.data.request_sha256 = 'f'.repeat(64);},
  p => {p.data.coverage.cutoff_validation = 'verified';},
  p => {p.data.result.charts[0].chart_data.candles[0].open = 'PRIVATE_RAW_SENTINEL';},
  p => {p.data = null; p.error = {code: 'BUSY', message: 'PRIVATE_RAW_SENTINEL'};},
]) test('invalid packet closes without panel or raw data', () => {
  const packet = clone(fixture.response); mutate(packet);
  const tree = display(packet);
  assert.equal(panels(tree).length, 0); assert.equal(tree.props.role, 'alert');
  assert.ok(dom(tree).includes('확인할 수 없습니다')); assert.ok(!dom(tree).includes('PRIVATE_RAW_SENTINEL'));
});

test('invalid or inconsistent independent expected closes safely', () => {
  for (const expected of [undefined, null, {}, {...clone(fixture.expected), request_sha256: 'a'.repeat(64)}]) {
    assert.equal(panels(view({response: fixture.response, expected})).length, 0);
  }
});

for (const mode of ['missing', 'empty']) test('valid all-' + mode + ' charts retain coverage and explicit empty state', () => {
  const packet = clone(fixture.response);
  if (mode === 'missing') delete packet.data.result.charts;
  else for (const item of packet.data.result.charts) item.chart_data.candles = [];
  packet.data.coverage.available_periods = [];
  for (const row of packet.data.coverage.periods) Object.assign(row, {
    start: null, end: null, count: 0, status: mode === 'missing' ? 'not_provided' : 'empty',
  });
  assert.equal(decoder.decodeTechnicalBoundary(packet, fixture.expected).kind, 'success');
  const tree = display(packet); assert.equal(panels(tree).length, 0);
  assert.ok(dom(tree).includes('표시할 차트 자료가 없습니다'));
  assert.ok(dom(tree).includes(mode === 'missing' ? '미제공' : '빈 자료'));
});

test('partial missing coverage is displayed while the complete validated preview reaches the panel', () => {
  const packet = clone(fixture.response); packet.data.result.charts.pop();
  packet.data.coverage.available_periods = ['3m'];
  Object.assign(packet.data.coverage.periods[2], {start: null, end: null, count: 0, status: 'not_provided'});
  const before = clone(packet), tree = display(packet);
  assert.equal(panels(tree).length, 1); assert.ok(dom(tree).includes('미제공'));
  assert.deepEqual(panels(tree)[0].props.charts, decoder.decodeTechnicalBoundary(packet, fixture.expected).preview);
  assert.deepEqual(packet, before);
});

test('mutating the same packet or expected reference revalidates on the next function call', () => {
  const packet = clone(fixture.response), expected = clone(fixture.expected);
  assert.equal(panels(display(packet, expected)).length, 1);
  packet.data.result.charts[0].chart_data.candles[0].open = 'bad';
  assert.equal(panels(display(packet, expected)).length, 0);
  const second = clone(fixture.response); assert.equal(panels(display(second, expected)).length, 1);
  expected.request.data.stock.stock_code = 'bad';
  assert.equal(panels(display(second, expected)).length, 0);
});

test('same binding clones keep the key; other valid supplied bindings change it without claiming a mount', () => {
  const key = panels(display())[0].key;
  assert.equal(panels(display(clone(fixture.response), clone(fixture.expected)))[0].key, key);
  const expected = clone(fixture.expected), packet = clone(fixture.response);
  const reportId = '10000000-0000-4000-8000-000000000006';
  expected.request.data.context.report_id = reportId; packet.data.request_snapshot.context.report_id = reportId;
  // This is independently supplied digest consistency, not a JS canonical hash.
  expected.request_sha256 = 'b'.repeat(64); packet.data.request_sha256 = expected.request_sha256;
  assert.equal(decoder.decodeTechnicalBoundary(packet, expected).kind, 'success');
  assert.notEqual(panels(display(packet, expected))[0].key, key);
  const tuple = JSON.parse(key);
  assert.equal(tuple.length, 8); assert.ok(!tuple.includes(fixture.expected.request.data.original_query));
});
