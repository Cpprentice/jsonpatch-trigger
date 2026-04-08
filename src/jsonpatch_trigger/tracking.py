import collections
import copy
import functools
from typing import Any, MutableSequence, MutableMapping

import jsonpath
from jsonpath import JSONPointer, JSONPatch, JSONPointerIndexError, JSONPointerKeyError
from pydantic import BaseModel

from jsonpatch_trigger.common import escape_json_pointer_part, profile


@profile
def get_all_subtree_pointers(
        document: Any,
        base_pointer: JSONPointer
) -> set[JSONPointer]:
    try:
        obj = base_pointer.resolve(document)
    except (JSONPointerIndexError, JSONPointerKeyError):
        return set()
    if isinstance(obj, MutableMapping):
        sub_pointers = {
            # copy.deepcopy(base_pointer).join(escape_json_pointer_part(key))
            base_pointer.join(escape_json_pointer_part(key))
            for key in obj.keys()
        }
        return {base_pointer} | sub_pointers | {
            child
            for pointer in sub_pointers
            for child in get_all_subtree_pointers(document, pointer)
        }
    elif isinstance(obj, MutableSequence):
        sub_pointers = {
            # copy.deepcopy(base_pointer).join(str(idx))
            base_pointer.join(str(idx))
            for idx in range(len(obj))
        }
        return {base_pointer} | sub_pointers | {
            child
            for pointer in sub_pointers
            for child in get_all_subtree_pointers(document, pointer)
        }
    return {base_pointer}


class ChangeTracker:
    def __init__(self):
        self.additions: set[JSONPointer] = set()
        self.removals: set[JSONPointer] = set()

    def add_pointers(self, pointers: set[JSONPointer], removal=False):
        if removal:
            self.removals |= pointers
            self.additions -= pointers  # Removes all additions if they are removed again before other actions can trigger
        else:
            self.additions |= pointers
            # TODO for now, we do not do the inverse here: so if something becomes added after removal we still keep it in the removal list
            #  this should not really matter because we don't trigger anything on removals yet

    def add_pointer_pairs(self, pointer_pairs: list[tuple[JSONPointer, bool]]):
        pointer_sorter = collections.defaultdict(set)
        for pointer, removal in pointer_pairs:
            pointer_sorter[removal].add(pointer)
        self.add_pointers(pointer_sorter[True])
        self.add_pointers(pointer_sorter[False])


class ChangeRegistrationMixin(BaseModel):
    @staticmethod
    def _get_pointer(rfc_operation: jsonpath.patch.Op, slot_names: list[str]) -> JSONPointer:
        for slot_name in slot_names:
            pointer = getattr(rfc_operation, slot_name, None)
            if pointer is not None:
                return pointer
        raise RuntimeError('No suitable pointer slot found')

    def pre_execution_registration(self, rfc_operation: jsonpath.patch.Op, change_tracker: ChangeTracker, document: Any):
        pass

    def post_execution_registration(self, rfc_operation: jsonpath.patch.Op, change_tracker: ChangeTracker, document: Any):
        pass


class RemovalRegistrationMixin(ChangeRegistrationMixin):
    @profile
    def pre_execution_registration(self, rfc_operation: jsonpath.patch.Op, change_tracker: ChangeTracker, document: Any):
        pointer = self._get_pointer(rfc_operation, ['path'])
        change_tracker.add_pointers(get_all_subtree_pointers(document, pointer), removal=True)


class CopyRegistrationMixin(ChangeRegistrationMixin):
    @profile
    def post_execution_registration(self, rfc_operation: jsonpath.patch.Op, change_tracker: ChangeTracker, document: Any):
        pointer = self._get_pointer(rfc_operation, ['dest', 'path'])
        change_tracker.add_pointers(get_all_subtree_pointers(document, pointer), removal=False)


class MoveRegistrationMixin(CopyRegistrationMixin):
    @profile
    def pre_execution_registration(self, rfc_operation: jsonpath.patch.Op, change_tracker: ChangeTracker,
                                   document: Any):
        pointer = self._get_pointer(rfc_operation, ['source', 'path'])
        change_tracker.add_pointers(get_all_subtree_pointers(document, pointer), removal=True)


# TODO we likely need some further checking if an operation actually overwrites something else or not
ReplaceRegistrationMixin = MoveRegistrationMixin
AddRegistrationMixin = MoveRegistrationMixin


class TrackingJSONPatch:

    def __init__(self, change_tracker: ChangeTracker, base_operation: ChangeRegistrationMixin, document: Any):
        self._patch = JSONPatch()
        self._tracker = change_tracker
        self._base = base_operation
        self._document = document

    def __getattr__(self, attr):
        patch_attr = getattr(self._patch, attr)

        if not attr.startswith('_') and attr != 'apply':
            # this is a respective method to add an operation

            @functools.wraps(patch_attr)
            @profile
            def wrapper(*args, **kwargs):
                result = patch_attr(*args, **kwargs)
                self._base.pre_execution_registration(result.ops[-1], self._tracker, self._document)
                return result

            return wrapper
        return patch_attr

    @profile
    def run(self, document: Any) -> Any:
        for operation in self._patch.ops:
            document = operation.apply(document)
            self._base.post_execution_registration(operation, self._tracker, document)
        return document
