from jsonpath import JSONPointer

from jsonpatch_plus.tracking import get_all_subtree_pointers, ChangeTracker


def test_get_all_subtree_pointers():
    pointers = get_all_subtree_pointers({}, JSONPointer(
        ''
    ))
    assert pointers == {JSONPointer('')}

    pointers = get_all_subtree_pointers({
        'a': [
            {'b': 42}
        ]
    }, JSONPointer(''))
    assert len(pointers) == 4


def test_change_tracker_add_pointers():
    change_tracker = ChangeTracker()

    change_tracker.add_pointers({JSONPointer('/a/b/c')}, removal=False)
    change_tracker.add_pointers({JSONPointer('/a/b/c')}, removal=True)

    assert len(change_tracker.removals) == 1
    assert len(change_tracker.additions) == 0, 'Removal of pointer does not remove it from additions'

