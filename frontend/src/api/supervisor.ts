import type { SupervisorAnalyzeResponse } from "@/types/supervisor";

export type AnalyzeResult = { response: SupervisorAnalyzeResponse; live: boolean };

// No live calls or synthetic-success fallback may trigger follow-up report writes.
export async function analyzeQuery(query: string): Promise<AnalyzeResult> {
  void query;
  throw new Error("새 분석은 준비 중입니다.");
}
