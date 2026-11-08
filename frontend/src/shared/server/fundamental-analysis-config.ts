import 'server-only';
export function fundamentalAnalysisEnabled():boolean{return process.env.FUNDAMENTAL_ANALYSIS_ENABLED==='true';}
