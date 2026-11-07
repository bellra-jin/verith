import { BackendApiError } from "./backend";

// flow payload(storage-spec v1) — 상세 화면이 JSON 에서 다시 그린다(HTML 저장 안 함).
export type FlowStrength = { ratio: number; strong: boolean };
export type FlowConsecutive = { days: number; signal: boolean };
export type FlowPersistence = { sum_5: number; sum_20: number; consistent: boolean };
export type FlowPriceRow = {
  date: string;
  close: number;
  change: number;
  change_rate: number;
  volume: number;
  frgn_qty: number | null;
  inst_qty: number | null;
};
export type FlowOwnershipRow = { date: string; ratio: number };
export type FlowGate = { gate?: number; passed: boolean; checks: string[]; failures: string[] };

export type FlowPayload = {
  version: number;
  report_id: string;
  trace_id: string | null;
  data_status: string | null;
  meta: { stock_name: string | null; ticker: string | null; market: string | null; base_date: string | null };
  signals: {
    alignment?: string;
    strength?: Record<string, FlowStrength>;
    consecutive?: Record<string, FlowConsecutive>;
    persistence?: Record<string, FlowPersistence>;
    inst_detail?: Record<string, number> | null;
    price_daily?: FlowPriceRow[] | null;
    ownership?: FlowOwnershipRow[] | null;
    daily?: Array<Record<string, number | string>> | null;
  } | null;
  verification: {
    gate1?: FlowGate | null;
    gate2?: FlowGate | null;
    gate3?: FlowGate | null;
    outcome?: string | null;
    regen_count?: number | null;
  } | null;
  interpretation: string | null;
  interpretation_meta: { source: string | null; provider: string | null; model: string | null } | null;
};

export type FlowReportEnvelope = { report_id: string; report: FlowPayload };

export async function getFlowReport(reportId: string): Promise<FlowReportEnvelope> {
  const response=await fetch(`/api/private/flow/reports/${encodeURIComponent(reportId)}`,{cache:"no-store"});
  if (!response.ok) throw new BackendApiError("결과를 불러올 수 없습니다.",response.status);
  return response.json();
}

export async function deleteFlowReport(reportId: string): Promise<void> {
  const session=await fetch("/api/auth/session",{cache:"no-store"});
  if (!session.ok) throw new Error("로그인이 필요합니다.");
  const {csrf_token}=await session.json();
  const response=await fetch(`/api/private/flow/reports/${reportId}`,{method:"DELETE",headers:{"X-CSRF-Token":csrf_token},cache:"no-store"});
  if (!response.ok) throw new Error("삭제할 수 없습니다.");
}

// DELETE /api/flow/reports → flow 리포트 전체 삭제. { deleted: N } 반환.
export async function deleteAllFlowReports(): Promise<{ deleted: number }> {
  throw new Error("전체 삭제는 사용할 수 없습니다.");
}
