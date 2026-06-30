# okf-mcp Timestamped Log Entries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefix every `_log.md` entry with a bold UTC time (`* **HH:MM:SSZ** **<Keyword>**: …`) and switch the date-group heading from the local date to the UTC date, both derived from one instant per write.

**Architecture:** A single `_now_utc()` helper provides the write instant; `_utc_date()` and `_utc_time()` derive the heading string and the entry's time prefix from it. The three entry builders (`_append_log_for`, `_log_move`, `_append_log_deletion`) embed the time and pass the UTC date to the unchanged `_append_log`. `_now_iso()` (frontmatter timestamp) is rederived from `_now_utc()` with identical output.

**Tech Stack:** Python 3.12, pytest, `uv`. Change confined to `okf-mcp`.

## Global Constraints

- Change is confined to `packages/okf-mcp/src/okf_mcp/operations.py` and its test file. No `okf-core`, `CONFORMANCE.md`, `README.md`, or `CLAUDE.md` changes (the time prefix is a producer convention, not an OKF conformance requirement).
- Time format: `HH:MM:SS` UTC with a trailing `Z`, second precision (consistent with `_now_iso()`).
- Date-group heading: UTC `YYYY-MM-DD` (was local date) — keeps LOG-01.
- `_append_log`'s insertion logic and newest-first ordering (LOG-02) are unchanged; only the `entry` text and `date_group` string passed to it change.
- The leading bold keyword (`**Creation**`/`**Update**`/`**Move**`/`**Deletion**`) is retained immediately after the time (LOG-03).
- Run tests with `uv run pytest` from the workspace root.
- Conventional commit scoped to the package; end the commit message with the `Co-Authored-By` trailer shown below.
- Spec: `docs/superpowers/specs/2026-06-30-okf-mcp-log-timestamps-design.md`.

## File Structure

- `packages/okf-mcp/src/okf_mcp/operations.py` — **modify**: add `_now_utc`/`_utc_date`/`_utc_time`, rederive `_now_iso`, remove `_today_iso` and the unused `date` import, and embed the time in the three entry builders.
- `packages/okf-mcp/tests/test_operations.py` — **modify**: add time-prefix tests for add/patch/move/delete, a deterministic UTC heading+time test, a move single-instant test, and adjust the one anchored deletion-log assertion.

---

### Task 1: Timestamped, UTC log entries

**Files:**
- Modify: `packages/okf-mcp/src/okf_mcp/operations.py` (helpers at lines 4, 45-55; builders `_append_log_for` ~80-84, `_log_move` ~251-277, `_append_log_deletion`)
- Test: `packages/okf-mcp/tests/test_operations.py`

**Interfaces:**
- Consumes: existing `_append_log(log_path, entry, date_group)` (unchanged), `LOG_FILENAME`.
- Produces:
  - `_now_utc() -> datetime` — current UTC time, microsecond-stripped.
  - `_utc_date(dt: datetime) -> str` — `"YYYY-MM-DD"`.
  - `_utc_time(dt: datetime) -> str` — `"HH:MM:SSZ"`.
  - `_now_iso() -> str` — unchanged output (`"YYYY-MM-DDTHH:MM:SSZ"`), now rederived from `_now_utc()`.
  - Entry builders emit `* **<HH:MM:SSZ>** **<Keyword>**: …` and group under the UTC date.

- [ ] **Step 1: Write the failing tests**

Add `import re` to the top of `packages/okf-mcp/tests/test_operations.py` (the file currently starts with `import pytest`):

```python
import re

import pytest
```

Append these tests to `packages/okf-mcp/tests/test_operations.py`:

```python
def test_add_log_entry_has_time_prefix(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert re.search(r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Creation\*\*:", log, re.M)


def test_patch_log_entry_has_time_prefix(tmp_path):
    operations.add_concept(tmp_path, "a", {"type": "X"}, "")
    operations.patch_concept(tmp_path, "a", {"title": "A2"})
    log = (tmp_path / "_log.md").read_text()
    assert re.search(r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Update\*\*:", log, re.M)


def test_move_log_entries_have_time_prefix(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    dest = (tmp_path / "models" / "_log.md").read_text()
    src = (tmp_path / "tables" / "_log.md").read_text()
    pat = r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Move\*\*:"
    assert re.search(pat, dest, re.M)
    assert re.search(pat, src, re.M)


def test_delete_log_entry_has_time_prefix(tmp_path):
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    operations.add_concept(tmp_path, "tables/customers", {"type": "Table"}, "")
    operations.delete_concept(tmp_path, "tables/orders")
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert re.search(r"^\* \*\*\d{2}:\d{2}:\d{2}Z\*\* \*\*Deletion\*\*:", log, re.M)


def test_log_heading_and_time_are_utc(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    fixed = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
    monkeypatch.setattr(operations, "_now_utc", lambda: fixed)
    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    log = (tmp_path / "tables" / "_log.md").read_text()
    assert "## 2026-06-30" in log
    assert "* **23:59:59Z** **Creation**: Added [Orders](orders.md)." in log


def test_move_entries_share_one_instant(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    operations.add_concept(
        tmp_path, "tables/orders", {"type": "Table", "title": "Orders"}, ""
    )
    times = iter(
        [
            datetime(2026, 6, 30, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 30, 2, 0, 0, tzinfo=timezone.utc),
        ]
    )
    monkeypatch.setattr(operations, "_now_utc", lambda: next(times))
    operations.move_concept(tmp_path, "tables/orders", "models/orders")
    dest = (tmp_path / "models" / "_log.md").read_text()
    src = (tmp_path / "tables" / "_log.md").read_text()
    # _log_move computes _now_utc() once and reuses it for both entries.
    assert "**01:00:00Z**" in dest
    assert "**01:00:00Z**" in src
```

Then update the existing `test_delete_logs_deletion_entry` so its assertion is not anchored to the bullet start (which the time prefix now occupies). Change:

```python
    assert "* **Deletion**: Removed `Orders`." in log
```

to:

```python
    assert "**Deletion**: Removed `Orders`." in log
```

(Leave the surrounding `"Removed [" not in log` and `res["log"] == "tables/_log.md"` assertions untouched.)

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k "time_prefix or are_utc or one_instant" -v`
Expected: the six new tests FAIL — current entries have no `**HH:MM:SSZ**` prefix (regex misses), and `test_log_heading_and_time_are_utc` fails because `operations._now_utc` does not yet exist (AttributeError from `monkeypatch.setattr`).

- [ ] **Step 3: Replace the datetime import and time helpers**

In `packages/okf-mcp/src/okf_mcp/operations.py`, change the import on line 4 from:

```python
from datetime import date, datetime, timezone
```

to:

```python
from datetime import datetime, timezone
```

Then replace the `_now_iso` / `_today_iso` block (lines 45-55):

```python
def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _today_iso() -> str:
    return date.today().isoformat()
```

with:

```python
def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_iso() -> str:
    return _now_utc().isoformat().replace("+00:00", "Z")


def _utc_date(dt: datetime) -> str:
    return dt.date().isoformat()


def _utc_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S") + "Z"
```

- [ ] **Step 4: Embed the time in `_append_log_for`**

Replace `_append_log_for` (lines ~80-84):

```python
def _append_log_for(concept_path: Path, label: str, action: str, verb: str) -> Path:
    log_path = concept_path.parent / LOG_FILENAME
    entry = f"* **{action}**: {verb} [{label}]({concept_path.name})."
    _append_log(log_path, entry, _today_iso())
    return log_path
```

with:

```python
def _append_log_for(concept_path: Path, label: str, action: str, verb: str) -> Path:
    log_path = concept_path.parent / LOG_FILENAME
    dt = _now_utc()
    entry = (
        f"* **{_utc_time(dt)}** **{action}**: "
        f"{verb} [{label}]({concept_path.name})."
    )
    _append_log(log_path, entry, _utc_date(dt))
    return log_path
```

- [ ] **Step 5: Embed the time in `_log_move`**

Replace the body of `_log_move` so both entries share one instant. Change:

```python
    label = str(frontmatter.get("title") or to_path.stem)
    today = _today_iso()
    dest_log = to_path.parent / LOG_FILENAME
    _append_log(
        dest_log,
        f"* **Move**: Moved [{label}]({to_path.name}) from `{from_id}`.",
        today,
    )
    logs = [dest_log]
    if from_path.parent != to_path.parent:
        src_log = from_path.parent / LOG_FILENAME
        _append_log(
            src_log,
            f"* **Move**: Moved [{label}]({from_path.name}) to `{to_id}`.",
            today,
        )
        logs.append(src_log)
    return logs
```

to:

```python
    label = str(frontmatter.get("title") or to_path.stem)
    dt = _now_utc()
    date_group, time = _utc_date(dt), _utc_time(dt)
    dest_log = to_path.parent / LOG_FILENAME
    _append_log(
        dest_log,
        f"* **{time}** **Move**: Moved [{label}]({to_path.name}) from `{from_id}`.",
        date_group,
    )
    logs = [dest_log]
    if from_path.parent != to_path.parent:
        src_log = from_path.parent / LOG_FILENAME
        _append_log(
            src_log,
            f"* **{time}** **Move**: Moved [{label}]({from_path.name}) to `{to_id}`.",
            date_group,
        )
        logs.append(src_log)
    return logs
```

- [ ] **Step 6: Embed the time in `_append_log_deletion`**

Replace `_append_log_deletion`:

```python
def _append_log_deletion(concept_path: Path, label: str) -> Path:
    """Append a Deletion entry to the directory's log.

    The label is backticked (not a markdown link) because the file is gone --
    a link entry would itself be a dangling link.
    """
    log_path = concept_path.parent / LOG_FILENAME
    _append_log(log_path, f"* **Deletion**: Removed `{label}`.", _today_iso())
    return log_path
```

with:

```python
def _append_log_deletion(concept_path: Path, label: str) -> Path:
    """Append a Deletion entry to the directory's log.

    The label is backticked (not a markdown link) because the file is gone --
    a link entry would itself be a dangling link.
    """
    log_path = concept_path.parent / LOG_FILENAME
    dt = _now_utc()
    _append_log(
        log_path, f"* **{_utc_time(dt)}** **Deletion**: Removed `{label}`.", _utc_date(dt)
    )
    return log_path
```

- [ ] **Step 7: Run the log tests to verify they pass**

Run: `uv run pytest packages/okf-mcp/tests/test_operations.py -k "log or time_prefix or are_utc or one_instant or delete" -v`
Expected: PASS (the six new tests, the updated `test_delete_logs_deletion_entry`, and the existing `_append_log` / add / patch / move / delete log tests).

- [ ] **Step 8: Run the full suite to confirm no regressions**

Run: `uv run pytest`
Expected: PASS (entire workspace; the substring-based add/patch/move log assertions still hold, and the direct `_append_log` tests are unaffected since they pass explicit entries).

- [ ] **Step 9: Commit**

```bash
git add packages/okf-mcp/src/okf_mcp/operations.py \
        packages/okf-mcp/tests/test_operations.py
git commit -m "feat(okf-mcp): timestamp _log.md entries with UTC time" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
