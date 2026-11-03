import random

import numpy as np
import pytest

from vision.returning import (
    AMBIGUITY_MARGIN,
    MATCH_THRESHOLD,
    MIN_HISTOGRAM_SIMILARITY,
    StoredSignature,
    find_returning,
    match_returning,
    returning_score,
    smooth_histogram,
)
from vision.signature import HIST_BINS, Signature, SignatureError

SIZE = int(np.prod(HIST_BINS))


def histogram_at(bins: dict[int, float]) -> tuple[float, ...]:
    values = [0.0] * SIZE
    for index, weight in bins.items():
        values[index % SIZE] += weight
    total = sum(values)
    return tuple(v / total for v in values)


def random_histogram(rng: random.Random, spread: int = 6) -> tuple[float, ...]:
    picks = {rng.randrange(SIZE): rng.uniform(0.2, 1.0) for _ in range(spread)}
    return histogram_at(picks)


def random_signature(rng: random.Random, label: str = "x") -> Signature:
    return Signature(
        label,
        random_histogram(rng),
        rng.uniform(1.0, 80.0),
        rng.uniform(0.2, 5.0),
    )


def distinct_signatures(count: int) -> list[Signature]:
    sigs: list[Signature] = []
    for index in range(count):
        base = (index * 11) % SIZE
        bins = {base: 1.0, (base + 1) % SIZE: 0.5}
        sigs.append(
            Signature(f"s{index}", histogram_at(bins), 10.0 + 9.0 * index, 1.0 + index)
        )
    return sigs


def store_of(sigs: list[Signature]) -> list[StoredSignature]:
    return [StoredSignature(f"u_{i}", s) for i, s in enumerate(sigs)]


def test_no_stored_units_never_match() -> None:
    rng = random.Random(1)
    for _ in range(200):
        candidate = random_signature(rng)
        assert find_returning([], candidate) is None
        assert match_returning([], candidate) is None
        assert find_returning((), candidate) is None


def test_no_match_for_unusable_candidates() -> None:
    stored = store_of(distinct_signatures(4))
    zero = Signature("z", tuple([0.0] * SIZE), 10.0, 1.0)
    short = Signature("s", (1.0, 0.0), 10.0, 1.0)
    empty = Signature("e", (), 10.0, 1.0)
    for candidate in (zero, short, empty):
        assert find_returning(stored, candidate) is None
        assert match_returning(stored, candidate) is None


def test_unusable_stored_entries_are_skipped_not_fatal() -> None:
    sigs = distinct_signatures(3)
    junk = [
        StoredSignature("bad_zero", Signature("z", tuple([0.0] * SIZE), 5.0, 1.0)),
        StoredSignature("bad_short", Signature("s", (1.0,), 5.0, 1.0)),
    ]
    stored = [*junk, *store_of(sigs)]
    found = find_returning(stored, sigs[1])
    assert found is not None
    assert found.unit_id == "u_1"
    assert match_returning(junk, sigs[0]) is None


def test_returning_score_raises_signature_error_on_bad_histograms() -> None:
    good = distinct_signatures(1)[0]
    zero = Signature("z", tuple([0.0] * SIZE), 5.0, 1.0)
    short = Signature("s", (1.0,), 5.0, 1.0)
    for bad in (zero, short):
        with pytest.raises(SignatureError):
            returning_score(good, bad)
        with pytest.raises(SignatureError):
            returning_score(bad, good)


def test_smooth_histogram_is_a_distribution() -> None:
    rng = random.Random(2)
    for _ in range(100):
        smoothed = smooth_histogram(random_histogram(rng))
        assert len(smoothed) == SIZE
        assert all(v >= 0.0 for v in smoothed)
        assert sum(smoothed) == pytest.approx(1.0)
        again = smooth_histogram(smoothed)
        assert sum(again) == pytest.approx(1.0)


def test_smooth_histogram_rejects_wrong_size_and_empty() -> None:
    with pytest.raises(SignatureError):
        smooth_histogram((1.0,) * (SIZE - 1))
    with pytest.raises(SignatureError):
        smooth_histogram(tuple([0.0] * SIZE))


def test_score_is_bounded_and_symmetric() -> None:
    rng = random.Random(3)
    for _ in range(200):
        a = random_signature(rng)
        b = random_signature(rng)
        score, similarity = returning_score(a, b)
        assert -1e-6 <= similarity <= 1.0 + 1e-6
        assert -1e-6 <= score <= 1.0 + 1e-6
        other, _ = returning_score(b, a)
        assert score == pytest.approx(other, abs=1e-6)


def test_identical_signature_scores_one() -> None:
    rng = random.Random(4)
    for _ in range(100):
        sig = random_signature(rng)
        score, similarity = returning_score(sig, sig)
        assert similarity == pytest.approx(1.0, abs=1e-3)
        assert score == pytest.approx(1.0, abs=1e-3)


def test_zero_area_and_aspect_do_not_crash() -> None:
    sig = Signature("flat", histogram_at({0: 1.0}), 0.0, 0.0)
    score, _ = returning_score(sig, sig)
    assert 0.0 <= score <= 1.0
    find_returning(store_of([sig]), sig)


def test_stored_object_matches_itself_among_distinct_ones() -> None:
    sigs = distinct_signatures(8)
    stored = store_of(sigs)
    for index, sig in enumerate(sigs):
        found = find_returning(stored, sig)
        assert found is not None
        assert found.unit_id == f"u_{index}"
        assert found.score >= MATCH_THRESHOLD
        assert found.score - found.runner_up >= AMBIGUITY_MARGIN
        assert match_returning(stored, sig) == f"u_{index}"


def test_result_is_independent_of_stored_order() -> None:
    shuffler = random.Random(5)
    matched = 0
    for seed in range(150):
        local = random.Random(seed)
        sigs = [random_signature(local) for _ in range(local.randint(1, 7))]
        stored = store_of(sigs)
        if local.random() < 0.7:
            base = local.choice(sigs)
            candidate = Signature(
                base.label,
                base.histogram,
                base.area_cm2 * local.uniform(0.9, 1.1),
                base.aspect * local.uniform(0.9, 1.1),
            )
        else:
            candidate = random_signature(local)
        reference = find_returning(stored, candidate)
        for _ in range(4):
            shuffled = list(stored)
            shuffler.shuffle(shuffled)
            again = find_returning(shuffled, candidate)
            if reference is None:
                assert again is None
            else:
                assert again is not None
                assert again.unit_id == reference.unit_id
                assert again.score == pytest.approx(reference.score)
                assert again.runner_up == pytest.approx(reference.runner_up)
        matched += reference is not None
    assert matched > 20


def test_any_match_meets_the_documented_thresholds() -> None:
    for seed in range(300):
        rng = random.Random(seed)
        stored = store_of([random_signature(rng) for _ in range(rng.randint(1, 6))])
        candidate = random_signature(rng)
        found = find_returning(stored, candidate)
        if found is None:
            assert match_returning(stored, candidate) is None
            continue
        assert found.score >= MATCH_THRESHOLD
        assert found.score - found.runner_up >= AMBIGUITY_MARGIN
        assert found.runner_up >= 0.0
        winner = next(s.signature for s in stored if s.unit_id == found.unit_id)
        score, similarity = returning_score(winner, candidate)
        assert similarity >= MIN_HISTOGRAM_SIMILARITY
        assert score == pytest.approx(found.score)


def test_duplicate_twins_are_ambiguous_in_every_order() -> None:
    twin = distinct_signatures(1)[0]
    stored = [StoredSignature("u_a", twin), StoredSignature("u_b", twin)]
    assert find_returning(stored, twin) is None
    assert find_returning(list(reversed(stored)), twin) is None


def test_dissimilar_colours_never_match() -> None:
    sigs = distinct_signatures(2)
    candidate = Signature(
        "far", histogram_at({SIZE - 1: 1.0}), sigs[0].area_cm2, sigs[0].aspect
    )
    assert find_returning(store_of(sigs[:1]), candidate) is None


def test_inputs_are_not_mutated() -> None:
    sigs = distinct_signatures(5)
    stored = store_of(sigs)
    snapshot = list(stored)
    find_returning(stored, sigs[2])
    assert stored == snapshot
