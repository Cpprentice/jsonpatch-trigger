import abc
import collections
import copy
import functools
import json
import re
from pprint import pprint
from typing import Any, MutableMapping, MutableSequence, Callable, Mapping, Sequence

import jsonpath
from jsonpath import JSONPath, JSONPatch, JSONPathMatch
from jsonpath.pointer import JSONPointer
from jsonpath.segments import JSONPathSegment, JSONPathRecursiveDescentSegment
from jsonpath.selectors import NameSelector, KeySelector, WildcardSelector, KeysSelector, SliceSelector, \
    SingularQuerySelector, Filter, KeysFilter, JSONPathSelector
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict

from jsonpatch_trigger import make_jsonpath
from jsonpatch_trigger.execution import AutomatedOperationProducer, OperationExecutionContext, OperationExecutionDTO
from jsonpatch_trigger.operations import CompoundOperation, CopyOperation, RemoveOperation, AddOperation, Operation, \
    MoveOperation, PairwisePointerPairConstraintResolver

demo_document = {
    'classes': {
        "Generator": {
            "name": "Generator",
            "attributes": {
                "Variant_ID": {
                    "name": "Variant_ID",
                    "range": "string"
                },
                "PowSource_ID": {
                    "name": "PowSource_ID",
                    "range": "string"
                }
            },
            "slots": []
        },
        "Variant": {
            "name": "Variant",
            "attributes": {
                "Variant_ID": {
                    "name": "Variant_ID",
                    "range": "string"
                },
                "Is_Active": {
                    "name": 'Is_Active',
                    "range": "bool"
                }
            },
            "slots": []
        },
        "PowerSource": {
            "name": "PowerSource",
            "attributes": {
                "PowSource_ID": {
                    "name": "PowSource_ID",
                    "range": "string"
                }
            },
            "slots": []
        }
    },
    "slots": {}
}





# This is already builtin using JSONPointer.from_match(match)
# def extract_json_pointers(document: Any, json_path_expr: str) -> list[JSONPointer]:
#     pointers = []
#     for match in jsonpath.finditer(json_path_expr, document):
#         # path is a list of keys/indexes, convert to JSON Pointer
#         pointer = "/" + "/".join(
#             str(p).replace("~", "~0").replace("/", "~1")  # RFC 6901 escaping
#             for p in match.parts
#         )
#         pointers.append(pointer)
#     return pointers





# This class could be an idea to handle the resolution of parents more effectively
#  However, at the moment it is unclear how a parent ending in a recursive descent (..) would be handled
# class HybridJSONPathPointer:
#     def __init__(self, parent: JSONPath | str, key: str | int | None):
#         if isinstance(parent, str):
#             parent = jsonpath.compile(parent)
#         self.parent = parent
#         self.key = key




class MoveAttributeToRelationOperation(CompoundOperation):

    new_range: str

    def __init__(self, **data: Any):
        locator: JSONPath = data['locator']
        attribute_name = locator.segments[-1].selectors[0].name
        target_locator = make_jsonpath(f'$.slots.{attribute_name}')
        class_name = locator.segments[1].selectors[0].name
        class_slots_locator =  make_jsonpath(f'$.classes.{class_name}.slots[-1]')
        data['inner_operations'] = [
            CopyOperation(
                locator=locator,
                target_locator=target_locator,
                # target_key=locator.segments[-1].name
            ),
            RemoveOperation(
                locator=locator,
                # key=locator.segments[-1].name
            ),
            AddOperation(
                locator=make_jsonpath(f'{target_locator}.range'),
                value=data['new_range']
            ),
            AddOperation(
                locator=class_slots_locator,
                value=data['new_range']
            )
        ]
        super().__init__(**data)


class RenameLinkMLElementOperation(CompoundOperation):
    old_name: str
    new_name: str
    container_path: str

    def __init__(self, /, **data: Any):
        old_name = data['old_name']
        new_name = data['new_name']
        container_path = data['container_path']
        data['inner_operations'] = [
            AddOperation(
                locator=make_jsonpath(f'{container_path}.{old_name}.name'),
                value=new_name
            ),
            MoveOperation(
                locator=make_jsonpath(f'{container_path}.{old_name}'),
                target_locator=make_jsonpath(f'{container_path}.{new_name}'),
                constraint_strategy=PairwisePointerPairConstraintResolver()
            )
        ]
        data['locator'] = make_jsonpath('$')
        super().__init__(**data)


class RenameSlotOperation(RenameLinkMLElementOperation):
    def __init__(self, /, **data: Any):
        data['container_path'] = '$.slots'
        super().__init__(**data)


class RenameAttributeOperation(RenameLinkMLElementOperation):
    class_name: str

    def __init__(self, /, **data: Any):
        class_name = data['class_name']
        data['container_path'] = f'$.classes.{class_name}.attributes'
        super().__init__(**data)

# def perform_auto_update(obj: Any, ):
#     _to_check = [
#         '$.classes[*].attributes[*].name'
#     ]
#     jp = jsonpath.compile(_to_check[0])
#
#     actual_pointer = JSONPointer.from_parts(['classes', 'demo', 'attributes', 'myAttrib', 'name'])
#
#     check = can_pointer_match_path(actual_pointer, jp)
#     handled_pointer_value_pairs = set()
#
#     for class_ in obj['classes'].values():
#         for attribute in class_['attributes'].values():
#             pass





class ConvertAttributeToRelationOperationProducer(AutomatedOperationProducer):

    regular_expression: re.Pattern
    group_index: int = 0
    #
    # def __init__(self, /, **data: Any):
    #     super().__init__(**data)
    #

    def run(self, document: Any, modified_pointers: list[JSONPointer]) -> list[Operation]:
        class_names = set(jsonpath.findall('$.classes.*.name', document))
        operations = []


        for pointer in modified_pointers:
            attribute_name = str(pointer.resolve(document))
            match = re.match(self.regular_expression, attribute_name)
            if match is not None:
                target_entity_name = match.group(self.group_index)
                if target_entity_name in class_names:
                    if pointer.parts[1] == target_entity_name:
                        continue  # this does not apply for primary keys
                    operations.append(MoveAttributeToRelationOperation(
                        locator=make_jsonpath(f'$.{'.'.join(pointer.parts[:-1])}'),
                        new_range=target_entity_name
                    ))
        return operations





def main():

    context = OperationExecutionContext()
    context.register(ConvertAttributeToRelationOperationProducer(
        regular_expression=re.compile(r'(.+)_ID', re.IGNORECASE),
        group_index=1,
        triggers=[
            make_jsonpath('$.classes.*.attributes.*.name')
        ]
    ))
    context.add_custom_operation(AddOperation(
        locator=make_jsonpath('$'),
        value=demo_document
    ))
    context.add_custom_operation(
        # AddOperation(
        #     locator=make_jsonpath('$.classes.*.attributes.PowSource_ID.name'),
        #     value='PowerSource_ID'
        # )
        RenameAttributeOperation(
            old_name='PowSource_ID',
            new_name='PowerSource_ID',
            class_name='*'
        )
    )

    # dto = context.to_dto()

    dictified = context.serialize()
    # dictified = dto.model_dump()
    pprint(dictified)
    # serialized = dto.model_dump_json()
    # print(serialized)

    # loaded = OperationExecutionDTO.model_validate_json(serialized)
    loaded = OperationExecutionContext.deserialize(dictified)

    document = {}
    document = context.run(document)

    print(json.dumps(document, indent=4))

    return

    test = '$.classes[*].name'
    # pointers = extract_json_pointers(document=demo_document, json_path_expr=test)
    pointers = [
        JSONPointer.from_match(match)
        for match in jsonpath.finditer(test, demo_document)
    ]

    hardcore_case = '$.classes..name'
    hardcore_matches = list(jsonpath.finditer(hardcore_case, demo_document))

    hardcore_replacements = ['$.classes', '$.classes..[*]']
    hardcore_replacement_matches = [
        [
            match
            for match in jsonpath.finditer(rep, demo_document)
            if isinstance(match.obj, MutableMapping)
        ]
        for rep in hardcore_replacements
    ]

    locator = '$.classes.myRelation'
    lc = make_jsonpath(locator)

    op = AddObjectOperation(locator='$.classes', object_key='myRelation')
    op.apply(demo_document)

    perform_auto_update(demo_document)




if __name__ == "__main__":
    main()
