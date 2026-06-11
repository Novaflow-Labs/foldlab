"""Tests for app.services.variants (Agent C / Phase 1C).

The `claude` strategy is exercised with a monkeypatched Anthropic client — it is
never called against the real API.
"""
from __future__ import annotations

import pytest

from app.services import variants as v

BASE = "ACDEFGHIK"  # 9 residues, 1-indexed: A1 C2 D3 E4 F5 G6 H7 I8 K9


# --- positions_subs --------------------------------------------------------
def test_positions_subs_count_and_labels():
    out = v.generate(
        BASE,
        "positions_subs",
        {"positions": [1, 2], "substitutions": ["A", "Y"]},
    )
    labels = {x.label for x in out}
    # pos1 (A): "A" == WT excluded, "Y" -> A1Y. pos2 (C): "A" -> C2A, "Y" -> C2Y.
    assert labels == {"A1Y", "C2A", "C2Y"}
    assert len(out) == 3
    by_label = {x.label: x for x in out}
    assert by_label["A1Y"].residues == "YCDEFGHIK"
    assert by_label["A1Y"].mutations == ["A1Y"]


def test_positions_subs_excludes_wt_at_same_residue():
    out = v.generate(BASE, "positions_subs", {"positions": [1], "substitutions": ["A"]})
    # A at pos 1 == base, so nothing produced.
    assert out == []


def test_positions_subs_include_wt():
    out = v.generate(
        BASE,
        "positions_subs",
        {"positions": [2], "substitutions": ["Y"], "include_wt": True},
    )
    labels = [x.label for x in out]
    assert "WT" in labels
    assert "C2Y" in labels
    wt = next(x for x in out if x.label == "WT")
    assert wt.residues == BASE
    assert wt.mutations == []


def test_positions_subs_max_variants():
    out = v.generate(
        BASE,
        "positions_subs",
        {"positions": [2, 3, 4], "substitutions": ["Y", "W"], "max_variants": 2},
    )
    assert len(out) == 2


def test_positions_subs_invalid_substitution_raises():
    with pytest.raises(ValueError):
        v.generate(BASE, "positions_subs", {"positions": [1], "substitutions": ["Z"]})


def test_positions_subs_out_of_range_raises():
    with pytest.raises(ValueError):
        v.generate(BASE, "positions_subs", {"positions": [99], "substitutions": ["Y"]})


def test_positions_subs_missing_params_raises():
    with pytest.raises(ValueError):
        v.generate(BASE, "positions_subs", {"positions": [1]})


# --- alanine_scan ----------------------------------------------------------
def test_alanine_scan_default_skips_existing_alanine():
    out = v.generate(BASE, "alanine_scan", {})
    labels = [x.label for x in out]
    assert labels[0] == "WT"
    # A1 is already Alanine -> no A1A entry.
    assert "A1A" not in labels
    # Every non-A position becomes <wt><pos>A.
    assert "C2A" in labels
    assert "K9A" in labels
    # 8 non-A residues + WT.
    assert len(out) == 9


def test_alanine_scan_specific_positions():
    out = v.generate(BASE, "alanine_scan", {"positions": [2, 3]})
    labels = [x.label for x in out]
    assert labels == ["WT", "C2A", "D3A"]
    by_label = {x.label: x for x in out}
    assert by_label["C2A"].residues == "AADEFGHIK"
    assert by_label["C2A"].mutations == ["C2A"]


# --- pasted ----------------------------------------------------------------
def test_pasted_sequences():
    out = v.generate(BASE, "pasted", {"sequences": ["acdef", "GGGG"]})
    assert [x.label for x in out] == ["variant_1", "variant_2"]
    assert out[0].residues == "ACDEF"  # cleaned/uppercased
    assert out[1].residues == "GGGG"
    assert out[0].mutations == []


def test_pasted_labeled():
    out = v.generate(
        BASE,
        "pasted",
        {"labeled": [{"label": "mutant_x", "residues": "acd ef"}]},
    )
    assert len(out) == 1
    assert out[0].label == "mutant_x"
    assert out[0].residues == "ACDEF"


def test_pasted_invalid_residues_raises():
    with pytest.raises(ValueError):
        v.generate(BASE, "pasted", {"sequences": ["ACXEF"]})


def test_pasted_requires_input():
    with pytest.raises(ValueError):
        v.generate(BASE, "pasted", {})


# --- dedupe + cap + validation ---------------------------------------------
def test_dedupe_by_residues():
    # Two labeled entries with identical residues -> deduped to one.
    out = v.generate(
        BASE,
        "pasted",
        {
            "labeled": [
                {"label": "a", "residues": "ACDEF"},
                {"label": "b", "residues": "acdef"},  # same after cleaning
            ]
        },
    )
    assert len(out) == 1


def test_cap_at_max_variants(monkeypatch):
    monkeypatch.setattr(v, "MAX_VARIANTS", 2)
    out = v.generate(BASE, "pasted", {"sequences": ["AAAA", "CCCC", "DDDD", "EEEE"]})
    assert len(out) == 2


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        v.generate(BASE, "nonsense", {})


def test_invalid_base_raises():
    with pytest.raises(ValueError):
        v.generate("ACXEF", "alanine_scan", {})


# --- claude strategy (monkeypatched client, never hits the real API) -------
class _FakeMessages:
    def __init__(self, parsed):
        self._parsed = parsed
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)

        class _Resp:
            parsed_output = self._parsed

        return _Resp()


class _FakeClient:
    def __init__(self, *, api_key, parsed):
        self.api_key = api_key
        self.messages = _FakeMessages(parsed)


def _patch_anthropic(monkeypatch, parsed, api_key="sk-test"):
    import anthropic

    holder = {}

    def _factory(*, api_key):
        client = _FakeClient(api_key=api_key, parsed=parsed)
        holder["client"] = client
        return client

    monkeypatch.setattr(anthropic, "Anthropic", _factory)
    monkeypatch.setattr(v.get_settings(), "anthropic_api_key", api_key, raising=False)
    return holder


def test_claude_requires_api_key(monkeypatch):
    monkeypatch.setattr(v.get_settings(), "anthropic_api_key", "", raising=False)
    with pytest.raises(ValueError):
        v.generate(BASE, "claude", {"n": 2})


def test_claude_applies_and_validates_mutations(monkeypatch):
    parsed = v._ClaudeVariants(
        variants=[
            v._ProposedVariant(
                label="stabilize",
                mutations=[v._Mutation(pos=2, from_aa="C", to_aa="S")],
            ),
            # Invalid: from_aa mismatch (pos 3 is D, not Q) -> skipped.
            v._ProposedVariant(
                label="bad",
                mutations=[v._Mutation(pos=3, from_aa="Q", to_aa="A")],
            ),
        ]
    )
    _patch_anthropic(monkeypatch, parsed)
    out = v.generate(BASE, "claude", {"n": 2})
    assert len(out) == 1
    assert out[0].label == "stabilize"
    assert out[0].mutations == ["C2S"]
    assert out[0].residues == "ASDEFGHIK"


def test_claude_invalid_n_raises(monkeypatch):
    _patch_anthropic(monkeypatch, v._ClaudeVariants(variants=[]))
    with pytest.raises(ValueError):
        v.generate(BASE, "claude", {"n": 0})
