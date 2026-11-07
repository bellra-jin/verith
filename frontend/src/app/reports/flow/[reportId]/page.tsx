export const dynamic = "force-dynamic";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import type { FlowReportEnvelope } from "@/api/flow";
import {archiveHref, archivePagination, type ArchiveSearchParams} from "@/lib/archive-pagination";
import {sessionBackendFetch} from "@/lib/session-backend";
import {SessionControls} from "@/features/flow/components/session-controls";
import { FlowReportView } from "@/features/flow/components/flow-report-view";

export default async function FlowReportPage({
  params, searchParams,
}: {
  params: Promise<{ reportId: string }>;
  searchParams: Promise<ArchiveSearchParams>;
}) {
  const { reportId } = await params;
  const returnTo = archiveHref(archivePagination(await searchParams));
  if (!/^[0-9a-fA-F-]{36}$/.test(reportId)) notFound();
  const auth=await sessionBackendFetch('/api/auth/session');
  if (!auth?.ok) redirect('/');
  const session=await auth.json() as {csrf_token:string};
  const response=await sessionBackendFetch(`/api/flow/reports/${reportId}`);
  if (response?.status===404) notFound();
  if (!response?.ok) redirect('/');
  const envelope=await response.json() as FlowReportEnvelope;

  // 배경·카드 구성은 flow 목업(flow_sample) 디자인 언어: #F2F4F6 위에 흰 카드들.
  return (
    <div className="min-h-screen bg-[#F2F4F6] px-4 py-8 font-sans antialiased sm:px-6 lg:px-8">
      <article className="mx-auto w-full max-w-[1200px]">
        {/* Top Brand Bar */}
        <div className="mb-5 flex h-[60px] items-center justify-between rounded-2xl border border-[#e2e8f0] bg-white px-6 shadow-sm print:hidden">
          <Link href="/" className="flex items-center gap-2">
            <div className="grid h-[30px] w-[30px] place-items-center rounded-lg bg-[#4f46e5] text-[17px] font-bold leading-none text-white">
              θ
            </div>
            <span className="text-[18px] font-bold tracking-tight text-[#0f172a]">
              veri<span className="text-[#4f46e5]">θ</span>
            </span>
            <span className="ml-1 rounded border border-[#e2e8f0] px-1.5 py-0.5 text-[9px] font-bold leading-none text-[#94a3b8]">
              BETA
            </span>
          </Link>
          <span className="text-xs font-bold uppercase tracking-wider text-[#94a3b8]">수급·자금흐름 리포트</span>
        </div>

        <SessionControls csrfToken={session.csrf_token} reportId={reportId} returnTo={returnTo} />
        <FlowReportView payload={envelope.report} />
      </article>
    </div>
  );
}
