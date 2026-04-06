# Crontab Pause/Resume — Design Spec

**Date:** 2026-04-06  
**Status:** Approved

---

## Overview

Add the ability to pause (disable) and resume (enable) individual crontab entries without deleting them. The paused state is stored directly in the crontab file using a `#PAUSED:` marker prefix, keeping the file as the single source of truth with no database changes required.

---

## Storage Strategy

Paused entries are serialized in the crontab file using a `#PAUSED:` prefix (no space after `#` to distinguish from regular description comments which use `# `):

```
# Active entry with description comment
0 * * * * /usr/bin/backup.sh

# Paused entry (invisible to cron daemon, parseable by the app)
#PAUSED:0 * * * * /usr/bin/backup.sh
```

The cron daemon ignores any line starting with `#`, so paused entries are effectively disabled. The app detects and restores them transparently.

---

## Backend Changes

### `backend/schemas/crontab.py`

Add `enabled: bool = True` field to `CrontabEntry`.  
`CrontabEntryCreate` remains unchanged (you cannot create a paused entry, only toggle existing ones).

### `backend/services/crontab_service.py`

**Parser (`_parse_raw_with_envvars`):**  
- Detect lines matching `#PAUSED:<cron fields> <command>` (regex: `^#PAUSED:(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$`)
- Parse them as `CrontabEntry` with `enabled=False`
- Also handle `#PAUSED:@special <command>` for special strings

**Serializer (`_entries_and_envs_to_text`):**  
- If `entry.enabled` is `False`, emit `#PAUSED:{fields} {command}` instead of the normal line
- Description comment (`# comment`) is still emitted before the paused line

**New function `toggle_entry(entry_id: int) -> List[CrontabEntry]`:**  
- Load entries, find by id, flip `enabled`, save, return updated list

### `backend/routers/crontab.py`

New endpoint:

```python
PATCH /api/crontab/{entry_id}/toggle
```

- Requires admin role
- No request body
- Returns `List[CrontabEntry]` (same pattern as all other crontab endpoints)
- Audit log: `crontab_toggle user=<user> entry_id=<id> enabled=<new_state>`

---

## Frontend Changes

### `frontend/src/views/CrontabView.vue`

**Table row styling:**  
- Class `entry--paused` on rows where `!data.enabled`
- CSS: `opacity: 0.45`, `text-decoration: line-through` on the expression cell

**Action column:**  
- New icon button before the delete button (admin only)
- `pi-pause` icon (orange) when entry is active → click pauses it
- `pi-play` icon (green) when entry is paused → click resumes it
- Tooltip: `"Pause"` / `"Resume"`
- Calls `PATCH /api/crontab/{id}/toggle`, updates local `entries` list

**Filter:**  
- Three pill buttons in the list panel header: `ALL` / `ACTIVE` / `PAUSED`
- Default: `ALL`
- Filters the DataTable via a computed `filteredEntries` property
- Does not affect the editing panel (selecting a paused entry still loads it in the editor)

---

## Out of Scope

- Creating entries in paused state
- Bulk pause/resume
- Audit history of who paused what and when (no DB changes)
- Editing a paused entry's schedule is allowed — the entry stays paused after saving the edit (the `#PAUSED:` marker is preserved)
