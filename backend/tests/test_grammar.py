import statistics
import time

import pytest

from voice.grammar import (
    ATTACK_WORDS,
    CANCEL_WORDS,
    HEAL_WORDS,
    POWER_WORDS,
    Command,
    CommandKind,
    GrammarContext,
    GrammarEnemy,
    GrammarUnit,
    normalize,
    parse_command,
)

SPEARMAN = GrammarUnit("u_spear", "Spearman", "reach", 10.0, 10.0)
CHARM = GrammarUnit("u_charm", "Anting-anting", "charm", 20.0, 10.0)
HEALER = GrammarUnit("u_heal", "Albularyo", "healer", 30.0, 10.0)
KUBO = GrammarUnit("u_kubo", "Kubo", "kubo", 50.0, 50.0)

ASWANG_1 = GrammarEnemy("e_aswang_1", "aswang", 12.0, 12.0)
ASWANG_2 = GrammarEnemy("e_aswang_2", "aswang", 80.0, 80.0)
KAPRE_1 = GrammarEnemy("e_kapre_1", "kapre", 11.0, 10.0)

CONTEXT = GrammarContext(
    units=(SPEARMAN, CHARM, HEALER, KUBO),
    enemies=(ASWANG_1, ASWANG_2, KAPRE_1),
)


def parse(text: str, context: GrammarContext = CONTEXT) -> Command | None:
    return parse_command(text, context)


@pytest.mark.parametrize("word", ATTACK_WORDS)
def test_every_attack_word(word: str) -> None:
    assert parse(f"Spearman {word} aswang") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


@pytest.mark.parametrize("word", POWER_WORDS)
def test_every_power_word(word: str) -> None:
    assert parse(f"Anting-anting {word} kubo") == Command(
        CommandKind.POWER, "u_charm", "u_kubo"
    )


@pytest.mark.parametrize("word", HEAL_WORDS)
def test_every_heal_word(word: str) -> None:
    assert parse(f"Albularyo {word} Spearman") == Command(
        CommandKind.HEAL, "u_heal", "u_spear"
    )


@pytest.mark.parametrize("text", ["tapos", "Tapos na", "end turn", "End Turn!", "done"])
def test_every_end_turn_word(text: str) -> None:
    assert parse(text) == Command(CommandKind.END_TURN, None, None)


@pytest.mark.parametrize("word", CANCEL_WORDS)
def test_every_cancel_word(word: str) -> None:
    assert parse(word) == Command(CommandKind.CANCEL, None, None)


def test_doc_examples() -> None:
    assert parse("Spearman, saksakin ang aswang!") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )
    assert parse("Anting-anting, protektahan ang kubo!") == Command(
        CommandKind.POWER, "u_charm", "u_kubo"
    )
    assert parse("Albularyo, gamutin si Spearman") == Command(
        CommandKind.HEAL, "u_heal", "u_spear"
    )
    assert parse("Tapos!") == Command(CommandKind.END_TURN, None, None)
    assert parse("Hindi, mali") == Command(CommandKind.CANCEL, None, None)


def test_cancel_in_the_middle_does_not_cancel_the_order() -> None:
    assert parse("Spearman saksakin aswang, hindi tapos") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


@pytest.mark.parametrize(
    "text", ["hindi tapos", "hindi yan", "mali yan", "wag na", "huwag na"]
)
def test_leading_cancel_phrases(text: str) -> None:
    assert parse(text) == Command(CommandKind.CANCEL, None, None)


def test_leading_cancel_word_before_an_action_cancels() -> None:
    assert parse("wag na atake Spearman") == Command(CommandKind.CANCEL, None, None)
    assert parse("huwag saksakin si Spearman") == Command(
        CommandKind.CANCEL, None, None
    )


@pytest.mark.parametrize("word", ["huwag", "ayaw", "kansela", "stop"])
def test_extended_cancel_words(word: str) -> None:
    assert word in CANCEL_WORDS


def test_leading_hindi_with_a_clear_order_keeps_the_order() -> None:
    assert parse("hindi ko alam, atake si Spearman sa aswang") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )
    assert parse("mali, Spearman atake aswang") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


def test_hindi_pa_is_not_a_cancel() -> None:
    assert parse("hindi pa ako tapos") is None
    assert parse("hindi pa") is None


def test_lone_tapos_connector_is_not_end_turn() -> None:
    assert parse("tapos ano gagawin natin") is None
    assert parse("tapos si Spearman") is None


@pytest.mark.parametrize(
    "text",
    [
        "tapos",
        "tapos na",
        "tapos na ako",
        "sige tapos na",
        "done",
        "end turn",
        "end",
        "next",
    ],
)
def test_end_turn_phrases(text: str) -> None:
    assert parse(text) == Command(CommandKind.END_TURN, None, None)


def test_tapos_connector_between_orders_keeps_the_first_order() -> None:
    assert parse("atake si Spearman, tapos gamot si Albularyo") == Command(
        CommandKind.ATTACK, "u_spear", "e_kapre_1"
    )


def test_end_word_inside_an_order_keeps_the_order() -> None:
    assert parse("Spearman tapos na saksakin ang aswang") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


def test_end_word_with_action_but_no_actor_is_unknown() -> None:
    assert parse("tapos na atake aswang") is None


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("Spearman atake aswang 2", "e_aswang_2"),
        ("Spearman atake aswang dos", "e_aswang_2"),
        ("Spearman atake aswang isa", "e_aswang_1"),
        ("Spearman atake aswang una", "e_aswang_1"),
        ("Spearman atake aswang 1", "e_aswang_1"),
    ],
)
def test_instance_numbers(text: str, target: str) -> None:
    assert parse(text) == Command(CommandKind.ATTACK, "u_spear", target)


@pytest.mark.parametrize(
    ("word", "number"),
    [
        ("isa", 1),
        ("una", 1),
        ("dalawa", 2),
        ("dos", 2),
        ("tatlo", 3),
        ("tres", 3),
        ("apat", 4),
        ("kwatro", 4),
        ("lima", 5),
        ("singko", 5),
    ],
)
def test_number_words_map_to_suffix(word: str, number: int) -> None:
    enemies = tuple(
        GrammarEnemy(f"e_kapre_{n}", "kapre", float(n * 10), 0.0) for n in range(1, 6)
    )
    context = GrammarContext(units=(SPEARMAN,), enemies=enemies)
    assert parse(f"Spearman tira kapre {word}", context) == Command(
        CommandKind.ATTACK, "u_spear", f"e_kapre_{number}"
    )


@pytest.mark.parametrize(
    ("word", "number"), [("uno", 1), ("anim", 6), ("pito", 7), ("walo", 8)]
)
def test_higher_number_words(word: str, number: int) -> None:
    enemies = tuple(
        GrammarEnemy(f"e_kapre_{n}", "kapre", float(n * 10), 0.0) for n in range(1, 9)
    )
    context = GrammarContext(units=(SPEARMAN,), enemies=enemies)
    assert parse(f"Spearman tira kapre {word}", context) == Command(
        CommandKind.ATTACK, "u_spear", f"e_kapre_{number}"
    )


def test_reduplicated_isa_isa_is_not_an_instance_number() -> None:
    enemies = (
        GrammarEnemy("e_aswang_1", "aswang", 10.0, 0.0),
        GrammarEnemy("e_aswang_2", "aswang", 10.0, 9.0),
    )
    context = GrammarContext(units=(SPEARMAN,), enemies=enemies)
    expected = Command(CommandKind.ATTACK, "u_spear", "e_aswang_2")
    assert parse("Spearman atake aswang isa isa", context) == expected
    assert parse("Spearman atake aswang isa-isa", context) == expected
    assert parse("Spearman atake aswang isa", context) == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


ENEMY_FAR_KAPRE = GrammarContext(
    units=(SPEARMAN,),
    enemies=(
        GrammarEnemy("e_aswang_1", "aswang", 12.0, 12.0),
        GrammarEnemy("e_kapre_1", "kapre", 90.0, 90.0),
        GrammarEnemy("e_tikbalang_1", "tikbalang", 80.0, 80.0),
        GrammarEnemy("e_duwende_1", "duwende", 70.0, 70.0),
    ),
)


@pytest.mark.parametrize("fragment", ["pre", "kap", "apr", "ape"])
def test_short_fragments_do_not_match_an_enemy(fragment: str) -> None:
    assert parse(f"Spearman atake {fragment}", ENEMY_FAR_KAPRE) == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


@pytest.mark.parametrize("spelling", ["kapre", "kapr", "kapri", "kaprre"])
def test_kapre_spellings_match(spelling: str) -> None:
    assert parse(f"Spearman atake {spelling}", ENEMY_FAR_KAPRE) == Command(
        CommandKind.ATTACK, "u_spear", "e_kapre_1"
    )


@pytest.mark.parametrize(
    ("spelling", "target"),
    [
        ("tigbalang", "e_tikbalang_1"),
        ("tikbalang", "e_tikbalang_1"),
        ("duende", "e_duwende_1"),
        ("dwende", "e_duwende_1"),
        ("duwende", "e_duwende_1"),
    ],
)
def test_enemy_alias_spellings(spelling: str, target: str) -> None:
    assert parse(f"Spearman atake {spelling}", ENEMY_FAR_KAPRE) == Command(
        CommandKind.ATTACK, "u_spear", target
    )


@pytest.mark.parametrize("word", ["kalaban", "kaaway"])
def test_generic_enemy_words_mean_nearest_enemy(word: str) -> None:
    assert parse(f"Spearman atake {word}", ENEMY_FAR_KAPRE) == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


def test_manang_is_not_an_enemy_word() -> None:
    assert parse("Spearman atake manang", ENEMY_FAR_KAPRE) == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


@pytest.mark.parametrize(
    "word", ["tirahin", "saksak", "atakihin", "sugurin", "palo", "paluin", "hampas"]
)
def test_gentle_attack_variants(word: str) -> None:
    assert word in ATTACK_WORDS
    assert parse(f"Spearman {word} aswang") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


@pytest.mark.parametrize("word", ["gamot", "pagaling", "ayusin", "i-heal", "iheal"])
def test_heal_variants(word: str) -> None:
    assert parse(f"Albularyo {word} Spearman") == Command(
        CommandKind.HEAL, "u_heal", "u_spear"
    )


@pytest.mark.parametrize(
    "word", ["protekta", "bantay", "kalasag", "i-use", "gamitin mo", "iuse"]
)
def test_power_variants(word: str) -> None:
    assert parse(f"Anting-anting {word} kubo") == Command(
        CommandKind.POWER, "u_charm", "u_kubo"
    )


def test_gamot_is_heal_and_gamitin_is_power() -> None:
    assert "gamot" in HEAL_WORDS
    assert "gamot" not in POWER_WORDS
    assert parse("Albularyo gamot Spearman") == Command(
        CommandKind.HEAL, "u_heal", "u_spear"
    )
    assert parse("Albularyo gamitin mo Spearman") == Command(
        CommandKind.POWER, "u_heal", "u_spear"
    )


def test_gamot_is_not_a_class_alias() -> None:
    nameless = GrammarUnit("u_x", "Xyz", "healer", 0.0, 0.0)
    context = GrammarContext(units=(nameless, SPEARMAN), enemies=())
    assert parse("Spearman gamot", context) == Command(
        CommandKind.HEAL, "u_spear", None
    )


@pytest.mark.parametrize(
    ("unit_class", "alias"),
    [
        ("fighter", "mandirigma"),
        ("reach", "sibat"),
        ("ranged", "pana"),
        ("ranged", "archer"),
        ("scout", "scout"),
        ("wall", "pader"),
        ("wall", "wall"),
        ("healer", "manggagamot"),
        ("kubo", "bahay"),
    ],
)
def test_new_class_aliases(unit_class: str, alias: str) -> None:
    unit = GrammarUnit("u_q", "Zzz Nameless", unit_class, 0.0, 0.0)
    context = GrammarContext(units=(unit,), enemies=(ASWANG_1,))
    assert parse(f"{alias} atake aswang", context) == Command(
        CommandKind.ATTACK, "u_q", "e_aswang_1"
    )


def test_short_alias_does_not_match_near_words() -> None:
    unit = GrammarUnit("u_q", "Zzz Nameless", "ranged", 0.0, 0.0)
    context = GrammarContext(units=(unit,), enemies=(ASWANG_1,))
    assert parse("pano atake aswang", context) is None


def test_missing_instance_falls_back_to_nearest_of_type() -> None:
    assert parse("Spearman atake aswang 4") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


def test_nearest_of_type_without_number() -> None:
    context = GrammarContext(
        units=(SPEARMAN,),
        enemies=(
            GrammarEnemy("e_aswang_1", "aswang", 90.0, 90.0),
            GrammarEnemy("e_aswang_2", "aswang", 15.0, 10.0),
        ),
    )
    assert parse("Spearman atake aswang", context) == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_2"
    )


def test_attack_without_target_picks_nearest_enemy() -> None:
    assert parse("Spearman atake") == Command(
        CommandKind.ATTACK, "u_spear", "e_kapre_1"
    )


def test_attack_on_missing_type_falls_back_to_nearest_enemy() -> None:
    assert parse("Spearman atake tikbalang") == Command(
        CommandKind.ATTACK, "u_spear", "e_kapre_1"
    )


def test_attack_with_no_enemies_has_no_target() -> None:
    context = GrammarContext(units=(SPEARMAN,), enemies=())
    assert parse("Spearman atake", context) == Command(
        CommandKind.ATTACK, "u_spear", None
    )


def test_heal_and_power_without_target_are_none() -> None:
    assert parse("Albularyo gamutin") == Command(CommandKind.HEAL, "u_heal", None)
    assert parse("Anting-anting protektahan") == Command(
        CommandKind.POWER, "u_charm", None
    )


def test_kubo_resolves_by_class_alias() -> None:
    renamed = GrammarUnit("u_kubo", "Bahay", "kubo", 0.0, 0.0)
    context = GrammarContext(units=(CHARM, renamed), enemies=())
    assert parse("Anting-anting protektahan kubo", context) == Command(
        CommandKind.POWER, "u_charm", "u_kubo"
    )


def test_class_alias_names_the_actor() -> None:
    renamed = GrammarUnit("u_h", "Nanay Rosa", "healer", 0.0, 0.0)
    context = GrammarContext(units=(renamed, SPEARMAN), enemies=())
    assert parse("albularyo gamutin Spearman", context) == Command(
        CommandKind.HEAL, "u_h", "u_spear"
    )


@pytest.mark.parametrize(
    "text",
    [
        "Spearmin saksakin ang aswang",
        "SPEARMAN, SAKSAKIN ANG ASWANG",
        "Spearmen saksakin ang aswan",
        "spearman saksakin ang asuwang",
    ],
)
def test_fuzzy_misspellings_of_unit_and_enemy(text: str) -> None:
    assert parse(text) == Command(CommandKind.ATTACK, "u_spear", "e_aswang_1")


def test_fuzzy_misspelled_trigger_word() -> None:
    assert parse("Spearman saksakn ang aswang") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


def test_accents_and_punctuation_are_normalized() -> None:
    assert normalize("  Spéarman,  SAKSAKÍN!!  ") == "spearman saksakin"
    assert parse("Spéarman… saksakín ang áswang?!") == Command(
        CommandKind.ATTACK, "u_spear", "e_aswang_1"
    )


def test_actor_is_the_earliest_unit_in_the_sentence() -> None:
    assert parse("Albularyo gamutin Spearman") == Command(
        CommandKind.HEAL, "u_heal", "u_spear"
    )
    assert parse("Spearman Albularyo gamutin") == Command(
        CommandKind.HEAL, "u_spear", "u_heal"
    )


def test_unit_without_action_word_is_unknown() -> None:
    assert parse("Spearman aswang") is None


def test_action_without_unit_is_unknown() -> None:
    assert parse("saksakin ang aswang") is None


@pytest.mark.parametrize(
    "text", ["", "   ", "...", "kumusta ka na", "ang ganda ng gabi", "12345"]
)
def test_unknown_and_empty_text(text: str) -> None:
    assert parse(text) is None


def test_non_string_input_is_rejected() -> None:
    assert parse_command(None, CONTEXT) is None  # type: ignore[arg-type]


def test_untrusted_long_text_is_bounded() -> None:
    text = "blah " * 20_000 + "Spearman atake aswang"
    assert parse(text) is None


def test_untrusted_text_cannot_inject_ids() -> None:
    command = parse("Spearman atake e_aswang_2; DROP TABLE units")
    assert command is not None
    assert command.target_id in {"e_aswang_1", "e_aswang_2", "e_kapre_1"}


def test_empty_context_gives_end_and_cancel_only() -> None:
    empty = GrammarContext(units=(), enemies=())
    assert parse("tapos", empty) == Command(CommandKind.END_TURN, None, None)
    assert parse("hindi", empty) == Command(CommandKind.CANCEL, None, None)
    assert parse("Spearman atake aswang", empty) is None


def test_parse_is_fast() -> None:
    texts = [
        "Spearman, saksakin ang aswang dos!",
        "Anting-anting, protektahan ang kubo!",
        "Albularyo, gamutin si Spearman",
        "Tapos na",
        "kumusta ka na ngayong gabi",
    ]
    durations: list[float] = []
    for i in range(50):
        started = time.perf_counter()
        parse(texts[i % len(texts)])
        durations.append((time.perf_counter() - started) * 1000)
    assert statistics.median(durations) < 20.0


def test_descriptive_phrase_does_not_fuzzy_match_a_unit() -> None:
    context = GrammarContext(
        units=(
            GrammarUnit("u_albu", "Albularyo", "healer", 10, 10),
            GrammarUnit("u_spear", "Spearman", "reach", 20, 20),
            GrammarUnit("u_kubo", "Kubo", "kubo", 0, 0),
        ),
        enemies=(GrammarEnemy("e_aswang_1", "aswang", 30, 30),),
    )
    assert parse_command("pre, yung may susi, gamutin mo yung kubo", context) is None
