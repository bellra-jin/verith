// Read-only display evidence, never payload mutation or market coverage.
export const SUBJECTS = ["개인", "외국인", "기관"] as const;
export type Subject = (typeof SUBJECTS)[number];
export type Relation = "unknown" | "buy" | "sell" | "opposite" | "neutral";
export type DailyDisplayRow = { date: string } & Record<Subject, number>;
export type ObservationWindow = {
  status: "unknown" | "insufficient" | "sufficient_rows";
  shownRows: number | null;
  shortCount: number | null;
  longCount: number | null;
  notice: string;
  shortLabel: string;
  longLabel: string;
  dailyLabel: string;
  interpretationNotice: string;
  relations: Record<Subject, Relation>;
};
export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
export function finiteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
export function isoDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.slice(0, 4) === "0000") return false;
  const parsed = new Date(value + "T00:00:00.000Z");
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
export function safeDaily(signals: unknown): DailyDisplayRow[] | null {
  const daily = record(signals) ? signals.daily : null;
  if (!Array.isArray(daily) || !daily.length || daily.length > 20) return null;
  const rows: DailyDisplayRow[] = [];
  for (const row of daily) {
    if (!record(row) || !isoDate(row.date)) return null;
    const p = row["개인"], f = row["외국인"], i = row["기관"];
    if (!finiteNumber(p) || !finiteNumber(f) || !finiteNumber(i)) return null;
    if (rows.length && rows[rows.length - 1].date >= row.date) return null;
    rows.push({ date: row.date, 개인: p, 외국인: f, 기관: i });
  }
  return rows;
}
export type PersistenceCell = { short: number | null; long: number | null; consistent: boolean | null };
function persistenceCell(value: unknown): PersistenceCell {
  const claim: Record<string, unknown> = record(value) ? value : {};
  return { short: finiteNumber(claim.sum_5) ? claim.sum_5 : null,
    long: finiteNumber(claim.sum_20) ? claim.sum_20 : null,
    consistent: typeof claim.consistent === "boolean" ? claim.consistent : null };
}
export function persistenceCells(signals: unknown): Record<Subject, PersistenceCell> {
  const source: Record<string, unknown> = record(signals) && record(signals.persistence) ? signals.persistence : {};
  return { 개인: persistenceCell(source["개인"]), 외국인: persistenceCell(source["외국인"]), 기관: persistenceCell(source["기관"]) };
}
function sign(value: number): number { return value > 0 ? 1 : value < 0 ? -1 : 0; }
function relation(short: number, long: number): Relation {
  if (short === 0 || long === 0) return "neutral";
  if (sign(short) !== sign(long)) return "opposite";
  return short > 0 ? "buy" : "sell";
}
export function relationText(value: Relation): string {
  switch (value) {
    case "buy": return "단기·장기 모두 순매수";
    case "sell": return "단기·장기 모두 순매도";
    case "opposite": return "단기·장기 방향 차이";
    case "neutral": return "합 0 포함 · 판단 보류";
    default: return "지속성 비교 보류";
  }
}
export function observationWindow(signals: unknown, recentDays: number, trendDays: number): ObservationWindow {
  const raw = record(signals) ? signals.daily : null;
  const shown = Array.isArray(raw) ? raw.length : null;
  const rows = safeDaily(signals);
  const result: ObservationWindow = {
    status: "unknown", shownRows: shown, shortCount: null, longCount: null,
    notice: "계산창 관측기간 미확인 · 지속성 비교 보류",
    shortLabel: "단기 합 (기간 미확인)", longLabel: "장기 합 (기간 미확인)",
    dailyLabel: rows !== null ? `표시 ${shown}행 · 계산창 관측기간 미확인`
      : shown !== null ? `제공된 일별자료 ${shown}행 · 표시 미확인` : "제공된 일별자료 · 표시 미확인",
    interpretationNotice: "저장 당시 해석 · 관측기간 미확인, 아래 원문의 기간 주장은 현재 보증되지 않음",
    relations: { 개인: "unknown", 외국인: "unknown", 기관: "unknown" },
  };
  if (!Number.isInteger(recentDays) || !Number.isInteger(trendDays) || recentDays < 1 || recentDays > trendDays || trendDays > 20
      || rows === null || rows.length < 1 || rows.length > trendDays || !record(signals)) return result;
  if (rows.some((row, index) => index > 0 && rows[index - 1].date >= row.date)) return result;
  const persistence = signals.persistence;
  if (!record(persistence)) return result;
  const relations: Record<Subject, Relation> = { 개인: "unknown", 외국인: "unknown", 기관: "unknown" };
  for (const subject of SUBJECTS) {
    const claim = persistence[subject];
    if (!record(claim) || typeof claim.consistent !== "boolean" || !finiteNumber(claim.sum_5) || !finiteNumber(claim.sum_20)) return result;
    const short = claim.sum_5, long = claim.sum_20;
    const derivedShort = rows.slice(-recentDays).reduce((sum, row) => sum + row[subject], 0);
    const derivedLong = rows.slice(-trendDays).reduce((sum, row) => sum + row[subject], 0);
    if (!finiteNumber(derivedShort) || !finiteNumber(derivedLong)) return result;
    const close = (a: number, b: number) => Math.abs(a - b) <= Math.max(1e-9 * Math.max(Math.abs(a), Math.abs(b)), 1e-6) && sign(a) === sign(b);
    if (!close(short, derivedShort) || !close(long, derivedLong)) return result;
    const consistent = sign(derivedShort) === sign(derivedLong) && sign(derivedLong) !== 0;
    const storedConsistent = sign(short) === sign(long) && sign(long) !== 0;
    if (claim.consistent !== consistent || claim.consistent !== storedConsistent) return result;
    relations[subject] = relation(short, long);
  }
  const count = rows.length, shortCount = Math.min(count, recentDays), sufficient = count === trendDays;
  result.status = sufficient ? "sufficient_rows" : "insufficient";
  result.shortCount = shortCount; result.longCount = count;
  result.shortLabel = `단기 제공 ${shortCount}개`; result.longLabel = `장기 제공 ${count}개`;
  result.dailyLabel = `제공된 일별자료 ${count}행`;
  if (sufficient) {
    result.notice = `제공 자료 기준 단기 ${shortCount}개·장기 ${count}개 관측 비교`;
    result.interpretationNotice = "저장 당시 해석 · 제공 자료 행수 정합만 확인했으며 거래일 완비·원천 계산창을 보증하지 않음";
    result.relations = relations;
  } else {
    result.notice = count < recentDays ? `제공 관측 ${count}개 · ${recentDays}/${trendDays}개 기준 자료 부족 · 지속성 비교 보류`
      : `제공 자료 기준 단기 ${shortCount}개·장기 ${count}개 관측 · 장기 관측 부족 · 지속성 비교 보류`;
    result.interpretationNotice = "저장 당시 해석 · 관측기간 부족, 아래 원문의 기간 주장은 현재 보증되지 않음";
  }
  return result;
}
