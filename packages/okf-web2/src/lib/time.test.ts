import { ago, formatDate } from "./time";

const now = Date.parse("2026-11-13T12:00:00Z");

describe("ago", () => {
  it.each([
    ["2026-11-13T11:59:40Z", "just now"],
    ["2026-11-13T11:55:00Z", "5 minutes ago"],
    ["2026-11-13T09:00:00Z", "3 hours ago"],
    ["2026-11-12T12:00:00Z", "yesterday"],
    ["2026-10-30T12:00:00Z", "2 weeks ago"],
    ["2025-11-13T12:00:00Z", "last year"],
  ])("%s → %s", (ts, out) => expect(ago(ts, now)).toBe(out));

  it("ignores things that are not dates", () => {
    expect(ago("Platform team", now)).toBe("");
    expect(ago(null, now)).toBe("");
  });
});

describe("formatDate", () => {
  it("formats ISO timestamps and leaves other values alone", () => {
    expect(formatDate("2026-11-13T05:47:04Z")).toMatch(/^Nov 1[23], 2026, \d{1,2}:\d{2}\s?[AP]M$/);
    expect(formatDate("2026 plans")).toBeNull();
    expect(formatDate(42)).toBeNull();
  });
});
