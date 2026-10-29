---
title: Data model
purpose: SQLite tables, constraints, IDs, autosave and data lifecycle
read_when: [writing backend/db/schema.sql or store.py, adding a column, delete campaign]
canonical_for: [SQLite schema, ID schemes, autosave transaction, data lifecycle]
sources: [docs/DeskTop_PRD.md#sqlite-schema, docs/DeskTop_PRD.md#sam-usage-spec]
status: active
last_verified: 2026-10-28
related: [docs/architecture/backend-modules.md, docs/engineering/security-and-privacy.md, docs/decisions/ADR-0107-money-precision.md]
---

# Data model

All state lives in one SQLite file in the Electron user data folder. `backend/db/schema.sql` (schema version 2 in `PRAGMA user_version`) implements the schema below plus the changes under "Built schema changes".

## Key facts

| Fact | Value |
|---|---|
| Engine | SQLite via Python `sqlite3` |
| Location | `%APPDATA%\DeskTop\` (path passed from Electron main) |
| Tables | campaign, calibration, player, object_signature, sprite, unit, night, night_unit, enemy, voice_map, turn_log, api_usage, settings |
| IDs | TEXT UUIDs for entities. Game-state IDs `u_*` and `e_<type>_<n>` |
| Time | UTC ISO 8601 text, turn timing in `t_ms` |
| Migrations | `PRAGMA user_version` is 2. `db/store.py` builds a fresh database, steps version 1 up with `MIGRATIONS`, and refuses a newer version. Schema changes after a database exists need approval and a stepped migration |
| Money | REAL columns, values rounded to 1e-8 USD on write and summed as integers, Decimal in code (ADR-0107) |

## Schema

```sql
CREATE TABLE campaign (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, difficulty TEXT NOT NULL CHECK (difficulty IN ('madali','normal','mahirap')),
  barrio_level INTEGER NOT NULL DEFAULT 0, nights_survived INTEGER NOT NULL DEFAULT 0,
  style_anchor_sprite_id TEXT, created_at TEXT NOT NULL
);
CREATE TABLE calibration (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  homography_json TEXT NOT NULL, px_per_cm REAL NOT NULL, play_w_cm REAL NOT NULL, play_h_cm REAL NOT NULL,
  baseline_path TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE player (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL, color_hex TEXT NOT NULL
);
CREATE TABLE object_signature (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  label TEXT NOT NULL, hist_json TEXT NOT NULL, area_cm2 REAL NOT NULL, aspect REAL NOT NULL,
  ref_crop_path TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE sprite (
  id TEXT PRIMARY KEY, cache_key TEXT NOT NULL UNIQUE, path TEXT NOT NULL,
  palette_version TEXT NOT NULL, prompt_version TEXT NOT NULL, source_response_id TEXT, created_at TEXT NOT NULL
);
CREATE TABLE unit (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  object_signature_id TEXT NOT NULL REFERENCES object_signature(id),
  player_id TEXT REFERENCES player(id), name TEXT NOT NULL,
  class TEXT NOT NULL, hp_max INTEGER NOT NULL, atk INTEGER NOT NULL,
  move_class TEXT NOT NULL, range_class TEXT NOT NULL, power_id TEXT NOT NULL,
  power_name_tl TEXT, card_text_tl TEXT, card_text_en TEXT,
  sprite_id TEXT REFERENCES sprite(id), badges_json TEXT NOT NULL DEFAULT '[]', scars INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE night (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  number INTEGER NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
  result TEXT CHECK (result IN ('win','lose','abandoned')), turns_completed INTEGER NOT NULL DEFAULT 0,
  flags_json TEXT NOT NULL DEFAULT '{}', recap_tl TEXT, recap_en TEXT,
  recording_consent INTEGER NOT NULL DEFAULT 0, replay_path TEXT, cost_usd REAL NOT NULL DEFAULT 0,
  UNIQUE (campaign_id, number)
);
CREATE TABLE night_unit (
  night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE, unit_id TEXT NOT NULL REFERENCES unit(id),
  sam_object_id INTEGER NOT NULL CHECK (sam_object_id BETWEEN 1 AND 16),
  hp_current INTEGER NOT NULL, x_cm REAL NOT NULL, y_cm REAL NOT NULL, status_json TEXT NOT NULL DEFAULT '[]',
  cooldown INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (night_id, unit_id), UNIQUE (night_id, sam_object_id)
);
CREATE TABLE enemy (
  id TEXT PRIMARY KEY, night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE,
  type TEXT NOT NULL, part TEXT, hp INTEGER NOT NULL, x_cm REAL NOT NULL, y_cm REAL NOT NULL,
  spawn_turn INTEGER NOT NULL, status_json TEXT NOT NULL DEFAULT '[]', intent_json TEXT, alive INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE voice_map (
  night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE, speaker_label TEXT NOT NULL,
  player_id TEXT NOT NULL REFERENCES player(id), PRIMARY KEY (night_id, speaker_label)
);
CREATE TABLE turn_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE,
  turn INTEGER NOT NULL, phase TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
  t_ms INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE api_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, model TEXT NOT NULL, kind TEXT NOT NULL,
  input_tokens INTEGER, cached_tokens INTEGER, output_tokens INTEGER, images INTEGER, frames INTEGER,
  audio_seconds INTEGER, cost_usd REAL NOT NULL, latency_ms INTEGER, ok INTEGER NOT NULL
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX idx_turn_log_night ON turn_log(night_id, turn);
```

## Constraint gaps to consider (before the first database exists)

| Gap | Proposal |
|---|---|
| `unit.class`, `move_class`, `range_class`, `power_id` have no CHECK | Add CHECK lists matching the enums |
| `enemy.type` has no CHECK | Add CHECK for the five types |
| No index on `unit.campaign_id`, `night.campaign_id`, `enemy.night_id` | Add indexes for lookups |
| No index on `api_usage.ts` | Add for the cost meter sum |
| Foreign keys off by default in SQLite | Run `PRAGMA foreign_keys = ON` on every connection |
| REAL money | ADR-0107 |

## Built schema changes (2026-10-28)

| Change | Why |
|---|---|
| CHECK lists on `unit.class`, `move_class` (none, short, medium, long), `range_class` (none, melee, reach, far), `power_id`, `enemy.type`, `enemy.part` (upper, lower) | Back enum validation with storage |
| Range checks on atk (0 to 3), hp_max (1 or more), sam_object_id (1 to 16), turns (0 to 8), costs (0 or more), 0 or 1 flags, name lengths | Back validation rules |
| `night_unit.unit_id` and `voice_map.player_id` ON DELETE CASCADE. `unit.player_id` and `unit.sprite_id` ON DELETE SET NULL | Delete campaign leaves no orphans |
| Indexes on every campaign_id and night_id foreign key, `unit.object_signature_id`, `night_unit.unit_id`, `voice_map.player_id`, `api_usage.ts`, `campaign.created_at` | Lookups, joins, the cost meter sum and the campaign list sort |
| `PRAGMA foreign_keys = ON` and WAL journal on every connection | Foreign keys are off by default in SQLite |
| `PRAGMA secure_delete = ON` on every connection, WAL checkpoint after delete campaign | Deleted rows do not linger in free pages or the WAL file |
| `night.board_json` (version 2, added M10, approval pending from EHIBE) | Restore needs rules counters the tables do not hold: players, player order, enemies defeated, enemy id counters, damage per owner, unit hulls. Manananggal reform timers ride in `enemy.status_json` as `reform_<n>` |

## ID schemes

| ID | Meaning |
|---|---|
| SAM object ID 1 | Always the kubo |
| SAM IDs 2 to 12 | Other units in summon order |
| SAM IDs 13 to 16 | Reserved, never used |
| `unit.id` | UUID, persistent across nights. `night_unit.sam_object_id` maps the slot |
| Game-state IDs | `u_<slug>` for units, `e_<type>_<n>` for enemies, used in GM input and enums |

## Autosave

One transaction at CHECK_END writes `night_unit`, `enemy`, `night` (with `board_json`) and that turn's `turn_log` rows. Roll back fully on failure. Restore resumes at the start of the current turn's PLAYER_PHASE: Begin Night on an unfinished night with turns done rebuilds the board and runs `begin_turn`, which is deterministic, so spawns and intents match the original. Summon and re-roll are refused until then.

## Lifecycle and deletion

| Data | Where | Deleted by |
|---|---|---|
| DB rows | SQLite | Delete campaign (cascade) |
| Sprites made in play | `%APPDATA%\DeskTop\` | Delete campaign |
| Baseline and reference crops | `%APPDATA%\DeskTop\` | Delete campaign |
| Recordings and reels | `%APPDATA%\DeskTop\campaigns\<campaign id>\recordings\night_<n>_<ms>.mp4` (built Phase 13), `night.recording_consent` set when claims finish | Delete clip or delete campaign (the campaign folder is removed) |
| Uploaded replay proxy | Meta Files API | Explicit DELETE after processing, `expires_after` 86,400 s backup |
| api_usage | SQLite | Kept (cost audit) |

Delete only paths that resolve inside the user data root (FR-52).
