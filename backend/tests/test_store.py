import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import count
from pathlib import Path

import pytest

from db.store import (
    SCHEMA_VERSION,
    SETTING_DEFAULTS,
    ApiUsageRecord,
    CardFields,
    EnemySave,
    NotFoundError,
    Progression,
    SchemaVersionError,
    SettingValue,
    SignatureFields,
    Store,
    StoreError,
    UnitPlacement,
    UnitProgress,
    UnitSave,
    UnsafePathError,
)
from rules.units import Difficulty, MoveClass, PowerId, RangeClass, UnitClass

BASE_TIME = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)


class StepClock:
    def __init__(self) -> None:
        self._ticks = count()

    def __call__(self) -> datetime:
        return BASE_TIME + timedelta(seconds=next(self._ticks))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    instance = Store(tmp_path / "data" / "test.sqlite", clock=StepClock())
    yield instance
    instance.close()


def _seed_night_graph(store: Store, campaign_id: str) -> None:
    with store.transaction() as conn:
        conn.execute(
            "INSERT INTO object_signature (id, campaign_id, label, hist_json, area_cm2, aspect, "
            "ref_crop_path, created_at) VALUES ('sig1', ?, 'mug', '[]', 50.0, 1.0, 'c.png', 't')",
            (campaign_id,),
        )
        conn.execute(
            "INSERT INTO unit (id, campaign_id, object_signature_id, name, class, hp_max, atk, "
            "move_class, range_class, power_id) VALUES "
            "('unit1', ?, 'sig1', 'Kubo', 'kubo', 10, 0, 'none', 'none', 'none')",
            (campaign_id,),
        )
        conn.execute(
            "INSERT INTO night (id, campaign_id, number, started_at) VALUES ('n1', ?, 1, 't')",
            (campaign_id,),
        )
        conn.execute(
            "INSERT INTO night_unit (night_id, unit_id, sam_object_id, hp_current, x_cm, y_cm) "
            "VALUES ('n1', 'unit1', 1, 10, 30.0, 20.0)"
        )
        conn.execute(
            "INSERT INTO enemy (id, night_id, type, hp, x_cm, y_cm, spawn_turn) "
            "VALUES ('e_aswang_1', 'n1', 'aswang', 3, 30.0, 2.5, 1)"
        )
        conn.execute(
            "INSERT INTO turn_log (night_id, turn, phase, event_type, payload_json, t_ms, "
            "created_at) VALUES ('n1', 1, 'SPAWN_TELEGRAPH', 'spawn', '{}', 0, 't')"
        )


COUNT_QUERIES: dict[str, str] = {
    "campaign": "SELECT COUNT(*) FROM campaign",
    "object_signature": "SELECT COUNT(*) FROM object_signature",
    "unit": "SELECT COUNT(*) FROM unit",
    "night": "SELECT COUNT(*) FROM night",
    "night_unit": "SELECT COUNT(*) FROM night_unit",
    "enemy": "SELECT COUNT(*) FROM enemy",
    "turn_log": "SELECT COUNT(*) FROM turn_log",
    "api_usage": "SELECT COUNT(*) FROM api_usage",
    "campaign_recap": "SELECT COUNT(*) FROM campaign_recap",
}


def _count(store: Store, table: str) -> int:
    with store.transaction() as conn:
        return int(conn.execute(COUNT_QUERIES[table]).fetchone()[0])


def test_new_database_has_schema_and_foreign_keys(store: Store) -> None:
    assert store.schema_version() == SCHEMA_VERSION
    assert store.foreign_keys_enabled()


def test_reopen_keeps_data(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    first = Store(path)
    campaign = first.create_campaign("Barkada", Difficulty.NORMAL)
    first.close()
    second = Store(path)
    assert second.get_campaign(campaign.id).name == "Barkada"
    second.close()


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()
    with pytest.raises(SchemaVersionError):
        Store(path)


def test_create_and_get_campaign(store: Store) -> None:
    campaign = store.create_campaign("Gabi ng Barkada", Difficulty.MAHIRAP)
    loaded = store.get_campaign(campaign.id)
    assert loaded == campaign
    assert loaded.difficulty is Difficulty.MAHIRAP
    assert loaded.created_at.endswith("+00:00")


def test_get_missing_campaign_raises(store: Store) -> None:
    with pytest.raises(NotFoundError):
        store.get_campaign("missing")


def test_list_campaigns_newest_first_with_pages(store: Store) -> None:
    ids = [store.create_campaign(f"C{i}", Difficulty.NORMAL).id for i in range(3)]
    assert [c.id for c in store.list_campaigns(limit=2)] == [ids[2], ids[1]]
    assert [c.id for c in store.list_campaigns(limit=2, offset=2)] == [ids[0]]


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (51, 0), (10, -1)])
def test_list_campaigns_rejects_bad_page(store: Store, limit: int, offset: int) -> None:
    with pytest.raises(StoreError):
        store.list_campaigns(limit=limit, offset=offset)


def test_campaign_name_length_is_enforced(store: Store) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.create_campaign("", Difficulty.NORMAL)
    with pytest.raises(sqlite3.IntegrityError):
        store.create_campaign("x" * 41, Difficulty.NORMAL)


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO campaign (id, name, difficulty, created_at) VALUES ('c', 'n', 'easy', 't')",
        "INSERT INTO api_usage (ts, model, kind, cost_usd, ok) VALUES ('t', 'm', 'k', -1, 1)",
        "INSERT INTO api_usage (ts, model, kind, cost_usd, ok) VALUES ('t', 'm', 'k', 0, 2)",
    ],
)
def test_check_constraints_reject_bad_rows(store: Store, statement: str) -> None:
    with pytest.raises(sqlite3.IntegrityError), store.transaction() as conn:
        conn.execute(statement)


def test_unit_class_and_power_checks(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    _seed_night_graph(store, campaign.id)
    with pytest.raises(sqlite3.IntegrityError), store.transaction() as conn:
        conn.execute(
            "INSERT INTO unit (id, campaign_id, object_signature_id, name, class, hp_max, atk, "
            "move_class, range_class, power_id) VALUES "
            "('u2', ?, 'sig1', 'X', 'wizard', 4, 1, 'short', 'melee', 'P01')",
            (campaign.id,),
        )
    with pytest.raises(sqlite3.IntegrityError), store.transaction() as conn:
        conn.execute(
            "INSERT INTO unit (id, campaign_id, object_signature_id, name, class, hp_max, atk, "
            "move_class, range_class, power_id) VALUES "
            "('u3', ?, 'sig1', 'X', 'healer', 4, 4, 'short', 'melee', 'P01')",
            (campaign.id,),
        )


def test_sam_slot_is_unique_per_night(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    _seed_night_graph(store, campaign.id)
    with pytest.raises(sqlite3.IntegrityError), store.transaction() as conn:
        conn.execute(
            "INSERT INTO unit (id, campaign_id, object_signature_id, name, class, hp_max, atk, "
            "move_class, range_class, power_id) VALUES "
            "('unit2', ?, 'sig1', 'Pen', 'reach', 4, 2, 'medium', 'reach', 'P04')",
            (campaign.id,),
        )
        conn.execute(
            "INSERT INTO night_unit (night_id, unit_id, sam_object_id, hp_current, x_cm, y_cm) "
            "VALUES ('n1', 'unit2', 1, 4, 10.0, 10.0)"
        )


def test_foreign_keys_reject_orphans(store: Store) -> None:
    with pytest.raises(sqlite3.IntegrityError), store.transaction() as conn:
        conn.execute(
            "INSERT INTO night (id, campaign_id, number, started_at) VALUES ('n', 'nope', 1, 't')"
        )


def test_delete_campaign_cascades_every_row(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    _seed_night_graph(store, campaign.id)
    store.save_recap(campaign.id, "Kagabi...", "spark")
    store.set_progression(campaign.id, 2, 2)
    store.set_unit_progress("unit1", ["hp_up"], ["scar_1"])
    store.set_map_image(campaign.id, store.campaign_dir(campaign.id) / "map.png")
    assert store.delete_campaign(campaign.id)
    assert store.get_recap(campaign.id) is None
    assert store.campaign_units(campaign.id) == []
    for table in (
        "campaign_recap",
        "campaign",
        "object_signature",
        "unit",
        "night",
        "night_unit",
        "enemy",
        "turn_log",
    ):
        assert _count(store, table) == 0


def test_delete_missing_campaign_is_idempotent(store: Store) -> None:
    assert not store.delete_campaign("8a1f1f0e-2c4b-4d5e-9f00-0123456789ab")


def test_delete_campaign_refuses_unsafe_ids(store: Store) -> None:
    with pytest.raises(UnsafePathError):
        store.delete_campaign("../escape")


def test_delete_campaign_removes_files_and_owned_sprites(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    other = store.create_campaign("D", Difficulty.NORMAL)
    store.save_calibration(campaign.id, IDENTITY, 20.0, (60.0, 40.0), b"png")
    night = store.start_or_resume_night(campaign.id)
    other_night = store.start_or_resume_night(other.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    other_unit = store.add_unit(
        other_night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0)
    )
    owned = store.save_sprite("owned", b"a", "p", "v", None)
    shared = store.save_sprite("shared", b"b", "p", "v", None)
    store.set_unit_sprite(unit.unit_id, owned.id)
    store.set_style_anchor_if_missing(campaign.id, shared.id)
    store.set_unit_sprite(other_unit.unit_id, shared.id)
    directory = store.campaign_dir(campaign.id)
    assert directory.exists()
    assert store.delete_campaign(campaign.id)
    assert not directory.exists()
    assert not owned.path.exists()
    assert store.find_sprite("owned") is None
    assert shared.path.exists()
    assert store.find_sprite("shared") == shared
    assert store.campaign_dir(other.id).exists()
    assert [c.id for c in store.list_campaigns()] == [other.id]


def test_delete_campaign_sweeps_unlinked_sprites_and_stray_files(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    rerolled = store.save_sprite("rerolled", b"a", "p", "v", None)
    stray = store.data_root / "sprites" / "stray.png"
    stray.write_bytes(b"x")
    assert store.delete_campaign(campaign.id)
    assert store.find_sprite("rerolled") is None
    assert not rerolled.path.exists()
    assert not stray.exists()


def test_delete_campaign_reports_leftover_files(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    store.save_calibration(campaign.id, IDENTITY, 20.0, (60.0, 40.0), b"png")
    monkeypatch.setattr("db.store.shutil.rmtree", lambda *args, **kwargs: None)
    with pytest.raises(StoreError):
        store.delete_campaign(campaign.id)
    assert store.list_campaigns() == []


def test_secure_delete_is_on(store: Store) -> None:
    with store.transaction() as conn:
        assert conn.execute("PRAGMA secure_delete").fetchone()[0] == 1


def test_transaction_rolls_back_on_error(store: Store) -> None:
    with pytest.raises(RuntimeError), store.transaction() as conn:
        conn.execute(
            "INSERT INTO campaign (id, name, difficulty, created_at) "
            "VALUES ('c', 'n', 'normal', 't')"
        )
        raise RuntimeError("boom")
    assert _count(store, "campaign") == 0


def test_api_cost_sum_is_exact(store: Store) -> None:
    for _ in range(1000):
        store.record_api_usage(
            ApiUsageRecord(
                model="muse-spark-1.3",
                kind="spark",
                cost_usd=Decimal("0.0101"),
                ok=True,
            )
        )
    assert store.total_api_cost() == Decimal("10.1")


def test_api_cost_sum_starts_at_zero(store: Store) -> None:
    assert store.total_api_cost() == Decimal(0)


def test_api_usage_rejects_negative_cost(store: Store) -> None:
    with pytest.raises(StoreError):
        store.record_api_usage(
            ApiUsageRecord(
                model="sam-3.1", kind="sam_image", cost_usd=Decimal("-0.01"), ok=True
            )
        )


def test_api_usage_keeps_failed_calls(store: Store) -> None:
    store.record_api_usage(
        ApiUsageRecord(model="sam-3.1", kind="sam_image", cost_usd=Decimal(0), ok=False)
    )
    assert _count(store, "api_usage") == 1


def test_settings_upsert(store: Store) -> None:
    assert store.get_setting("camera") is None
    store.set_setting("camera", "0")
    store.set_setting("camera", "1")
    assert store.get_setting("camera") == "1"


IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def test_save_and_load_latest_calibration(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    assert store.latest_calibration(campaign.id) is None
    store.save_calibration(campaign.id, IDENTITY, 20.0, (60.0, 40.0), b"first")
    second = store.save_calibration(campaign.id, IDENTITY, 20.0, (50.0, 40.0), b"png")
    loaded = store.latest_calibration(campaign.id)
    assert loaded == second
    assert loaded.play_w_cm == 50.0
    assert loaded.baseline_path.read_bytes() == b"png"
    assert loaded.baseline_path.is_relative_to(store.data_root)


@pytest.mark.parametrize(
    "homography", [(1.0, 2.0), (float("inf"),) + IDENTITY[1:], (float("nan"),) * 9]
)
def test_calibration_rejects_bad_homography(
    store: Store, homography: tuple[float, ...]
) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    with pytest.raises(StoreError):
        store.save_calibration(campaign.id, homography, 20.0, (60.0, 40.0), b"x")


def test_calibration_needs_an_existing_campaign(store: Store) -> None:
    with pytest.raises(NotFoundError):
        store.save_calibration(
            "6f1d2a1e-7c1b-4c2e-9a3b-0a1b2c3d4e5f", IDENTITY, 20.0, (60.0, 40.0), b"x"
        )


@pytest.mark.parametrize(
    "campaign_id", ["../evil", "not-a-uuid", "6F1D2A1E-7C1B-4C2E-9A3B-0A1B2C3D4E5F", ""]
)
def test_campaign_dir_rejects_unsafe_ids(store: Store, campaign_id: str) -> None:
    with pytest.raises(UnsafePathError):
        store.campaign_dir(campaign_id)


def test_campaign_dir_stays_under_data_root(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    assert store.campaign_dir(campaign.id).is_relative_to(store.data_root)


def test_stored_baseline_path_cannot_escape(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    with store.transaction() as conn:
        conn.execute(
            "INSERT INTO calibration (id, campaign_id, homography_json, px_per_cm, play_w_cm, "
            "play_h_cm, baseline_path, created_at) VALUES ('x', ?, '[]', 20, 60, 40, "
            "'../../outside.png', '9999')",
            (campaign.id,),
        )
    with pytest.raises(UnsafePathError):
        store.latest_calibration(campaign.id)


def card_fields(name: str = "Kubo", unit_class: str = "kubo") -> CardFields:
    return CardFields(
        name=name,
        unit_class=UnitClass(unit_class),
        hp_max=10,
        atk=0,
        move_class=MoveClass.NONE,
        range_class=RangeClass.NONE,
        power_id=PowerId.NONE,
        power_name_tl="",
        card_text_tl="Bahay",
        card_text_en="House",
    )


SIGNATURE = SignatureFields(
    label="mug", histogram=(0.5, 0.5), area_cm2=40.0, aspect=1.0, ref_crop_png=b"png"
)


def test_night_is_resumed_until_it_ends(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    first = store.start_or_resume_night(campaign.id)
    assert first.number == 1
    assert store.start_or_resume_night(campaign.id) == first
    with store.transaction() as conn:
        conn.execute("UPDATE night SET result = 'win' WHERE id = ?", (first.id,))
    assert store.start_or_resume_night(campaign.id).number == 2


def test_add_and_list_units(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    kubo = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    assert (
        store.campaign_dir(campaign.id) / "crops" / f"{kubo.signature_id}.png"
    ).read_bytes() == b"png"
    units = store.night_units(night.id)
    assert units == [kubo]
    assert units[0].hp_current == 10


def test_duplicate_slot_rolls_back_the_crop(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    with pytest.raises(sqlite3.IntegrityError):
        store.add_unit(
            night, card_fields("Pen", "reach"), SIGNATURE, UnitPlacement(1, 10.0, 10.0)
        )
    assert len(list((store.campaign_dir(campaign.id) / "crops").iterdir())) == 1
    assert len(store.night_units(night.id)) == 1


def test_update_card_and_flags_and_turn_log(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    store.update_unit_card(night.id, unit.unit_id, card_fields("Bahay ni Lola"))
    assert store.night_units(night.id)[0].card.name == "Bahay ni Lola"
    with pytest.raises(NotFoundError):
        store.update_unit_card(night.id, "missing", card_fields())
    store.set_night_flags(night.id, {"rerolls": [unit.unit_id]})
    assert store.start_or_resume_night(campaign.id).flags == {"rerolls": [unit.unit_id]}
    with pytest.raises(NotFoundError):
        store.set_night_flags("missing", {})
    store.log_turn(night.id, 0, "SUMMON", "gm_invalid", {"why": "x"}, 5)
    assert store.turn_log_count(night.id, "gm_invalid") == 1


def test_sprite_cache_save_find_and_link(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    assert store.find_sprite("key-1") is None
    sprite = store.save_sprite("key-1", b"\x89PNG", "gabi16-v1", "sprite-v1", "resp_1")
    assert (
        store.save_sprite("key-1", b"other", "gabi16-v1", "sprite-v1", None) == sprite
    )
    assert store.find_sprite("key-1") == sprite
    assert store.sprite_png(sprite.id) == b"\x89PNG"
    store.set_unit_sprite(unit.unit_id, sprite.id)
    assert store.night_units(night.id)[0].sprite_id == sprite.id
    with pytest.raises(NotFoundError):
        store.set_unit_sprite("missing", sprite.id)
    with pytest.raises(NotFoundError):
        store.get_sprite("missing")


def test_style_anchor_is_set_once(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    first = store.save_sprite("a", b"1", "p", "v", None)
    second = store.save_sprite("b", b"2", "p", "v", None)
    assert store.style_anchor(campaign.id) is None
    store.set_style_anchor_if_missing(campaign.id, first.id)
    store.set_style_anchor_if_missing(campaign.id, second.id)
    assert store.style_anchor(campaign.id) == first.id
    with pytest.raises(NotFoundError):
        store.style_anchor("missing")


def test_stored_sprite_path_cannot_escape(store: Store) -> None:
    with store.transaction() as conn:
        conn.execute(
            "INSERT INTO sprite (id, cache_key, path, palette_version, prompt_version, created_at) "
            "VALUES ('s', 'k', '../evil.png', 'p', 'v', 't')"
        )
    with pytest.raises(UnsafePathError):
        store.find_sprite("k")


def test_signatures_and_positions(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    assert store.unit_signatures(night.id) == {unit.unit_id: ("mug", (0.5, 0.5))}
    store.update_positions(night.id, {unit.unit_id: (12.5, 7.25)})
    moved = store.night_units(night.id)[0]
    assert (moved.x_cm, moved.y_cm) == (12.5, 7.25)


def test_players_and_owners(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    migs = store.find_or_add_player(campaign.id, "Migs", "#F2C14E")
    assert store.find_or_add_player(campaign.id, "Migs", "#F2C14E") == migs
    store.set_unit_owner(unit.unit_id, migs)
    assert store.unit_owners(night.id) == {unit.unit_id: "Migs"}
    store.set_unit_owner(unit.unit_id, None)
    assert store.unit_owners(night.id) == {}
    with pytest.raises(NotFoundError):
        store.set_unit_owner("missing", None)
    with pytest.raises(sqlite3.IntegrityError):
        store.find_or_add_player(campaign.id, "Bea", "yellow")


def test_autosave_is_one_transaction(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    enemy = EnemySave(
        "e_aswang_1",
        "aswang",
        None,
        3,
        30.0,
        2.5,
        1,
        {"target_id": "u_kubo", "dmg": 2},
        (),
    )
    store.autosave(
        night.id,
        1,
        [UnitSave(unit.unit_id, 7, 31.0, 21.0, 1, ())],
        [enemy],
        None,
        [(1, "CHECK_END", "attack", {"dmg": 2}, 50)],
    )
    saved = store.night_units(night.id)[0]
    assert (saved.hp_current, saved.x_cm) == (7, 31.0)
    assert store.turn_log_count(night.id, "attack") == 1
    bad_enemy = EnemySave("e_x_1", "dragon", None, 3, 0.0, 0.0, 1, None, ())
    with pytest.raises(sqlite3.IntegrityError):
        store.autosave(
            night.id,
            2,
            [UnitSave(unit.unit_id, 1, 0.0, 0.0, 0, ())],
            [bad_enemy],
            None,
            [],
        )
    after = store.night_units(night.id)[0]
    assert after.hp_current == 7
    assert store.turn_log_count(night.id, "attack") == 1
    store.autosave(night.id, 8, [], [], "win", [])
    assert store.start_or_resume_night(campaign.id).number == 2


def test_saved_night_round_trips_the_autosave(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 30.0, 20.0))
    assert store.saved_night(night.id) is None
    enemy = EnemySave(
        "e_aswang_1",
        "aswang",
        None,
        3,
        30.0,
        2.5,
        1,
        {"target_id": "u_kubo", "dmg": 2},
        (),
    )
    upper = EnemySave(
        "e_manananggal_2", "manananggal", "upper", 0, 5.0, 5.0, 2, None, ("reform_2",)
    )
    board = {"enemies_defeated": 1, "enemy_counter": {"aswang": 1}}
    store.autosave(
        night.id,
        2,
        [UnitSave(unit.unit_id, 7, 31.0, 21.0, 1, ())],
        [enemy, upper],
        None,
        [],
        board,
    )
    saved = store.saved_night(night.id)
    assert saved is not None
    assert saved.turns_completed == 2
    assert saved.board == board
    assert saved.units == {unit.unit_id: UnitSave(unit.unit_id, 7, 31.0, 21.0, 1, ())}
    assert saved.enemies == (enemy, upper)
    store.autosave(night.id, 3, [], [], "lose", [], board)
    assert store.saved_night(night.id) is None
    with pytest.raises(NotFoundError):
        store.saved_night("missing")


def test_version_one_database_migrates(tmp_path: Path) -> None:
    path = tmp_path / "data" / "old.sqlite"
    first = Store(path)
    with first.transaction() as conn:
        conn.execute("ALTER TABLE night DROP COLUMN board_json")
        conn.execute("DROP TABLE campaign_recap")
        conn.execute("ALTER TABLE unit DROP COLUMN scars_json")
        conn.execute("ALTER TABLE campaign DROP COLUMN map_image_path")
    first._conn.execute("PRAGMA user_version = 1")
    first.close()
    second = Store(path)
    assert second.schema_version() == SCHEMA_VERSION == 3
    campaign = second.create_campaign("C", Difficulty.NORMAL)
    night = second.start_or_resume_night(campaign.id)
    second.autosave(night.id, 1, [], [], None, [], {"enemies_defeated": 0})
    assert second.saved_night(night.id) is not None
    second.close()


def test_turn_log_rows_and_replay_path(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    store.log_turn(
        night.id, 1, "CHECK_END", "attack", {"dst": "e_aswang_1", "dmg": 2}, 50
    )
    store.log_turn(night.id, 1, "CHECK_END", "win", {}, 70)
    assert store.turn_log_rows(night.id) == [
        (1, "CHECK_END", "attack", {"dst": "e_aswang_1", "dmg": 2}, 50),
        (1, "CHECK_END", "win", {}, 70),
    ]
    reel = store.campaign_dir(campaign.id) / "recordings" / "reel.mp4"
    store.set_replay_path(night.id, reel)
    with store.transaction() as conn:
        row = conn.execute(
            "SELECT replay_path FROM night WHERE id = ?", (night.id,)
        ).fetchone()
    assert row[0] == f"campaigns/{campaign.id}/recordings/reel.mp4"
    with pytest.raises(ValueError):
        store.set_replay_path(night.id, Path("C:/elsewhere/reel.mp4"))


def test_version_two_database_upgrades_with_rows_intact(tmp_path: Path) -> None:
    path = tmp_path / "data" / "v2.sqlite"
    first = Store(path, clock=StepClock())
    campaign = first.create_campaign("C", Difficulty.NORMAL)
    night = first.start_or_resume_night(campaign.id)
    unit = first.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 3.0, 4.0))
    first.set_setting("camera", "2")
    first.set_progression(campaign.id, 1, 1)
    with first.transaction() as conn:
        conn.execute("DROP TABLE campaign_recap")
        conn.execute("ALTER TABLE unit DROP COLUMN scars_json")
        conn.execute("ALTER TABLE campaign DROP COLUMN map_image_path")
    first._conn.execute("PRAGMA user_version = 2")
    first.close()
    second = Store(path, clock=StepClock())
    assert second.schema_version() == SCHEMA_VERSION == 3
    assert second.get_campaign(campaign.id).name == "C"
    assert second.get_progression(campaign.id) == Progression(1, 1)
    assert second.night_units(night.id) == [unit]
    assert second.get_setting("camera") == "2"
    assert second.get_unit_progress(unit.unit_id) == UnitProgress((), ())
    assert second.get_map_image(campaign.id) is None
    assert second.get_recap(campaign.id) is None
    second.save_recap(campaign.id, "Kagabi...", "line_bank")
    assert second.get_recap(campaign.id) is not None
    migrated = _table_columns(second)
    second.close()
    fresh = Store(tmp_path / "data" / "fresh.sqlite")
    assert _table_columns(fresh) == migrated
    fresh.close()


def _table_columns(store: Store) -> dict[str, list[str]]:
    with store.transaction() as conn:
        tables = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return {
            table: sorted(
                str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")
            )
            for table in tables
        }


def test_preferences_default_and_round_trip(store: Store) -> None:
    assert store.all_preferences() == dict(SETTING_DEFAULTS)
    assert store.get_preference("difficulty") == "normal"
    assert store.get_preference("replay_enabled") is True
    assert store.get_preference("tts_enabled") is False
    store.set_preference("difficulty", "hard")
    store.set_preference("camera_device", 2)
    store.set_preference("mic_device", "USB Mic")
    store.set_preference("caption_language", "en")
    store.set_preference("generated_map", True)
    store.set_preference("strict_ownership", True)
    prefs = store.all_preferences()
    assert prefs["difficulty"] == "hard"
    assert prefs["camera_device"] == 2
    assert prefs["mic_device"] == "USB Mic"
    assert prefs["caption_language"] == "en"
    assert prefs["generated_map"] is True
    assert prefs["strict_ownership"] is True


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("nope", True),
        ("difficulty", "madali"),
        ("caption_language", "xx"),
        ("camera_device", -1),
        ("camera_device", True),
        ("camera_device", "0"),
        ("mic_device", ""),
        ("mic_device", 3),
        ("replay_enabled", "yes"),
        ("tts_enabled", 1),
    ],
)
def test_preferences_reject_bad_input(
    store: Store, key: str, value: SettingValue
) -> None:
    with pytest.raises(StoreError):
        store.set_preference(key, value)


def test_preferences_survive_reopen_and_fall_back_when_corrupt(tmp_path: Path) -> None:
    path = tmp_path / "data" / "p.sqlite"
    first = Store(path)
    first.set_preference("tts_enabled", True)
    first.set_setting("difficulty", "not json")
    first.set_setting("camera_device", '"two"')
    first.close()
    second = Store(path)
    assert second.get_preference("tts_enabled") is True
    assert second.get_preference("difficulty") == "normal"
    assert second.get_preference("camera_device") == 0
    with pytest.raises(StoreError):
        second.get_preference("nope")
    second.close()


def test_progression_round_trip_and_limits(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    assert store.get_progression(campaign.id) == Progression(0, 0)
    store.set_progression(campaign.id, 5, 7)
    assert store.get_progression(campaign.id) == Progression(5, 7)
    assert store.get_campaign(campaign.id).barrio_level == 5
    for level, nights in ((6, 0), (-1, 0), (0, -1)):
        with pytest.raises(StoreError):
            store.set_progression(campaign.id, level, nights)
    with pytest.raises(NotFoundError):
        store.set_progression("missing", 1, 1)
    with pytest.raises(NotFoundError):
        store.get_progression("missing")


def test_unit_badges_and_scars(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 3.0, 4.0))
    assert store.get_unit_progress(unit.unit_id) == UnitProgress((), ())
    saved = store.set_unit_progress(
        unit.unit_id, ["hp_up", "hp_up", "cd_down"], ["scar_1"]
    )
    assert saved == UnitProgress(("hp_up", "cd_down"), ("scar_1",))
    assert store.get_unit_progress(unit.unit_id) == saved
    with store.transaction() as conn:
        row = conn.execute(
            "SELECT scars FROM unit WHERE id = ?", (unit.unit_id,)
        ).fetchone()
    assert row[0] == 1
    for bad in (["Bad Id"], [""], ["x" * 33], [f"b{i}" for i in range(9)]):
        with pytest.raises(StoreError):
            store.set_unit_progress(unit.unit_id, bad, [])
    with pytest.raises(NotFoundError):
        store.set_unit_progress("missing", [], [])
    with pytest.raises(NotFoundError):
        store.get_unit_progress("missing")


def test_recap_save_replace_clear(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    assert store.get_recap(campaign.id) is None
    first = store.save_recap(campaign.id, "Kagabi...", "spark")
    assert store.get_recap(campaign.id) == first
    second = store.save_recap(campaign.id, "Muli", "glimmer")
    assert store.get_recap(campaign.id) == second
    assert second.source == "glimmer"
    assert _count(store, "campaign_recap") == 1
    assert store.clear_recap(campaign.id)
    assert not store.clear_recap(campaign.id)
    assert store.get_recap(campaign.id) is None


def test_recap_rejects_bad_input(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    with pytest.raises(StoreError):
        store.save_recap(campaign.id, "x", "gpt")
    with pytest.raises(StoreError):
        store.save_recap(campaign.id, "", "spark")
    with pytest.raises(StoreError):
        store.save_recap(campaign.id, "x" * 1001, "spark")
    with pytest.raises(NotFoundError):
        store.save_recap("8a1f1f0e-2c4b-4d5e-9f00-0123456789ab", "x", "spark")


def test_campaign_units_list_signatures_for_matching(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    other = store.create_campaign("D", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    first = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 3.0, 4.0))
    second = store.add_unit(
        night, card_fields("Tasa", "wall"), SIGNATURE, UnitPlacement(2, 5.0, 6.0)
    )
    store.set_unit_progress(first.unit_id, ["hp_up"], [])
    units = store.campaign_units(campaign.id)
    assert [u.unit_id for u in units] == [first.unit_id, second.unit_id]
    stored = units[0]
    assert stored.card == card_fields()
    assert stored.signature.label == "mug"
    assert stored.signature.histogram == (0.5, 0.5)
    assert stored.signature.area_cm2 == 40.0
    assert stored.signature.aspect == 1.0
    assert stored.signature.ref_crop_path.read_bytes() == b"png"
    assert stored.progress.badges == ("hp_up",)
    assert store.campaign_units(other.id) == []


def test_campaign_units_refuse_escaping_crop_path(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    _seed_night_graph(store, campaign.id)
    with store.transaction() as conn:
        conn.execute("UPDATE object_signature SET ref_crop_path = '../../x.png'")
    with pytest.raises(UnsafePathError):
        store.campaign_units(campaign.id)


def test_map_image_path_round_trip_and_guards(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    assert store.get_map_image(campaign.id) is None
    target = store.campaign_dir(campaign.id) / "map.png"
    store.set_map_image(campaign.id, target)
    assert store.get_map_image(campaign.id) == target
    store.set_map_image(campaign.id, None)
    assert store.get_map_image(campaign.id) is None
    with pytest.raises(UnsafePathError):
        store.set_map_image(campaign.id, store.data_root / "elsewhere.png")
    with pytest.raises(NotFoundError):
        store.set_map_image("8a1f1f0e-2c4b-4d5e-9f00-0123456789ab", None)
    with pytest.raises(NotFoundError):
        store.get_map_image("8a1f1f0e-2c4b-4d5e-9f00-0123456789ab")
    with store.transaction() as conn:
        conn.execute("UPDATE campaign SET map_image_path = '../x.png'")
    with pytest.raises(UnsafePathError):
        store.get_map_image(campaign.id)


def test_delete_campaign_removes_map_file(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    target = store.campaign_dir(campaign.id) / "map.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"map")
    store.set_map_image(campaign.id, target)
    assert store.delete_campaign(campaign.id)
    assert not target.exists()


def test_attach_unit_reuses_a_stored_unit_in_a_later_night(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 3.0, 4.0))
    store.set_unit_progress(unit.unit_id, ["hp"], [])
    store.autosave(night.id, 8, [], [], "win", [], {})
    later = store.start_or_resume_night(campaign.id)
    assert later.id != night.id
    assert store.night_units(later.id) == []
    attached = store.attach_unit(later, unit.unit_id, UnitPlacement(2, 9.0, 8.0))
    assert attached.unit_id == unit.unit_id
    assert attached.sam_object_id == 2
    assert (attached.x_cm, attached.y_cm) == (9.0, 8.0)
    assert attached.card == card_fields()
    assert attached.hp_current == attached.card.hp_max
    assert store.get_unit_progress(unit.unit_id).badges == ("hp",)
    other = store.create_campaign("Other", Difficulty.NORMAL)
    other_night = store.start_or_resume_night(other.id)
    with pytest.raises(NotFoundError):
        store.attach_unit(other_night, unit.unit_id, UnitPlacement(1, 0.0, 0.0))


def test_unit_crops_read_the_reference_png_of_each_unit(store: Store) -> None:
    campaign = store.create_campaign("C", Difficulty.NORMAL)
    night = store.start_or_resume_night(campaign.id)
    unit = store.add_unit(night, card_fields(), SIGNATURE, UnitPlacement(1, 3.0, 4.0))
    assert store.unit_crops(night.id) == {unit.unit_id: b"png"}
