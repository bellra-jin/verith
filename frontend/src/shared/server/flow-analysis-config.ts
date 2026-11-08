import 'server-only';

export function flowAnalysisEnabled(): boolean {
  return process.env.FLOW_ANALYSIS_ENABLED === 'true';
}
