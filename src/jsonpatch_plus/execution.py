import abc
import collections
import json
from typing import Any, Self, ClassVar

from jsonpath import JSONPath, JSONPointer
from jsonpath.segments import JSONPathSegment
from jsonpath.selectors import NameSelector, KeySelector, WildcardSelector, KeysSelector, SliceSelector, \
    SingularQuerySelector, Filter, KeysFilter
from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer, computed_field, model_validator, \
    ValidationError

from jsonpatch_plus import make_jsonpath
from jsonpatch_plus.operations import Operation, Operation
from jsonpatch_plus.tracking import ChangeTracker


def can_pointer_match_path(pointer: JSONPointer, path: JSONPath) -> bool:
    pointer_index = len(pointer.parts) - 1
    path_index = len(path.segments) - 1

    while pointer_index >= 0 and path_index >= 0:
        pointer_part: str | int = pointer.parts[pointer_index]
        segment: JSONPathSegment = path.segments[path_index]

        solvable = False
        for selector in segment.selectors:
            if isinstance(selector, NameSelector):
                if selector.name == pointer_part:
                    solvable = True
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
                query = selector.query
                sub_pointer_starting_index = pointer_index
                inner_solvable = False
                while sub_pointer_starting_index >= 0:
                    sub_pointer = JSONPointer.from_parts(pointer.parts[sub_pointer_starting_index:pointer_index + 1])
                    if can_pointer_match_path(sub_pointer, query):
                        sub_pointer_starting_index -= 1
                        inner_solvable = True
                    else:
                        sub_pointer_starting_index += 1
                        break
                if inner_solvable:
                    pointer_index -= pointer_index - sub_pointer_starting_index
                    solvable = True
            elif isinstance(selector, Filter):
                pass
            elif isinstance(selector, KeysFilter):
                pass
        if not solvable:
            return False
        pointer_index -= 1
        path_index -= 1

    return pointer_index == path_index


class AutomatedOperationProducer(BaseModel, abc.ABC):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

    triggers: list[JSONPath] = Field(default_factory=list)

    @computed_field
    @property
    def producer_type(self) -> str:
        return self.__class__.__qualname__

    _registry: ClassVar[dict[str, type[Self]]] = {}

    def __init_subclass__(cls, **kwargs):
        cls._registry[cls.__qualname__] = cls

    @model_validator(mode='before')
    @classmethod
    def validate(
            cls,
            value: Any,
            *,
            strict: bool | None = None,
            from_attributes: bool | None = None,
            context: Any | None = None,
    ):
        if isinstance(value, AutomatedOperationProducer):
            return value
        elif isinstance(value, dict):
            if cls is not AutomatedOperationProducer:
                return value
            producer_type = value.pop('producer_type')
            return cls._registry[producer_type](**value)
        raise ValidationError("Cannot deserialize automated producer")

    @abc.abstractmethod
    def run(
            self,
            document: Any,
            modified_pointers: list[JSONPointer]
    ) -> list[Operation]:
        ...

    @field_validator('triggers', mode='before')
    @classmethod
    def parse_triggers(cls, value_list):
        return [
            p
            if isinstance(p, JSONPath) else
            make_jsonpath(p)
            for p in value_list
        ]

    @field_serializer('triggers', when_used='always')
    def serialize_triggers(self, path_list: list[JSONPath]):
        return [
            str(p)
            for p in path_list
        ]


# class OperationExecutionDTO(BaseModel):
#     model_config = ConfigDict(
#         revalidate_instances='never'
#     )
#
#     operations: list[Operation]
#     # listeners: dict[str, list[str]]
#     producers: list[AutomatedOperationProducer]
#
#     @model_validator(mode='after')
#     @classmethod
#     def validate(cls, value: Any):
#         if isinstance(value, cls):
#             return value
#         return cls(**value)
#
#     # @field_validator('operations', mode='before')
#     # @classmethod
#     # def _serialize_operations(cls, operation_list: list[Operation]):
#     #     return [
#     #         op.model_dump()
#     #         for op in operation_list
#     #     ]
#
#     @field_serializer('operations')
#     def serialize_operations(self, operations: list[Operation]) -> list[dict]:
#         return [
#             op.model_dump() for op in operations
#         ]
#
#     @field_serializer('producers')
#     def serialize_producers(self, producers: list[AutomatedOperationProducer]) -> list[dict]:
#         return [
#             prod.model_dump() for prod in producers
#         ]


class OperationExecutionContext:

    def __init__(self):
        self.listeners: dict[JSONPath, list[AutomatedOperationProducer]] = collections.defaultdict(list)
        self.operations: collections.deque[Operation] = collections.deque()

    def register(self, producer: AutomatedOperationProducer):
        for trigger in producer.triggers:
            self.listeners[trigger].append(producer)

    def add_custom_operations(self, operations: list[Operation]):
        self.operations.extend(operations)

    def add_custom_operation(self, operation: Operation):
        self.operations.append(operation)

    def run(self, document: Any) -> Any:

        while self.operations:
            operation = self.operations.popleft()
            change_tracker = ChangeTracker()
            document = operation.apply_rfc(document, change_tracker)
            for trigger in self.listeners.keys():
                # TODO we might encounter scenarios where we would want to also trigger on removal
                relevant_pointers = [p for p in change_tracker.additions if can_pointer_match_path(p, trigger)]
                if relevant_pointers:
                    for producer in self.listeners[trigger]:
                        added_operations = producer.run(document, relevant_pointers)
                        self.operations.extendleft(reversed(added_operations))
        return document

    def serialize(self) -> dict:
        flat_producer_lookup = {
            producer.__class__.__name__: producer
            for producers in self.listeners.values()
            for producer in producers
        }
        return dict(
            operations=[
                op.model_dump()
                for op in self.operations
            ],
            producers=[
                producer.model_dump()
                for producer in flat_producer_lookup.values()
            ]
        )
        # return OperationExecutionDTO(
        #     operations=list(self.operations),
        #     producers=list(flat_producer_lookup.values())
        #     # listeners={
        #     #     str(path): [
        #     #         producer.__class__.__name__
        #     #         for producer in producers
        #     #     ]
        #     #     for path, producers in self.listeners.items()
        #     # }
        # )

    @classmethod
    def deserialize(cls, data: Any) -> Self:
        if isinstance(data, str):
            data = json.loads(data)

        operations = [
            Operation.validate(op)
            for op in data['operations']
        ]
        producers = [
            AutomatedOperationProducer.validate(producer)
            for producer in data['producers']
        ]

        self = cls()
        self.add_custom_operations(operations)
        for producer in producers:
            self.register(producer)
        return self
