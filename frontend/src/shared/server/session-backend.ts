import "server-only";
import { headers } from "next/headers";

// Explicit server-only address; never use a browser-controlled target or public fallback.
export function sessionBackendUrl(): string | null {
  const value = process.env.BACKEND_URL;
  if (!value) return null;
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) return null;
  return url.origin;
}

export async function sessionBackendFetch(path: string): Promise<Response | null> {
  const base = sessionBackendUrl();
  if (!base) return null;
  // RequestCookies collapses duplicate names. Preserve the raw header so the
  // Backend applies the same ambiguity rejection as direct API and BFF requests.
  const incoming = await headers();
  if (base === 'http://localhost:8200' &&
      (incoming.get('host') !== 'localhost:3200' ||
       incoming.get('x-forwarded-host') !== null && incoming.get('x-forwarded-host') !== 'localhost:3200' ||
       incoming.get('origin') !== null && incoming.get('origin') !== 'http://localhost:3200')) return null;
  const cookieHeader = incoming.get('cookie');
  return fetch(base + path, {headers: cookieHeader ? {Cookie: cookieHeader} : {}, cache: 'no-store', redirect: 'manual'});
}
