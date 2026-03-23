import jsonpath

from jsonpatch_trigger.common import make_jsonpath, normalize_jsonpath


def test_make_jsonpath():
    p1 = make_jsonpath('$.a.b.c')
    p2 = make_jsonpath('$["a"]["b"]["c"]')
    p3 = make_jsonpath("$['a']['b']['c']")
    p4 = make_jsonpath("$['a'].b[\"c\"]")

    assert p1 == p2
    assert p2 == p3
    assert p3 == p4


def test_normalize_jsonpath():
    p1 = jsonpath.compile("$.a.b.c")
    p2 = make_jsonpath("$.a.b.c")

    assert p1 != p2
    assert normalize_jsonpath(p1) == p2
