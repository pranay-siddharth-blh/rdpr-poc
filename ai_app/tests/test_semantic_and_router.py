import json
from pathlib import Path

import pytest

from app.semantic_layer import definitional_term, extract_entities, load_semantic_layer, unknown_names


def test_layer_is_complete_and_documented():
    layer = load_semantic_layer()
    assert len(layer["tables"]) == 31 and len(layer["entities"]["gps"]) == 6099
    for t in layer["tables"].values():
        assert t["columns"] and all(c["doc"] for c in t["columns"].values())
    # every metric points at a documented table
    for m in layer["metrics"]:
        for v in m["variants"].values():
            assert v["table"] in layer["tables"]


def test_period_and_place_extraction():
    e = extract_entities("What was the total collection in Mysuru zilla in FY 2024-25?")
    assert e["zillas"] == ["Mysuru"] and e["metrics"] == ["total_collection"]
    assert e["periods"][0]["value"] == "2024-25"
    e = extract_entities("collection in March 2026 for Hassan")
    assert e["periods"][0] == {"kind": "month", "value": "MAR-2026", "fy": "2025-26", "label": "March 2026", "relative": False}
    e = extract_entities("collection last year")
    assert e["periods"][0]["value"] == "2025-26" and e["periods"][0]["relative"]
    assert extract_entities("collection in 2019-20")["periods"][0]["kind"] == "out_of_range"


def test_zilla_taluk_name_clash_defaults_to_zilla_with_note():
    e = extract_entities("collection in Bagalkot")
    assert e["zillas"] == ["Bagalkot"] and e["place_notes"]
    assert extract_entities("collection in Bagalkot taluk")["taluks"] == ["Bagalkot"]


def test_gp_resolution():
    e = extract_entities("collection of Siddapura GP in Madhugiri taluk in 2024-25")
    assert e["gps"][0]["id"] == "G4938"
    e = extract_entities("collection of Siddapura GP in 2024-25")
    assert len(e["gps"][0]["candidates"]) == 9
    e = extract_entities("collection of Siddapura GP in Sirsi taluk")
    assert e["gps"][0]["not_found_in"] == "Sirsi taluk"


def test_generic_staff_phrase_is_not_a_filter():
    assert not extract_entities("how many active GP staff are there in Badami taluk").get("staff_types")
    assert extract_entities("staff of type GP Staff in Badami taluk").get("staff_types") == ["GP Staff"]


def test_metric_priority_and_unknown_names():
    assert extract_entities("collection percentage in Hassan")["metrics"] == ["collection_pct"]
    assert extract_entities("staff pending at EO in Haveri")["metrics"] == ["staff_pending_at_eo"]
    assert unknown_names("balance of Xyzpur taluk in 2024-25") == ["Xyzpur"]
    assert unknown_names("Which five zillas have the lowest collection?") == []
    assert definitional_term("What is DCB?") == "DCB"


@pytest.mark.parametrize("question", ["collection percent Mandya", "What is the collection per cent of Mandya zilla in 2024-25?",
                                      "percent collected in Mandya", "Mandya collection pct"])
def test_collection_percent_typed_is_the_percentage(question):
    assert extract_entities(question)["metrics"] == ["collection_pct"]


def test_collection_percent_typed_answers_the_percentage(ask):
    r = ask("collection percent Mandya")
    assert r.answerable and "%" in r.answer.split("\n")[0]
