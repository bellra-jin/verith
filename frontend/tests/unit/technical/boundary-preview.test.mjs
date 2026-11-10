import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const fixture = JSON.parse(fs.readFileSync('tests/fixtures/cf021-technical-boundary.json','utf8'));
function load(file) {
  const m = {exports:{}};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{
    compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},
  }).outputText,{module:m,exports:m.exports,structuredClone,Object,require(){throw Error('Closed pure registry');}},{timeout:100});
  return m.exports;
}
const preview = load('src/features/technical/lib/boundary-preview.ts').boundaryPreview;
const chart = load('src/features/technical/lib/chart.ts');
const clone = value => structuredClone(value);

test('shared synthetic boundary preview is a detached lossless existing chart props projection',()=>{
  assert.equal(fixture.synthetic,true);
  const before = JSON.stringify(fixture);
  const result = preview(fixture.expected_preview);
  assert.deepEqual(result,fixture.expected_preview);
  assert.notEqual(result,fixture.expected_preview);
  assert.equal(result.report_id,fixture.request.data.context.report_id);
  assert.deepEqual(result.stock,fixture.request.data.stock);
  for (const entry of result.charts) {
    const raw = fixture.result.charts.find(item => item.period === entry.period);
    assert.deepEqual(entry.chart_data,raw.chart_data);
    assert.deepEqual(entry.annotations,raw.chart_data.annotations);
  }
  result.stock.stock_name = 'detached synthetic edit';
  assert.equal(JSON.stringify(fixture),before);
});

test('actual existing date/price/level/RSI helpers consume the boundary props and retain zero/null',()=>{
  const result = preview(fixture.expected_preview);
  for (const entry of result.charts) {
    const annotations = entry.chart_data.annotations;
    if (!entry.has_chart_data) {assert.equal(annotations.length,0);assert.deepEqual(chart.computeHighLow(entry.chart_data.candles),null);continue;}
    const prices = chart.getPriceChartAnnotations(annotations);
    assert.deepEqual(Array.from(prices.filter(x=>x.marker==='price'),x=>x.y),fixture.expected_markers.price);
    assert.deepEqual(Array.from(prices.filter(x=>x.marker==='level'),x=>x.y),fixture.expected_markers.level);
    assert.deepEqual(Array.from(chart.getRsiAnnotations(annotations),x=>x.rsi),fixture.expected_markers.rsi);
    assert.equal(annotations.find(x=>x.kind==='rsi_oversold').price,null);
    const candle = entry.chart_data.candles[0];
    assert.equal(chart.candleDate(candle),candle.date);
    assert.equal(candle.volume,0);
    assert.equal(entry.chart_data.overlays.moving_average[0].points[0].value,0);
  }
  assert.equal(chart.formatChartDate('2026-11-06','3m'),'11/06');
  assert.equal(chart.formatChartDate('2026-11-02','5y'),'26.11');
});

for (const mutation of [
  value=>{value.charts[0].period='1d';},
  value=>{value.charts[0].chart_data.candle_unit='W';},
  value=>{value.charts.push(clone(value.charts[0]));},
  value=>{value.charts[0].display_order=2;},
  value=>{value.available_periods=[];},
  value=>{value.charts[0].has_chart_data=false;},
  value=>{value.charts[0].annotation_count=0;},
  value=>{value.charts[0].annotations=[];},
  value=>{value.charts[0].chart_data.candles[0].close=Infinity;},
  value=>{value.charts[0].chart_data.annotations[0].meta={bad:NaN};},
  value=>{value.charts[0].chart_data.annotations[0].meta={bad:undefined};},
  value=>{value.stock.stock_code=5930;},
]) test('pure boundary preview rejects policy/unit/coverage/non-JSON mutation '+mutation.toString(),()=>{
  const value = clone(fixture.expected_preview);mutation(value);
  assert.throws(()=>preview(value),/Invalid synthetic Technical preview/);
});

test('missing and empty charts stay explicit without inventing coverage or prices',()=>{
  const value = clone(fixture.expected_preview);
  value.charts = value.charts.slice(0,1);
  const entry = value.charts[0];
  entry.chart_data.candles=[];entry.has_chart_data=false;
  value.available_periods=[];
  const result = preview(value);
  assert.deepEqual(result.available_periods,[]);
  assert.deepEqual(result.charts[0].chart_data.candles,[]);
  assert.deepEqual(chart.computeHighLow(result.charts[0].chart_data.candles),null);
  const empty = {...value,charts:[]};assert.deepEqual(preview(empty).charts,[]);
});
