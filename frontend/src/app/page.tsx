import { fundamentalAnalysisEnabled } from '@/shared/server/fundamental-analysis-config';
import Link from "next/link";
import { flowAnalysisEnabled } from "@/shared/server/flow-analysis-config";
import { flowDemoEnabled } from "@/shared/server/flow-demo-config";
import { redirect } from "next/navigation";
import { AppShell } from "@/shared/ui/app-shell";
import { sessionBackendFetch } from "@/shared/server/session-backend";
import { SessionControls } from "@/features/flow/components/session-controls";
import { archiveHref, archivePagination, lastArchiveOffset, type ArchiveSearchParams } from "@/features/archive/lib/pagination";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams: Promise<ArchiveSearchParams> }) {
  const page = archivePagination(await searchParams);
  const fundamentalLink=fundamentalAnalysisEnabled() && <Link href="/fundamental">재무 분석·본인 결과</Link>;
  const analysisLink=flowAnalysisEnabled() && <Link href="/research">Flow 분석 요청</Link>;
  const demoLink=flowDemoEnabled() && <Link href="/flow/demo">합성 데모</Link>;
  let sessionResponse: Response | null = null;
  try { sessionResponse = await sessionBackendFetch("/api/auth/session"); } catch { /* safe closed screen */ }
  if (!sessionResponse?.ok) return <AppShell title="Flow 보관함" subtitle="Google 로그인 후 본인 결과를 확인하세요.">{fundamentalLink}{analysisLink}{demoLink}<Link href="/api/auth/login">Google로 로그인</Link><p>실제 로그인 설정과 검증은 준비 중입니다. 새 분석·저장·전체 삭제는 사용할 수 없습니다.</p></AppShell>;
  const session = await sessionResponse.json() as { csrf_token: string };
  const response = await sessionBackendFetch(`/api/reports/archive?agent_type=flow&limit=${page.limit}&offset=${page.offset}`);
  if (!response?.ok) return <AppShell title="Flow 보관함" subtitle="결과를 불러올 수 없습니다.">{fundamentalLink}{analysisLink}{demoLink}<SessionControls csrfToken={session.csrf_token} /></AppShell>;
  const archive = await response.json() as { total: number; items: Array<{ report_id: string; stock: { stock_name: string | null }; card: { title: string } }> };
  // A deletion can empty the last page. Return to the last remaining page (or zero).
  if (page.offset > 0 && page.offset >= archive.total) redirect(archiveHref({ ...page, offset: lastArchiveOffset(archive.total, page.limit) }));
  const returnQuery = archiveHref(page).slice(1);
  return <AppShell title="내 Flow 보관함" subtitle={`${archive.total}개 결과`}>
    {fundamentalLink}{analysisLink}{demoLink}
    <SessionControls csrfToken={session.csrf_token} />
    <ul>{archive.items.map(item => <li key={item.report_id}><Link href={`/reports/flow/${item.report_id}${returnQuery}`}>{item.stock.stock_name} · {item.card.title}</Link></li>)}</ul>
    {!archive.items.length && <p>저장된 본인 결과가 없습니다.</p>}
    <nav aria-label="리포트 페이지">
      {page.offset > 0 && <Link href={archiveHref({ ...page, offset: Math.max(0, page.offset - page.limit) })}>이전 페이지</Link>}
      {page.offset + page.limit < archive.total && <Link href={archiveHref({ ...page, offset: page.offset + page.limit })}>다음 페이지</Link>}
    </nav>
  </AppShell>;
}
