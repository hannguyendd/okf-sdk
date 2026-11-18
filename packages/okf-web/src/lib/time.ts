/** Friendly dates for frontmatter timestamps (ISO 8601 strings from the server). */

const parse = (ts: unknown): Date | null => {
  if (typeof ts !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(ts)) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
};

const full = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });
const rel = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60], ["month", 30 * 24 * 60], ["week", 7 * 24 * 60], ["day", 24 * 60], ["hour", 60], ["minute", 1],
];

/** "just now", "5 minutes ago", "yesterday", "3 weeks ago"; "" if not a date. */
export function ago(ts: unknown, now = Date.now()): string {
  const d = parse(ts);
  if (!d) return "";
  const mins = (d.getTime() - now) / 60000;
  if (Math.abs(mins) < 1) return "just now";
  const [unit, size] = UNITS.find(([, s]) => Math.abs(mins) >= s)!;
  return rel.format(Math.round(mins / size), unit);
}

/** "Nov 13, 2026, 12:47 PM" in the viewer's time zone; null if not a date. */
export function formatDate(ts: unknown): string | null {
  const d = parse(ts);
  return d ? full.format(d) : null;
}
