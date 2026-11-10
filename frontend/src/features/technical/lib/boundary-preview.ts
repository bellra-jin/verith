import type {TechnicalChartsReadModel} from '../model/types';

const periods = ['3m', '1y', '5y'] as const;
const invalid = () => new Error('Invalid synthetic Technical preview');

function assertJson(value: unknown, ancestors = new Set<object>()): void {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return;
  if (typeof value === 'number' && Number.isFinite(value)) return;
  if (typeof value !== 'object' || ancestors.has(value)) throw invalid();
  ancestors.add(value);
  if (Array.isArray(value)) {
    for (const item of value) assertJson(item, ancestors);
  } else {
    if (Object.getPrototypeOf(value) !== Object.prototype) throw invalid();
    for (const item of Object.values(value)) assertJson(item, ancestors);
  }
  ancestors.delete(value);
}

function canonical(value: unknown): string {
  return JSON.stringify(value, (_key, item) => {
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]));
    }
    return item;
  });
}

/** Pure projection of an already Backend-validated, non-persistent boundary preview.
 * No fetch, signal calculation, identity generation, storage or public execution.
 */
export function boundaryPreview(value: TechnicalChartsReadModel): TechnicalChartsReadModel {
  assertJson(value);
  if (!value || typeof value.report_id !== 'string' || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value.report_id)
      || !value.stock || typeof value.stock.stock_code !== 'string' || !/^[0-9]{6}$/.test(value.stock.stock_code)
      || !(value.stock.stock_name === null || typeof value.stock.stock_name === 'string')
      || !(value.stock.market === null || typeof value.stock.market === 'string')
      || !Array.isArray(value.charts) || !Array.isArray(value.available_periods)) throw invalid();
  const seen = new Set<string>();
  for (const chart of value.charts) {
    const index = periods.findIndex(period => period === chart.period);
    const data = chart.chart_data;
    if (index < 0 || seen.has(chart.period) || chart.display_order !== index || !data
        || data.candle_unit === '1min' || data.candle_unit !== (chart.period === '5y' ? 'W' : 'D')
        || chart.candle_unit !== data.candle_unit || !Array.isArray(data.candles)
        || !Array.isArray(data.annotations) || !Array.isArray(chart.annotations)
        || chart.annotation_count !== data.annotations.length
        || chart.has_chart_data !== (data.candles.length > 0)
        || canonical(chart.annotations) !== canonical(data.annotations)) throw invalid();
    seen.add(chart.period);
  }
  const available = periods.filter(period => value.charts.some(chart => chart.period === period && chart.has_chart_data));
  if (canonical(value.available_periods) !== canonical(available)) throw invalid();
  // structuredClone preserves null, zero and the supplied numeric values without coercion.
  return structuredClone(value);
}
