export type ArchiveSearchParams = Record<string, string | string[] | undefined>;
export type ArchivePagination = { limit: number; offset: number };

function integer(value: string | string[] | undefined, fallback: number, min: number, max: number): number {
  if (typeof value !== "string" || !/^\d+$/.test(value)) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= min && parsed <= max ? parsed : fallback;
}

export function archivePagination(params: ArchiveSearchParams): ArchivePagination {
  return {
    limit: integer(params.limit, 20, 1, 100),
    // Keep page arithmetic exact and stay within PostgreSQL's bigint offset range.
    offset: integer(params.offset, 0, 0, Number.MAX_SAFE_INTEGER - 100),
  };
}

export function archiveHref({ limit, offset }: ArchivePagination): string {
  return `/?limit=${limit}&offset=${offset}`;
}

export function lastArchiveOffset(total: number, limit: number): number {
  return total > 0 ? Math.floor((total - 1) / limit) * limit : 0;
}
