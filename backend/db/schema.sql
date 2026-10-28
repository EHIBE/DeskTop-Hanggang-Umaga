CREATE TABLE campaign (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
  difficulty TEXT NOT NULL CHECK (difficulty IN ('madali','normal','mahirap')),
  barrio_level INTEGER NOT NULL DEFAULT 0 CHECK (barrio_level BETWEEN 0 AND 5),
  nights_survived INTEGER NOT NULL DEFAULT 0 CHECK (nights_survived >= 0),
  style_anchor_sprite_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE calibration (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  homography_json TEXT NOT NULL,
  px_per_cm REAL NOT NULL CHECK (px_per_cm > 0),
  play_w_cm REAL NOT NULL CHECK (play_w_cm > 0),
  play_h_cm REAL NOT NULL CHECK (play_h_cm > 0),
  baseline_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE player (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL CHECK (length(display_name) BETWEEN 1 AND 24),
  color_hex TEXT NOT NULL CHECK (color_hex GLOB '#[0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F]')
);
CREATE TABLE object_signature (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 40),
  hist_json TEXT NOT NULL,
  area_cm2 REAL NOT NULL CHECK (area_cm2 > 0),
  aspect REAL NOT NULL CHECK (aspect > 0),
  ref_crop_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE sprite (
  id TEXT PRIMARY KEY,
  cache_key TEXT NOT NULL UNIQUE,
  path TEXT NOT NULL,
  palette_version TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  source_response_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE unit (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  object_signature_id TEXT NOT NULL REFERENCES object_signature(id),
  player_id TEXT REFERENCES player(id) ON DELETE SET NULL,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
  class TEXT NOT NULL CHECK (class IN ('kubo','charm','healer','fighter','reach','ranged','scout','wall')),
  hp_max INTEGER NOT NULL CHECK (hp_max >= 1),
  atk INTEGER NOT NULL CHECK (atk BETWEEN 0 AND 3),
  move_class TEXT NOT NULL CHECK (move_class IN ('none','short','medium','long')),
  range_class TEXT NOT NULL CHECK (range_class IN ('none','melee','reach','far')),
  power_id TEXT NOT NULL CHECK (power_id IN ('none','P01','P02','P03','P04','P05','P06','P07','P08','P09','P10','P11','P12')),
  power_name_tl TEXT,
  card_text_tl TEXT,
  card_text_en TEXT,
  sprite_id TEXT REFERENCES sprite(id) ON DELETE SET NULL,
  badges_json TEXT NOT NULL DEFAULT '[]',
  scars INTEGER NOT NULL DEFAULT 0 CHECK (scars >= 0)
);
CREATE TABLE night (
  id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
  number INTEGER NOT NULL CHECK (number >= 1),
  started_at TEXT NOT NULL,
  ended_at TEXT,
  result TEXT CHECK (result IN ('win','lose','abandoned')),
  turns_completed INTEGER NOT NULL DEFAULT 0 CHECK (turns_completed BETWEEN 0 AND 8),
  flags_json TEXT NOT NULL DEFAULT '{}',
  recap_tl TEXT,
  recap_en TEXT,
  recording_consent INTEGER NOT NULL DEFAULT 0 CHECK (recording_consent IN (0,1)),
  replay_path TEXT,
  cost_usd REAL NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
  UNIQUE (campaign_id, number)
);
CREATE TABLE night_unit (
  night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE,
  unit_id TEXT NOT NULL REFERENCES unit(id) ON DELETE CASCADE,
  sam_object_id INTEGER NOT NULL CHECK (sam_object_id BETWEEN 1 AND 16),
  hp_current INTEGER NOT NULL CHECK (hp_current >= 0),
  x_cm REAL NOT NULL,
  y_cm REAL NOT NULL,
  status_json TEXT NOT NULL DEFAULT '[]',
  cooldown INTEGER NOT NULL DEFAULT 0 CHECK (cooldown >= 0),
  PRIMARY KEY (night_id, unit_id),
  UNIQUE (night_id, sam_object_id)
);
CREATE TABLE enemy (
  id TEXT PRIMARY KEY,
  night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('aswang','tikbalang','kapre','manananggal','duwende')),
  part TEXT CHECK (part IN ('upper','lower')),
  hp INTEGER NOT NULL CHECK (hp >= 0),
  x_cm REAL NOT NULL,
  y_cm REAL NOT NULL,
  spawn_turn INTEGER NOT NULL CHECK (spawn_turn BETWEEN 1 AND 8),
  status_json TEXT NOT NULL DEFAULT '[]',
  intent_json TEXT,
  alive INTEGER NOT NULL DEFAULT 1 CHECK (alive IN (0,1))
);
CREATE TABLE voice_map (
  night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE,
  speaker_label TEXT NOT NULL,
  player_id TEXT NOT NULL REFERENCES player(id) ON DELETE CASCADE,
  PRIMARY KEY (night_id, speaker_label)
);
CREATE TABLE turn_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  night_id TEXT NOT NULL REFERENCES night(id) ON DELETE CASCADE,
  turn INTEGER NOT NULL CHECK (turn BETWEEN 0 AND 8),
  phase TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  t_ms INTEGER NOT NULL CHECK (t_ms >= 0),
  created_at TEXT NOT NULL
);
CREATE TABLE api_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  model TEXT NOT NULL,
  kind TEXT NOT NULL,
  input_tokens INTEGER CHECK (input_tokens >= 0),
  cached_tokens INTEGER CHECK (cached_tokens >= 0),
  output_tokens INTEGER CHECK (output_tokens >= 0),
  images INTEGER CHECK (images >= 0),
  frames INTEGER CHECK (frames >= 0),
  audio_seconds INTEGER CHECK (audio_seconds >= 0),
  cost_usd REAL NOT NULL CHECK (cost_usd >= 0),
  latency_ms INTEGER CHECK (latency_ms >= 0),
  ok INTEGER NOT NULL CHECK (ok IN (0,1))
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX idx_turn_log_night ON turn_log(night_id, turn);
CREATE INDEX idx_calibration_campaign ON calibration(campaign_id);
CREATE INDEX idx_player_campaign ON player(campaign_id);
CREATE INDEX idx_object_signature_campaign ON object_signature(campaign_id);
CREATE INDEX idx_unit_campaign ON unit(campaign_id);
CREATE INDEX idx_unit_signature ON unit(object_signature_id);
CREATE INDEX idx_night_campaign ON night(campaign_id);
CREATE INDEX idx_night_unit_unit ON night_unit(unit_id);
CREATE INDEX idx_enemy_night ON enemy(night_id);
CREATE INDEX idx_voice_map_player ON voice_map(player_id);
CREATE INDEX idx_api_usage_ts ON api_usage(ts);
CREATE INDEX idx_campaign_created ON campaign(created_at);
