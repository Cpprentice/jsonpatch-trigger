import jsonpath
from jsonpath import JSONPath

from jsonpatch_plus.common import make_jsonpath
from jsonpatch_plus.parents import _make_raw_parent, make_parent_key_pairs


def test_make_raw_parent():
    empty_path = make_jsonpath('')
    root_path = make_jsonpath('$')
    pseudo_root_path = make_jsonpath('^')

    # empty path and root path are equal so only test one of them
    assert empty_path == root_path
    assert pseudo_root_path == root_path

    # Important! different forms of writing are unequal if not built using jsonpatch_plus.common.make_jsonpath
    assert make_jsonpath('$["a"]') == make_jsonpath('$.a')
    assert jsonpath.compile('$["a"]') != jsonpath.compile('$.a')

    assert _make_raw_parent(make_jsonpath('$.a.b.c')) == make_jsonpath('$.a.b')

    one_path = make_jsonpath('a')
    simple_path = make_jsonpath('$.a.b.c')
    deep_path = make_jsonpath('$a..c')

    p = _make_raw_parent(root_path)
    assert p == root_path

    p = _make_raw_parent(one_path)
    assert p == root_path

    p = _make_raw_parent(simple_path)
    assert p == make_jsonpath('$.a.b')
    assert len(p.segments) == 2
    assert p.segments[0].selectors[0].name == 'a'
    assert p.segments[1].selectors[0].name == 'b'

    # "..c" forms the last segment
    p = _make_raw_parent(deep_path)
    assert p == make_jsonpath('$.a')
    assert len(p.segments) == 1
    assert p.segments[0].selectors[0].name == 'a'


def test_make_parent_key_pairs():
    root_path = make_jsonpath('$')
    pairs = make_parent_key_pairs(root_path)
    assert len(pairs) == 1
    assert pairs[0][0] == root_path
    assert pairs[0][1] is None

    simple_path = make_jsonpath('$.a.b.c')
    pairs = make_parent_key_pairs(simple_path)
    assert len(pairs) == 1
    assert pairs[0][0] == make_jsonpath('$.a.b')
    assert pairs[0][0].segments[-1].selectors[0].name == 'b'
    assert str(pairs[0][1]) == "'c'"

    split_path = make_jsonpath('$.a.b[c,d]')
    pairs = make_parent_key_pairs(split_path)
    assert len(pairs) == 2
    assert pairs[0][0] == make_jsonpath('$.a.b')
    assert str(pairs[0][1]) == "$['c']"
    assert pairs[1][0] == make_jsonpath('$.a.b')
    assert str(pairs[1][1]) == "$['d']"

    deep_path = make_jsonpath('$..c')
    pairs = make_parent_key_pairs(deep_path)
    assert len(pairs) == 2
    assert pairs[0][0] == make_jsonpath('')
    assert pairs[1][0] == make_jsonpath('$..*')
    assert str(pairs[0][1]) == "'c'"
    assert str(pairs[1][1]) == "'c'"
