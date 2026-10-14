"""Retained independent elicitation algorithms; lifecycle tests use the replacement owners."""

from __future__ import annotations

from typing import Any


def test_translate_string_field_is_freeform() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema({"type": "object", "properties": {"name": {"type": "string"}}})
    assert t.degrade is None
    assert t.kind == "freeform"
    assert t.fields[0]["name"] == "name"


def test_translate_boolean_field_is_confirmation() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema({"type": "object", "properties": {"ok": {"type": "boolean"}}})
    assert t.kind == "confirmation"


def test_translate_enum_field_is_choice_with_options() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {"size": {"type": "string", "enum": ["s", "m", "l"]}},
        }
    )
    assert t.kind == "choice"
    assert [o.value for o in t.options] == ["s", "m", "l"]


def test_translate_number_and_defaults_are_carried() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 3},
                "ratio": {"type": "number"},
            },
        }
    )
    assert t.kind == "freeform"  # multi-field renders from fields descriptor
    by_name = {f["name"]: f for f in t.fields}
    assert by_name["count"]["default"] == 3
    assert by_name["ratio"]["type"] == "number"


def test_translate_non_object_schema_degrades() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema({"type": "string"})
    assert t.degrade == "elicitation_schema_not_object"


def test_translate_nested_schema_degrades_not_flat() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {"nested": {"type": "object", "properties": {}}},
        }
    )
    assert t.degrade == "elicitation_schema_not_flat"


def test_translate_unsupported_field_type_degrades() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema({"type": "object", "properties": {"x": {"type": "null"}}})
    assert t.degrade == "elicitation_unsupported_field_type"


def test_url_trust_rejects_untrusted_origin() -> None:
    from clio_agent.gact.elicitation_schema import check_url_trust

    reason = check_url_trust("https://evil.example/oauth", ["https://trusted.example"])
    assert reason == "elicitation_url_untrusted_origin"


def test_url_trust_accepts_listed_origin() -> None:
    from clio_agent.gact.elicitation_schema import check_url_trust

    assert check_url_trust("https://trusted.example/oauth", ["https://trusted.example"]) is None


def test_url_trust_rejects_insecure_scheme() -> None:
    from clio_agent.gact.elicitation_schema import check_url_trust

    reason = check_url_trust("http://trusted.example/x", ["https://trusted.example"])
    assert reason == "elicitation_url_insecure_scheme"


def test_punycode_warning_helper_detects_ace_labels() -> None:
    from clio_agent.gact.elicitation_schema import punycode_warning

    warning, host, raw = punycode_warning("https://plain.example/x")
    assert warning is False
    assert host == "plain.example"
    assert raw == "plain.example"

    warning, host, raw = punycode_warning("https://xn--nxasmq6b.example/x")
    assert warning is True
    # Computed via the SAME stdlib codec this helper uses, not hand-transcribed
    # (a real punycode-encoded Greek IDN label) — avoids a mistyped Unicode literal.
    assert host == "xn--nxasmq6b".encode("ascii").decode("idna") + ".example"
    assert host != "xn--nxasmq6b.example"
    # The raw ACE host is carried ALONGSIDE the decoded display host (Opus
    # review, C1-S4) -- callers must never lose access to the wire form.
    assert raw == "xn--nxasmq6b.example"


def test_punycode_warning_falls_back_to_raw_host_on_bad_decode() -> None:
    """An undecodable ACE label never raises -- it degrades to the raw host."""

    from clio_agent.gact.elicitation_schema import punycode_warning

    warning, host, raw = punycode_warning("https://xn--/x")
    assert warning is True
    assert host  # some non-empty fallback, never a crash
    assert raw == host  # the fallback IS the raw host in this branch


def test_punycode_warning_detects_raw_unicode_homograph_host() -> None:
    """The textbook MUST case (Opus review, C1-S4): a RAW-UNICODE homograph
    host with NO ``xn--`` prefix anywhere -- the original ACE-only check
    passed this with NO warning, which is exactly the risk F3 exists to flag.

    ``аpple.com`` uses Cyrillic CYRILLIC SMALL LETTER A (U+0430) in place
    of Latin "a" -- a real, well-known homograph of ``apple.com``.
    """

    from clio_agent.gact.elicitation_schema import punycode_warning

    homograph_host = "аpple.com"
    assert not homograph_host.isascii()  # sanity: genuinely non-ASCII, not a typo
    warning, host, raw = punycode_warning(f"https://{homograph_host}/oauth")
    assert warning is True
    # Nothing to ACE-decode -- the raw Unicode host IS the display host.
    assert host == homograph_host
    assert raw == homograph_host


def test_default_answer_metadata_helper_skips_none_defaults() -> None:
    from clio_agent.gact.elicitation_schema import default_answer_metadata, translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {
                "a": {"type": "string", "default": "x"},
                "b": {"type": "integer"},
                "c": {"type": "boolean", "default": False},
            },
        }
    )
    assert default_answer_metadata(t.fields) == {"a": "x", "c": False}


def test_translate_multi_select_enum_field_is_multi_choice() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {
                "colors": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["r", "g", "b"],
                        "enumNames": ["Red", "Green", "Blue"],
                    },
                    "uniqueItems": True,
                },
            },
        }
    )
    assert t.degrade is None
    assert t.kind == "multi_choice"
    assert [o.value for o in t.options] == ["r", "g", "b"]
    assert [o.label for o in t.options] == ["Red", "Green", "Blue"]
    field = t.fields[0]
    assert field["multi"] is True
    assert field["enum"] == ["r", "g", "b"]
    assert field["item_type"] == "string"


def test_translate_multi_select_enum_inside_a_multi_field_form_stays_freeform() -> None:
    """A multi-select field alongside another field renders from ``fields`` (freeform),
    exactly like today's single-vs-multi-field kind selection for scalar enums."""

    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string", "enum": ["x", "y"]}},
            },
        }
    )
    assert t.degrade is None
    assert t.kind == "freeform"
    by_name = {f["name"]: f for f in t.fields}
    assert by_name["tags"]["multi"] is True
    assert by_name["name"]["multi"] is False


def test_translate_unconstrained_array_still_degrades_not_flat() -> None:
    """A bare, non-enum array stays unsupported -- only the flat multi-select-enum
    shape is newly admitted; regression pin for the pre-existing array rejection."""

    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema(
        {"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}}
    )
    assert t.degrade == "elicitation_schema_not_flat"


def test_translate_nested_array_of_objects_still_degrades_not_flat() -> None:
    from clio_agent.gact.elicitation_schema import translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {
                "rows": {"type": "array", "items": {"type": "object", "properties": {}}},
            },
        }
    )
    assert t.degrade == "elicitation_schema_not_flat"


def test_multi_select_answer_builds_a_list_content_value() -> None:
    from clio_agent.gact.elicitation_schema import build_form_content, translate_form_schema

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {
                "colors": {"type": "array", "items": {"type": "string", "enum": ["r", "g", "b"]}}
            },
        }
    )
    content = build_form_content(
        t.fields, selected_options=["r", "b"], answer="", answer_metadata={}
    )
    assert content == {"colors": ["r", "b"]}


def test_multi_select_answer_validates_membership() -> None:
    from clio_agent.gact.elicitation_schema import (
        translate_form_schema,
        validate_elicitation_answer,
    )
    from clio_agent.gact.types import UserQuestion

    t = translate_form_schema(
        {
            "type": "object",
            "properties": {
                "colors": {"type": "array", "items": {"type": "string", "enum": ["r", "g", "b"]}}
            },
        }
    )
    row = UserQuestion(
        id="q1",
        session_id="s1",
        prompt="pick",
        kind=t.kind,  # type: ignore[arg-type]
        options=t.options,
        created_at="",
        updated_at="",
        source="mcp_elicitation",
        metadata={
            "elicitation": {
                "mode": "form",
                "fields": t.fields,
                "additional_properties": True,
            }
        },
    )
    ok = validate_elicitation_answer(
        row, selected_options=["r", "g"], answer="", answer_metadata={}
    )
    assert ok is None

    bad = validate_elicitation_answer(
        row, selected_options=[], answer="", answer_metadata={"colors": ["r", "purple"]}
    )
    assert bad is not None and "colors" in bad


def _bounded_multi_select_translation() -> Any:
    """The reviewer's exact measured case (Opus review, C1-S4): a 3-enum
    multi-select with ``minItems: 1`` / ``maxItems: 2``."""

    from clio_agent.gact.elicitation_schema import translate_form_schema

    return translate_form_schema(
        {
            "type": "object",
            "properties": {
                "colors": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["r", "g", "b"]},
                    "minItems": 1,
                    "maxItems": 2,
                },
            },
        }
    )


def test_translate_multi_select_carries_min_max_items_onto_the_field_descriptor() -> None:
    """minItems/maxItems must SURVIVE translation onto the field descriptor
    (Opus review, C1-S4 B4): before this fix a repo-wide grep found zero
    hits -- they were silently dropped."""

    t = _bounded_multi_select_translation()
    assert t.degrade is None
    field = t.fields[0]
    assert field["min_items"] == 1
    assert field["max_items"] == 2


def test_multi_select_answer_rejects_more_selections_than_max_items() -> None:
    """maxItems:2 over a 3-enum: 3 selections must reject (Opus review,
    C1-S4 B4 -- the reviewer's exact measured case). Before the fix this
    silently accepted."""

    from clio_agent.gact.elicitation_schema import validate_elicitation_answer
    from clio_agent.gact.types import UserQuestion

    t = _bounded_multi_select_translation()
    row = UserQuestion(
        id="q1",
        session_id="s1",
        prompt="pick",
        kind=t.kind,  # type: ignore[arg-type]
        options=t.options,
        created_at="",
        updated_at="",
        source="mcp_elicitation",
        metadata={
            "elicitation": {"mode": "form", "fields": t.fields, "additional_properties": True}
        },
    )
    ok = validate_elicitation_answer(
        row, selected_options=["r", "g"], answer="", answer_metadata={}
    )
    assert ok is None, "2 selections is within maxItems:2 -- must accept"

    bad = validate_elicitation_answer(
        row, selected_options=["r", "g", "b"], answer="", answer_metadata={}
    )
    assert bad is not None and "colors" in bad and "2" in bad


def test_multi_select_answer_rejects_empty_selection_via_min_items_even_when_not_required() -> None:
    """minItems:1 rejects an EMPTY selection even though the field itself is
    not marked ``required`` in the JSON-Schema sense (Opus review, C1-S4 B4
    -- the reviewer's exact measured case). ``required`` governs whether the
    field may be ABSENT; a PRESENT-but-empty selection is a different
    question minItems answers on its own. Before the fix an empty list
    satisfied ``all(...)`` over zero elements and silently passed.
    """

    from clio_agent.gact.elicitation_schema import validate_elicitation_answer
    from clio_agent.gact.types import UserQuestion

    t = _bounded_multi_select_translation()
    assert t.fields[0]["required"] is False, "sanity: this field is NOT required"
    row = UserQuestion(
        id="q1",
        session_id="s1",
        prompt="pick",
        kind=t.kind,  # type: ignore[arg-type]
        options=t.options,
        created_at="",
        updated_at="",
        source="mcp_elicitation",
        metadata={
            "elicitation": {"mode": "form", "fields": t.fields, "additional_properties": True}
        },
    )
    # An explicit, PRESENT empty selection (not an absent field -- see
    # build_form_content precedence: an explicit answer_metadata entry wins).
    bad = validate_elicitation_answer(
        row, selected_options=[], answer="", answer_metadata={"colors": []}
    )
    assert bad is not None and "colors" in bad and "1" in bad
    # An ABSENT field is still fine -- required=False permits omission entirely.
    ok = validate_elicitation_answer(row, selected_options=[], answer="", answer_metadata={})
    assert ok is None


def test_validate_elicitation_answer_unit_rules() -> None:
    """Unit: required / enum / integer / additionalProperties validation rules."""

    from clio_agent.gact.elicitation_schema import validate_elicitation_answer
    from clio_agent.gact.types import UserQuestion

    def _q(fields: list[dict[str, Any]], *, additional: bool = True) -> UserQuestion:
        return UserQuestion(
            id="q",
            session_id="s",
            prompt="p",
            created_at="t",
            updated_at="t",
            source="mcp_elicitation",
            metadata={
                "elicitation": {
                    "mode": "form",
                    "fields": fields,
                    "additional_properties": additional,
                }
            },
        )

    # required missing
    q = _q([{"name": "count", "type": "integer", "required": True}])
    assert (
        validate_elicitation_answer(q, selected_options=[], answer="", answer_metadata={})
        is not None
    )
    # invalid integer
    assert (
        validate_elicitation_answer(
            q, selected_options=[], answer="", answer_metadata={"count": "x"}
        )
        is not None
    )
    # enum violation
    qe = _q([{"name": "c", "type": "string", "enum": ["a", "b"]}])
    assert (
        validate_elicitation_answer(qe, selected_options=["z"], answer="", answer_metadata={})
        is not None
    )
    # additionalProperties=False rejects extras
    qa = _q([{"name": "c", "type": "string"}], additional=False)
    assert (
        validate_elicitation_answer(
            qa, selected_options=[], answer="", answer_metadata={"c": "x", "extra": "1"}
        )
        is not None
    )
    # valid
    assert (
        validate_elicitation_answer(qe, selected_options=["a"], answer="", answer_metadata={})
        is None
    )


def test_scalar_validation_rejects_invalid_answers() -> None:
    """Post-coercion scalar rules reject the probe's invalid values (finding 7)."""

    from clio_agent.gact.elicitation_schema import validate_elicitation_answer
    from clio_agent.gact.types import UserQuestion

    def _q(fields: list[dict[str, Any]]) -> UserQuestion:
        return UserQuestion(
            id="q",
            session_id="s",
            prompt="p",
            created_at="t",
            updated_at="t",
            source="mcp_elicitation",
            metadata={"elicitation": {"mode": "form", "fields": fields}},
        )

    def _bad(field: dict[str, Any], value: Any) -> bool:
        return (
            validate_elicitation_answer(
                _q([field]), selected_options=[], answer="", answer_metadata={field["name"]: value}
            )
            is not None
        )

    intf = {"name": "n", "type": "integer"}
    numf = {"name": "n", "type": "number"}
    boolf = {"name": "n", "type": "boolean"}
    strf = {"name": "n", "type": "string"}
    empty_enum = {"name": "n", "type": "string", "enum": []}
    str_enum = {"name": "n", "type": "string", "enum": ["1"]}  # string enum
    int_enum = {"name": "n", "type": "integer", "enum": [1]}  # typed int enum

    assert _bad(intf, 1.5)  # non-integral float
    assert _bad(intf, True)  # bool is not an integer
    assert _bad(intf, "1.5")  # non-integral string
    assert _bad(numf, False)  # bool is not a number
    assert _bad(numf, float("inf"))  # non-finite
    assert _bad(boolf, "maybe")  # unrecognised bool string (never coerce-to-false)
    assert _bad(empty_enum, "anything")  # empty enum admits nothing
    assert _bad(strf, 7)  # wrong-typed value for a string field
    assert _bad(str_enum, 1)  # cross-type enum: int 1 is NOT the string '1'

    # ...and the valid coercions still pass
    def _ok(field: dict[str, Any], value: Any) -> bool:
        return (
            validate_elicitation_answer(
                _q([field]), selected_options=[], answer="", answer_metadata={field["name"]: value}
            )
            is None
        )

    assert _ok(intf, "5") and _ok(intf, 5)
    assert _ok(numf, "1.5") and _ok(numf, 2)
    assert _ok(boolf, "true") and _ok(boolf, False)
    assert _ok(strf, "hello")  # correct-typed string
    assert _ok(str_enum, "1")  # string enum, string member
    assert _ok(int_enum, "1")  # int enum, "1" coerces to int 1 -> member
