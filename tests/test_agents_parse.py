from docsearch.services.agents import _parse_json, _parse_query_list


def test_parse_json_extracts_object_from_prose():
    raw = 'Verdict follows:\n{"faithful": false, "score": 0.2, "issues": ["unsupported"]}\nThanks'
    parsed = _parse_json(raw)
    assert parsed["faithful"] is False
    assert parsed["score"] == 0.2


def test_parse_query_list_accepts_json_array():
    assert _parse_query_list('["pto policy", "leave"]', "fallback") == ["pto policy", "leave"]


def test_parse_query_list_falls_back():
    assert _parse_query_list("not json", "pto policy") == ["pto policy"]
