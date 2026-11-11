import {boundaryPreview} from './boundary-preview';
import type {TechnicalChartsReadModel} from '../model/types';

type JsonObject = Record<string, unknown>;
export type TechnicalReadExpected = {request: unknown; request_sha256: string};
export type TechnicalReadResult =
  | {kind: 'success'; preview: TechnicalChartsReadModel; coverage: JsonObject; boundary_observed_at: string}
  | {kind: 'error'; error: {code: string; message: 'Technical boundary unavailable'}};
const periods = ['3m', '1y', '5y'];
const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;
const sha = /^[0-9a-f]{64}$/;
const invalid = (): never => {throw new Error('Invalid Technical boundary read');};
function check(ok: unknown): asserts ok {if (!ok) invalid();}
function text(value: unknown): asserts value is string {
  check(typeof value === 'string');
  // JS strings must have a UTF-8 representation without replacement characters.
  for (const character of value) {
    const code = character.codePointAt(0)!;
    check(code < 0xd800 || code > 0xdfff);
  }
}
function json(value: unknown, ancestors = new Set<object>()): void {
  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'string') {text(value); return;}
  if (typeof value === 'number') {
    check(Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value))); return;
  }
  check(typeof value === 'object' && !ancestors.has(value));
  ancestors.add(value);
  const array = Array.isArray(value);
  check(Object.getPrototypeOf(value) === (array ? Array.prototype : Object.prototype));
  check(Object.getOwnPropertySymbols(value).length === 0);
  const descriptors = Object.getOwnPropertyDescriptors(value);
  if (array) check(Object.keys(descriptors).length === (value as unknown[]).length + 1);
  for (const [key, descriptor] of Object.entries(descriptors)) {
    if (array && key === 'length') continue;
    check(descriptor.enumerable && 'value' in descriptor);
    if (array) check(/^(0|[1-9][0-9]*)$/.test(key) && Number(key) < (value as unknown[]).length);
    text(key); json(descriptor.value, ancestors);
  }
  ancestors.delete(value);
}
function object(value: unknown, required: string[], optional: string[] = []): JsonObject {
  check(value !== null && typeof value === 'object' && !Array.isArray(value));
  const result = value as JsonObject;
  check(required.every(key => Object.hasOwn(result, key))
    && Object.keys(result).every(key => required.includes(key) || optional.includes(key)));
  return result;
}
function array(value: unknown): unknown[] {check(Array.isArray(value)); return value;}
function equal(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object'
      || Array.isArray(a) !== Array.isArray(b)) return false;
  const left = a as JsonObject, right = b as JsonObject;
  return Object.keys(left).length === Object.keys(right).length
    && Object.keys(left).every(key => Object.hasOwn(right, key) && equal(left[key], right[key]));
}
function member(value: unknown, values: readonly unknown[]): void {check(values.includes(value));}
function number(value: unknown, minimum = 0, maximum = Infinity): asserts value is number {
  check(typeof value === 'number' && Number.isFinite(value) && value >= minimum && value <= maximum
    && (!Number.isInteger(value) || Number.isSafeInteger(value)));
}
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): void {
  number(value, minimum, maximum); check(Number.isSafeInteger(value));
}
function date(value: unknown): asserts value is string {
  text(value); check(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value) && !value.startsWith('0000'));
  const parsed = new Date(value + 'T00:00:00Z');
  check(Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value);
}
function utc(value: unknown): asserts value is string {
  text(value);
  check(/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)$/.test(value));
  date(value.slice(0, 10));
  check(Number(value.slice(11, 13)) < 24 && Number(value.slice(14, 16)) < 60
    && Number(value.slice(17, 19)) < 60 && Number.isFinite(Date.parse(value)));
}
function id(value: unknown): void {text(value); check(uuid.test(value));}
function digest(value: unknown): void {text(value); check(sha.test(value));}
function stock(value: unknown): void {
  const v = object(value, ['stock_code', 'stock_name', 'market']);
  text(v.stock_code); check(/^[0-9]{6}$/.test(v.stock_code));
  text(v.stock_name); check([...v.stock_name].length <= 256 && v.stock_name.trim().length > 0
    && !/[\u0000-\u001f\u007f-\u009f]/.test(v.stock_name));
  member(v.market, ['KOSPI', 'KOSDAQ', 'KONEX', null]);
}
function requestData(value: unknown): JsonObject {
  const v = object(value, ['operation', 'context', 'original_query', 'stock', 'requested_views', 'requested_as_of'], ['conditions']);
  check(v.operation === 'technical.boundary.v1');
  const c = object(v.context, ['analysis_id', 'admission_request_id', 'attempt_id', 'report_id', 'input_fingerprint']);
  for (const key of ['analysis_id', 'admission_request_id', 'attempt_id', 'report_id']) id(c[key]);
  digest(c.input_fingerprint); text(v.original_query);
  check(v.original_query.trim().length > 0 && [...v.original_query].length <= 2000 && !v.original_query.includes('\0'));
  stock(v.stock); check(equal(v.requested_views, ['technical'])); utc(v.requested_as_of);
  if (Object.hasOwn(v, 'conditions')) {
    const conditions = object(v.conditions, [], ['profile', 'periods']);
    if (Object.hasOwn(conditions, 'profile')) check(conditions.profile === 'technical.multiframe.v1');
    if (Object.hasOwn(conditions, 'periods')) check(equal(conditions.periods, periods));
  }
  return v;
}
function envelope(value: unknown): JsonObject {
  const v = object(value, ['schema_version', 'request_id', 'trace_id', 'data', 'error']);
  check(v.schema_version === 'analysis.agent.v1'); id(v.request_id); id(v.trace_id);
  check((v.data === null) !== (v.error === null));
  return v;
}
function chart(value: unknown): JsonObject {
  const v = object(value, ['period', 'chart_data']); member(v.period, periods);
  const data = object(v.chart_data, ['candle_unit', 'candles', 'overlays', 'subcharts', 'annotations']);
  check(data.candle_unit === (v.period === '5y' ? 'W' : 'D'));
  const dates: string[] = [];
  for (const item of array(data.candles)) {
    const c = object(item, ['date', 'open', 'high', 'low', 'close', 'volume', 'trading_value']);
    date(c.date); dates.push(c.date);
    for (const key of ['open', 'high', 'low', 'close']) number(c[key]);
    number(c.high); number(c.low); check(c.high >= c.low);
    integer(c.volume); integer(c.trading_value);
  }
  check(dates.every((value, index) => index === 0 || dates[index - 1] < value));
  const overlays = object(data.overlays, ['moving_average', 'support_resistance']);
  for (const item of array(overlays.moving_average)) {
    const ma = object(item, ['window', 'points']); integer(ma.window, 1);
    for (const item of array(ma.points)) {const p = object(item, ['date', 'value']); date(p.date); number(p.value);}
  }
  for (const item of array(overlays.support_resistance)) {
    const sr = object(item, ['type', 'price', 'from', 'to', 'touch_count']);
    member(sr.type, ['support', 'resistance']); number(sr.price); date(sr.from); date(sr.to); integer(sr.touch_count);
  }
  const subs = object(data.subcharts, ['rsi', 'volume']);
  const rsi = object(subs.rsi, ['period', 'overbought', 'oversold', 'points']);
  integer(rsi.period, 1); integer(rsi.overbought, 0, 100); integer(rsi.oversold, 0, 100);
  number(rsi.oversold); number(rsi.overbought); check(rsi.oversold < rsi.overbought);
  for (const item of array(rsi.points)) {const p = object(item, ['date', 'value']); date(p.date); number(p.value, 0, 100);}
  const volume = object(subs.volume, ['avg_window', 'bars']); integer(volume.avg_window, 1);
  for (const item of array(volume.bars)) {
    const bar = object(item, ['date', 'volume', 'is_spike'], ['avg_volume']);
    date(bar.date); integer(bar.volume); check(typeof bar.is_spike === 'boolean');
    if (Object.hasOwn(bar, 'avg_volume') && bar.avg_volume !== null) number(bar.avg_volume);
  }
  for (const item of array(data.annotations)) {
    const a = object(item, ['id', 'kind', 'date', 'label', 'importance', 'source'], ['price', 'meta']);
    text(a.id); text(a.label); date(a.date);
    member(a.kind, ['golden_cross', 'dead_cross', 'volume_spike', 'support_touch', 'resistance_touch',
      'rsi_overbought', 'rsi_oversold', 'box_range_candidate', 'box_breakout_candidate', 'cup_handle_candidate']);
    member(a.importance, ['low', 'medium', 'high']); check(a.source === 'code');
    if (Object.hasOwn(a, 'price') && a.price !== null) number(a.price);
    if (Object.hasOwn(a, 'meta')) check(a.meta !== null && typeof a.meta === 'object' && !Array.isArray(a.meta));
  }
  return v;
}

/** Pure decoder for a CF021 envelope and chart projection, not the opaque
 * non-chart TechnicalAgentOutput internals. Supplied digests are only compared
 * with independent expectations; no Python canonical hash is computed in JS.
 * Parsed unknown values cannot reveal duplicate JSON keys or lost precision.
 */
export function decodeTechnicalBoundary(value: unknown, expected: TechnicalReadExpected): TechnicalReadResult {
  json(value); json(expected);
  const expectation = object(expected, ['request', 'request_sha256']); digest(expectation.request_sha256);
  const request = envelope(expectation.request); check(request.error === null);
  const input = requestData(request.data), context = input.context as JsonObject;
  const ids = [request.request_id, request.trace_id, context.analysis_id, context.admission_request_id, context.attempt_id, context.report_id];
  check(new Set(ids).size === ids.length);
  const response = envelope(value);
  check(response.request_id === request.request_id && response.trace_id === request.trace_id);
  if (response.error !== null) {
    const e = object(response.error, ['code'], ['message']);
    member(e.code, ['FEATURE_UNAVAILABLE', 'AUTH_REQUIRED', 'INPUT_INVALID', 'SERVICE_UNAVAILABLE',
      'DEADLINE_EXCEEDED', 'RESULT_CONTRACT_INVALID', 'BUSY']);
    if (Object.hasOwn(e, 'message')) check(e.message === 'Technical boundary unavailable');
    return {kind: 'error', error: {code: e.code as string, message: 'Technical boundary unavailable'}};
  }
  const data = object(response.data, ['request_snapshot', 'request_sha256', 'result', 'coverage', 'execution_mode', 'boundary_observed_at']);
  requestData(data.request_snapshot); check(equal(data.request_snapshot, input)); digest(data.request_sha256);
  check(data.request_sha256 === expectation.request_sha256 && data.execution_mode === 'synthetic'); utc(data.boundary_observed_at);
  const result = object(data.result, ['request_id', 'ticker', 'as_of', 'source', 'trace_id', 'data_status', 'regime', 'interpretation', 'verification'],
    ['signal', 'technical_signals', 'risk', 'charts', 'intraday_context', 'resolved_stock_name']);
  check(result.request_id === request.request_id && result.trace_id === request.trace_id
    && result.ticker === (input.stock as JsonObject).stock_code && result.as_of === input.requested_as_of);
  member(result.source, ['KIS', 'KIS (stale)']);
  member(result.data_status, ['normal', 'stale_cache', 'data_limited', 'regime_unavailable']);
  const charts = Object.hasOwn(result, 'charts') ? array(result.charts).map(chart) : [];
  check(new Set(charts.map(c => c.period)).size === charts.length);
  const rows = periods.map(period => {
    const entry = charts.find(c => c.period === period), cd = entry?.chart_data as JsonObject | undefined;
    const candles = cd ? cd.candles as JsonObject[] : [];
    return {period, candle_unit: period === '5y' ? 'W' : 'D', start: candles[0]?.date ?? null,
      end: candles.at(-1)?.date ?? null, count: candles.length,
      status: candles.length ? 'available' : cd ? 'empty' : 'not_provided'};
  });
  const available = rows.filter(row => row.count > 0).map(row => row.period);
  const coverage = object(data.coverage, ['requested_periods', 'available_periods', 'periods', 'cutoff_validation', 'engine_generated_at', 'source_published_at', 'unreported_reason']);
  check(equal(coverage, {requested_periods: periods, available_periods: available, periods: rows,
    cutoff_validation: 'unverified', engine_generated_at: null, source_published_at: null, unreported_reason: 'engine_does_not_report'}));
  const preview = {report_id: context.report_id, stock: input.stock, available_periods: available,
    charts: charts.map(c => {
      const cd = c.chart_data as JsonObject;
      return {period: c.period, candle_unit: cd.candle_unit, display_order: periods.indexOf(c.period as string),
        has_chart_data: (cd.candles as unknown[]).length > 0, annotation_count: (cd.annotations as unknown[]).length,
        chart_data: cd, annotations: cd.annotations};
    })};
  // All numeric checks happen before boundaryPreview's JSON-based annotation
  // comparison. Both annotation views are derived from this one validated value.
  return {kind: 'success', preview: boundaryPreview(preview as TechnicalChartsReadModel),
    coverage: structuredClone(coverage), boundary_observed_at: data.boundary_observed_at};
}
