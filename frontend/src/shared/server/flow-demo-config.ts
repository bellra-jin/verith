import 'server-only';
export function flowDemoEnabled(): boolean { return process.env.FLOW_SYNTHETIC_DEMO_ENABLED === 'true'; }
