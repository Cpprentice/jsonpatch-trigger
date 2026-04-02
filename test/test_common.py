import jsonpath

from jsonpatch_trigger.common import (
    make_jsonpath, normalize_jsonpath, convert_pointer_to_path, escape_json_pointer_part
)
from jsonpath import JSONPointer


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


def test_convert_pointer_to_path():
    pointer = JSONPointer('/a/b/c')
    path = convert_pointer_to_path(pointer)
    assert path == make_jsonpath('$.a.b.c')

    pointer = JSONPointer('/a/b~1c/d')
    path = convert_pointer_to_path(pointer)
    assert path == make_jsonpath('$.a["b/c"].d')


def test_escape_pointer_part():
    assert escape_json_pointer_part('a.b') == 'a.b'
    assert escape_json_pointer_part('a/c') == 'a~1c'
    assert escape_json_pointer_part('a~c') == 'a~0c'