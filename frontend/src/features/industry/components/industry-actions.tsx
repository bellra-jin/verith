"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, Download, Trash2 } from "lucide-react";

import { deleteIndustryReport } from "@/features/industry/api/reports";

// industry 상세 상단 액션바 — 목록 복귀 · PDF 다운로드 · 삭제.
// React 렌더라서 window.print() 로 바로 인쇄/PDF 저장이 된다(flow·technical 과 동일).
export function IndustryActions({ reportId }: { reportId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [isPending, startTransition] = useTransition();

  const onPdf = () => window.print();

  const onDelete = async () => {
    if (busy) return;
    if (!window.confirm("이 리포트를 삭제할까요? 되돌릴 수 없습니다.")) return;
    setBusy(true);
    try {
      await deleteIndustryReport(reportId);
      startTransition(() => router.push("/?agent_type=industry"));
    } catch {
      window.alert("삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      setBusy(false);
    }
  };

  const disabled = busy || isPending;
  return (
    <div className="report-actions mb-5 flex items-center justify-between print:hidden">
      <Link
        href="/?agent_type=industry"
        className="flex items-center gap-1.5 text-[13px] font-bold text-[var(--brand)] transition-colors hover:text-[var(--brand-hover)]"
      >
        <ChevronLeft className="h-4 w-4" /> 리포트 목록으로 돌아가기
      </Link>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onDelete}
          disabled={disabled}
          className="flex items-center gap-1.5 rounded-xl border border-rose-100 bg-rose-50/60 px-3.5 py-2.5 text-[13px] font-bold text-rose-600 transition-colors hover:bg-rose-100 disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" />
          <span>{disabled ? "삭제 중…" : "삭제"}</span>
        </button>
        <button
          type="button"
          onClick={onPdf}
          title="브라우저 인쇄 창에서 PDF 로 저장할 수 있습니다."
          className="flex items-center gap-1.5 rounded-xl bg-[var(--brand)] px-3.5 py-2.5 text-[13px] font-bold text-white shadow-none transition-colors hover:bg-[var(--brand-hover)]"
        >
          <Download className="h-4 w-4" />
          <span>PDF 다운로드</span>
        </button>
      </div>
    </div>
  );
}
