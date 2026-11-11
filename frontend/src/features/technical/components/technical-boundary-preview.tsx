"use client";

import {decodeTechnicalBoundary, type TechnicalReadExpected} from '../lib/strict-boundary-read';
import {TechnicalChartPanel} from './technical-chart-panel';

const labels = {
  title: '합성 차트 미리보기',
  synthetic: '합성 자료입니다. 실제 KIS 조회나 모든 수치의 검증을 의미하지 않습니다.',
  invalid: '차트 결과를 확인할 수 없습니다.',
  unavailable: '차트 결과를 제공할 수 없습니다.',
  empty: '표시할 차트 자료가 없습니다.',
  cutoff: '요청 기준시점 적용 미검증',
  engine: '엔진 생성 시각 미보고',
  source: '원천 공개 시각 미보고',
  periods: {'3m': '3개월', '1y': '1년', '5y': '5년'},
  statuses: {available: '제공', empty: '빈 자료', not_provided: '미제공'},
} as const;

type ValidatedRequest = {
  request_id: string;
  trace_id: string;
  data: {context: {
    analysis_id: string;
    admission_request_id: string;
    attempt_id: string;
    input_fingerprint: string;
  }};
};
type CoveragePeriod = {
  period: keyof typeof labels.periods;
  status: keyof typeof labels.statuses;
};

/** Called only after the real decoder has checked these independent values.
 * Tuple encoding is a React identity, never a recalculated or authenticated hash.
 */
function bindingKey(reportId: string, expected: TechnicalReadExpected): string {
  const request = expected.request as ValidatedRequest;
  const context = request.data.context;
  return JSON.stringify([reportId, expected.request_sha256, request.request_id,
    request.trace_id, context.analysis_id, context.admission_request_id,
    context.attempt_id, context.input_fingerprint]);
}

type DisplayRead = {kind: 'invalid'} | {kind: 'error'} | {
  kind: 'success';
  value: Extract<ReturnType<typeof decodeTechnicalBoundary>, {kind: 'success'}>;
  key: string;
};

function readDisplay(response: unknown, expected: TechnicalReadExpected): DisplayRead {
  try {
    const value = decodeTechnicalBoundary(response, expected);
    return value.kind === 'error' ? {kind: 'error'}
      : {kind: 'success', value, key: bindingKey(value.preview.report_id, expected)};
  } catch {
    return {kind: 'invalid'};
  }
}

/** Pure display composition: no fetch, storage, execution or authentication.
 * Every render revalidates mutable unknown inputs. A key changes only with the
 * validated binding; actual child mounting/reconciliation is the caller's UI.
 */
export function TechnicalBoundaryPreview({response, expected}: {
  readonly response: unknown;
  readonly expected: TechnicalReadExpected;
}) {
  const read = readDisplay(response, expected);
  if (read.kind === 'invalid') {
    return <section role="alert" className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-700">
      <p>{labels.invalid}</p>
    </section>;
  }
  if (read.kind === 'error') {
    return <section role="alert" className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-700">
      <p>{labels.unavailable}</p>
    </section>;
  }
  const {value: decoded, key} = read;

  // The decoder validated this exact coverage shape; do not infer missing times
  // or derive an actual data cutoff from the requested or observed timestamp.
  const periods = decoded.coverage.periods as CoveragePeriod[];
  const hasCharts = decoded.preview.available_periods.length > 0;
  return <section aria-label={labels.title} className="space-y-4">
    <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-700">
      <h2 className="text-base font-semibold text-slate-900">{labels.title}</h2>
      <p className="mt-2">{labels.synthetic}</p>
      <ul className="mt-3 space-y-1">
        <li>{labels.cutoff}</li>
        <li>{labels.engine}</li>
        <li>{labels.source}</li>
      </ul>
      <ul aria-label="기간별 자료 제공 상태" className="mt-3 flex flex-wrap gap-3">
        {periods.map(period => <li key={period.period}>
          {labels.periods[period.period]}: {labels.statuses[period.status]}
        </li>)}
      </ul>
    </div>
    {hasCharts
      ? <TechnicalChartPanel key={key} charts={decoded.preview} />
      : <p role="status" className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">{labels.empty}</p>}
  </section>;
}
