import {AppShell} from '@/shared/ui/app-shell';
import {OwnedReportView} from '@/features/technical/components/owned-report-view';
export const dynamic='force-dynamic';
export const revalidate=0;
export default function TechnicalOwnedListPage(){return <AppShell title="본인 저장 차트" subtitle="조회 전용 · 새 분석 실행 없음"><OwnedReportView/></AppShell>;}
