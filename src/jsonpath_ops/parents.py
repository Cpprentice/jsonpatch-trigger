from jsonpath import JSONPath
from jsonpath.segments import JSONPathRecursiveDescentSegment
from jsonpath.selectors import JSONPathSelector

from jsonpath_ops.common import make_jsonpath, normalize_jsonpath


def _make_raw_parent(path: JSONPath) -> JSONPath:
    """
    This could potentially return an invalid JSONPath that returns on ".." and it loops back on the root if needed

    :param JSONPath path: the JSONPath to create a raw parent from
    :return: new JSONPath that was stripped by its last segment
    """
    return normalize_jsonpath(JSONPath(
        env=path.env,
        segments=path.segments[:-1],
        pseudo_root=path.pseudo_root
    ))


def make_parent_key_pairs(path: JSONPath) -> list[tuple[JSONPath, JSONPathSelector | None]]:
    if len(path.segments) == 0:  # this is a root path
        return [(path, None)]

    last_segment = path.segments[-1]
    selectors = last_segment.selectors

    if isinstance(last_segment, JSONPathRecursiveDescentSegment):
        base_parent = _make_raw_parent(path)
        nested_parent = make_jsonpath(f'{base_parent}..*')
        return [
            (parent, selector)
            for parent in [base_parent, nested_parent]
            for selector in selectors
        ]

    return [
        (_make_raw_parent(path), selector)
        for selector in selectors
    ]

    allows_parent = True
    for selector in segment.selectors:
        if isinstance(selector, NameSelector):
            pass
        elif isinstance(selector, KeySelector):
            if selector.key == pointer_part:
                solvable = True
        elif isinstance(selector, WildcardSelector):
            solvable = True
        elif isinstance(selector, KeysSelector):
            pass
        elif isinstance(selector, SliceSelector):
            pass
        elif isinstance(selector, SingularQuerySelector):
            pass
        elif isinstance(selector, Filter):
            pass
        elif isinstance(selector, KeysFilter):
            pass