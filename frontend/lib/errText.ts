/** Human error text from an axios/unknown error.
 *
 * Prefers the backend's `detail` message; falls back to a readable line
 * instead of raw axios strings like "Request failed with status code 500"
 * or "timeout of 120000ms exceeded". Use this in EVERY error state.
 */
export function errText(err: unknown, fallback = "Something went wrong. Try again."): string {
  const e = err as {
    code?: string;
    message?: string;
    response?: { status?: number; data?: { detail?: unknown } };
  };
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (e?.code === "ECONNABORTED" || /timeout/i.test(e?.message ?? ""))
    return "The studio is taking longer than expected. It may still be working — check the activity feed, or try again.";
  if (e?.response?.status === 401) return "Session expired. Sign in again.";
  if (e?.response?.status === 404) return "Not found — it may have been deleted.";
  if (e?.response?.status && e.response.status >= 500)
    return "The studio hit an internal error. Try again in a moment.";
  if (!e?.response && e?.message && /network/i.test(e.message))
    return "Cannot reach the studio backend. Is it running?";
  return typeof e?.message === "string" && e.message ? fallback : fallback;
}
