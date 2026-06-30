# okf-mcp — Timestamped Log Entries Design

**Date:** 2026-06-30
**Status:** Approved (brainstorming) — ready for implementation plan
**Depends on:** `okf-mcp` producer server (the `_log.md` machinery in `operations.py`)

## 1. Motivation

`okf-mcp` write tools (`add`, `patch`, `move`, `delete`) append entries to a
directory-scoped `_log.md`, grouped under `## YYYY-MM-DD` date headings. Entries
record *what* changed and on *which day*, but not *when* within the day. With
several writes per day the ordering is implicit and the exact time is lost.

This change adds a **UTC time of day to every log entry** while keeping the
existing date-group structure. It also fixes a latent inconsistency: date
groupings currently use the **local** date (`date.today()`), whereas the
frontmatter `timestamp` uses **UTC** (`_now_iso()` → `…Z`). After this change
the log's date heading and its entry times are both UTC, agreeing with the
frontmatter timestamp.

### Goals

- Prefix each `_log.md` entry with a bold UTC time: `* **HH:MM:SSZ** **<Keyword>**: …`.
- Switch the date-group heading to the **UTC** date so heading and time share one instant.
- Keep one source of truth for the write instant, so an entry's time always falls under the correct date heading (correct across midnight).

### Non-goals

- No `okf-core` changes. The time prefix is a **producer convention**, not an OKF
  conformance requirement — `LOG-03` already says even the bold keyword is
  optional. The validator (`_check_log`) only checks date-group headings.
- No change to `CONFORMANCE.md` examples — they illustrate the OKF standard, where
  times are not required; adding them would wrongly imply they are mandated.
- No change to entry wording, the `## YYYY-MM-DD` heading format, newest-first
  ordering, or the `_append_log` insertion logic.
- No backfilling of times onto pre-existing log entries.

## 2. Format

Date groups are unchanged; every entry gains a leading bold UTC time:

```markdown
# Update Log

## 2026-06-30
* **14:23:07Z** **Creation**: Added [Orders](orders.md).
* **09:11:02Z** **Move**: Moved [Sales](sales.md) from `tables/orders`.
* **08:00:55Z** **Deletion**: Removed `Customers`.
```

- Time is `HH:MM:SS` UTC with a trailing `Z`, second precision — consistent with
  `_now_iso()` (the frontmatter timestamp).
- The leading bold keyword (`**Creation**`, `**Update**`, `**Move**`,
  `**Deletion**`) is retained immediately after the time.

## 3. Implementation

All changes are in `packages/okf-mcp/src/okf_mcp/operations.py`.

### 3.1 One instant per write

Add a single UTC-now helper and derive everything from it:

```python
def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_date(dt: datetime) -> str:
    return dt.date().isoformat()              # "2026-06-30"


def _utc_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S") + "Z"      # "14:23:07Z"
```

- Rederive `_now_iso()` from `_now_utc()` (output unchanged:
  `…replace("+00:00", "Z")`).
- Remove `_today_iso()` (its only callers are the three entry builders; it used
  the local date). Each builder now calls `_now_utc()` once and passes
  `_utc_date(dt)` to `_append_log` while embedding `_utc_time(dt)` in the entry.
- Drop the now-unused `date` import from the `from datetime import …` line
  (`date.today()` in `_today_iso` was its only use); keep `datetime` and
  `timezone`.

### 3.2 Entry builders

Each builder computes `dt = _now_utc()` once and prefixes `**{time}** ` before
the existing bold keyword:

- `_append_log_for(concept_path, label, action, verb)` (Creation/Update):
  `* **{time}** **{action}**: {verb} [{label}]({name}).`
- `_log_move(...)` (Move): compute `dt` once and reuse for **both** the
  destination arrival and the source departure entries, so a move's two entries
  share the same time. Each entry: `* **{time}** **Move**: Moved …`.
- `_append_log_deletion(concept_path, label)` (Deletion):
  `* **{time}** **Deletion**: Removed \`{label}\`.`

### 3.3 `_append_log` unchanged

`_append_log(log_path, entry, date_group)` still creates the `# Update Log`
title when absent, inserts under an existing matching `## <date>` group, or
inserts a new date group above older ones — always prepending so the newest
entry sits on top (LOG-02). The `entry` it receives now already contains the
time; the `date_group` it receives is now the UTC date.

## 4. Conformance

- **LOG-01 (MUST):** date headings remain `## YYYY-MM-DD` (now UTC date) — the
  time is inside the bullet, never a heading. Still passes `_check_log`.
- **LOG-02 (SHOULD):** newest-first preserved (each write prepends within its
  group; times therefore read top-down newest-first).
- **LOG-03 (MAY):** bold keyword retained.

## 5. Testing (TDD)

`packages/okf-mcp/tests/test_operations.py`:

- **New** — `add`, `patch`, `move` (dest + source), and `delete` each write an
  entry matching the regex `^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* ` (time prefix
  present, second precision, `Z` suffix).
- **New** — a move's destination and source entries carry the **same** time
  string (single instant).
- **New** — the date-group heading is the UTC date: with a fixed instant
  (monkeypatched `_now_utc`), the heading equals `_utc_date(dt)`.
- **Update** — `test_delete_logs_deletion_entry`: its assertion
  `"* **Deletion**: Removed \`Orders\`." in log` is anchored to the bullet start
  and breaks under the prefix. Re-assert on the keyword-and-text substring
  (`"**Deletion**: Removed \`Orders\`." in log`) plus the time-prefix regex; keep
  the existing `"Removed [" not in log` check.
- **Unchanged (verify still pass)** — the direct `_append_log` tests (they pass
  explicit entries, so no time is added by them) and the substring-based
  add/patch/move assertions.

## 6. Housekeeping

- No README or `CLAUDE.md` change required (neither documents the log entry
  format). The `_log.md` description in both remains accurate.
