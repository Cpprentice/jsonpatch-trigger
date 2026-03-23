import abc
from typing import Any, Annotated, Union, ClassVar, Self

from jsonpath import JSONPointer, JSONPath, JSONPathMatch, JSONPointerIndexError, JSONPointerKeyError
from jsonpath.selectors import NameSelector, JSONPathSelector, IndexSelector
from pydantic import PrivateAttr, Field, ConfigDict, BaseModel, Discriminator, Tag, computed_field, model_validator, \
    ValidationError, model_serializer, field_serializer

from jsonpatch_plus import json_type
from jsonpatch_plus.compat import PydanticJSONPath
from jsonpatch_plus.parents import make_parent_key_pairs
from jsonpatch_plus.preconditions import Precondition, IsArrayOrObjectPreconditionFunction, ExistsPreconditionFunction, \
    DoesNotExistPreconditionFunction
from jsonpatch_plus.tracking import ChangeTracker, TrackingJSONPatch, RemovalRegistrationMixin, \
    CopyRegistrationMixin, AddRegistrationMixin, MoveRegistrationMixin


class OperationBehavior(abc.ABC):
    ...


class Operation(BaseModel, abc.ABC):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        revalidate_instances='never'
    )
    _preconditions: list[Precondition] = PrivateAttr(default_factory=list)
    user_preconditions: list[Precondition] = Field(default_factory=list)

    locator: PydanticJSONPath

    @computed_field
    @property
    def operation_type(self) -> str:
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
        if isinstance(value, Operation):
            return value
        elif isinstance(value, dict):
            if cls is not Operation:
                return value
            operation_type = value.pop('operation_type')
            return cls._registry[operation_type](**value)
        raise ValidationError("Cannot deserialize operation")

    # @model_serializer(mode='plain')
    # def serialize(self) -> dict:
    #     cls = self.__class__
    #     return cls.model_dump(self)

    @property
    def preconditions(self) -> list[Precondition]:
        return self._preconditions + self.user_preconditions

    # @property
    # def parent_locators(self) -> list[JSONPath]:
    #     return make_parent_key_pairs(self.locator)

    # @property
    # def key(self) -> int | str | None:
    #     return self.locator.segments[-1].selectors[0].name

    @staticmethod
    def iterate_matches(
            path: JSONPath,
            document: Any,
            none_allowed=False,
            only_resolvable_pointers=False
    ) -> list[tuple[JSONPath, JSONPathMatch, JSONPathSelector, JSONPointer]]:
        results = []

        parent_key_pairs = make_parent_key_pairs(path)
        for parent_path, selector in parent_key_pairs:
            for parent_match in parent_path.finditer(document):
                pointer = JSONPointer.from_match(parent_match)
                if isinstance(selector, NameSelector):
                    pointer = pointer.join(selector.name)
                elif isinstance(selector, IndexSelector):
                    if selector.index == -1:
                        pointer = pointer.join('-')
                    elif selector.index < 0:
                        raise RuntimeError('Cannot use negative indexes other than -1 for json pointers')
                    else:
                        pointer = pointer.join(str(selector.index))
                elif none_allowed and selector is None:
                    pass
                else:
                    raise NotImplementedError('Selector type not supported')
                if only_resolvable_pointers:
                    try:
                        pointer.resolve(document)
                    except (JSONPointerIndexError, JSONPointerKeyError):
                        continue
                results.append((parent_path, parent_match, selector, pointer))
        return results

    # def apply(self, onto: Any) -> list[JSONPointer]:
    #     if not self.test_preconditions(onto):
    #         return []
    #     return self._apply(onto)

    def apply_rfc(self, document: Any, change_tracker: ChangeTracker) -> Any:
        if not self.test_preconditions(document):
            return document
        patch_runner = TrackingJSONPatch(change_tracker, self, document)
        self.register_rfc_operations(document, patch_runner)
        document = patch_runner.run(document)
        return document

    # @abc.abstractmethod
    # def _apply(self, onto: Any) -> list[JSONPointer]:
    #     ...

    @abc.abstractmethod
    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):
        ...

    def test_preconditions(self, onto: Any) -> bool:
        for condition in self.preconditions:
            match = condition.query.match(onto)
            if match is None:
                if isinstance(condition.function, DoesNotExistPreconditionFunction):
                    return True
                if isinstance(condition.function, ExistsPreconditionFunction):
                    return False
                return False

            if match.obj != condition.function:
                return False
        return True


# class AddObjectOperation(Operation):
#
#     object_key: str
#
#     def __init__(self, **data: Any):
#         super().__init__(**data)
#         self._preconditions = [
#             Precondition(
#                 query=self.locator,
#                 function=IsObjectPreconditionFunction()
#             ),
#             Precondition(
#                 query=jsonpath.compile(f'{self.locator}.{self.object_key}'),
#                 function=IsNonePreconditionFunction()
#             )
#         ]
#
#     def _apply(self, onto: Any) -> list[JSONPointer]:
#         pointers = []
#         for ref in self.locator.finditer(onto):
#             ref.obj[self.object_key] = {}
#             pointers.append(JSONPointer.from_match(ref).join(self.object_key))
#         return pointers
#
#
# class InsertScalarOperation(Operation):
#
#     # key: int | str
#     value: int | float | bool | str | None
#
#     def __init__(self, /, **data: Any):
#         super().__init__(**data)
#         self._preconditions = [
#             Precondition(
#                 query=self.locator,
#                 function=IsArrayOrObjectPreconditionFunction()
#             ),
#             Precondition(
#                 query=jsonpath.compile(f'{self.locator}.{self.key}'),
#                 function=IsNonePreconditionFunction()
#             ),
#         ]
#
#     def _apply(self, onto: Any) -> list[JSONPointer]:
#         match = self.locator.match(onto)
#         if isinstance(match.obj, MutableMapping):
#             match.obj[self.key] = self.value
#         else:
#             match.obj.insert(self.key, self.value)
#         return [JSONPointer.from_match(match).join(self.key)]



# RFC 6902 compliant operations

class AddOperation(Operation, AddRegistrationMixin):

    value: json_type

    # def __init__(self, /, **data: Any):
    #     super().__init__(**data)
    #     locator = self.locator

        # parent_locator = make_parent(locator)

        # if len(locator.segments) == 1 and locator.segments[0].selectors:
        #     _ = 42

        # self._preconditions = [
        #     Precondition(
        #         query=self.locator,
        #
        #     )
        # ]

    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):
        for parent_path, parent_match, selector, pointer in (
                self.iterate_matches(self.locator, document, none_allowed=True)
        ):
            patch_runner.add(pointer, self.value)

    # def _apply(self, onto: Any) -> list[JSONPointer]:
    #     match = self.locator.match(onto)
    #     parent_matches = [x.match(onto) for x in self.parent_locators]
    #
    #     pointers = []
    #     for parent_match in parent_matches:
    #         if isinstance(parent_match.obj, MutableMapping):
    #             parent_match.obj[self.key] = self.value
    #             pointers.extend(get_all_subtree_pointers(onto, JSONPointer.from_match(match)))
    #         elif isinstance(parent_match.obj, MutableSequence):
    #             parent_match.obj.insert(self.key, self.value)
    #             pointers.extend(get_all_subtree_pointers(onto, JSONPointer.from_match(match)))
    #     return pointers



class PointerPairConstraintResolver(BaseModel):
    def resolve(
            self,
            pointers_a: list[JSONPointer],
            pointers_b: list[JSONPointer]
    ) -> list[tuple[JSONPointer, JSONPointer]]:
        if len(pointers_a) != 1 or len(pointers_b) != 1:
            raise RuntimeError('Only a single pair is allowed')
        return [(pointers_a[0], pointers_b[0])]


class OneToManyPointerPairConstraintResolver(PointerPairConstraintResolver):
    def resolve(
            self,
            pointers_a: list[JSONPointer],
            pointers_b: list[JSONPointer]
    ) -> list[tuple[JSONPointer, JSONPointer]]:
        if len(pointers_a) != 1 or len(pointers_b) == 0:
            raise RuntimeError('Invalid one to many pointer pairs')
        return [
            (pointers_a[0], pointer)
            for pointer in pointers_b
        ]


class PairwisePointerPairConstraintResolver(PointerPairConstraintResolver):
    def resolve(
            self,
            pointers_a: list[JSONPointer],
            pointers_b: list[JSONPointer]
    ) -> list[tuple[JSONPointer, JSONPointer]]:
        if len(pointers_a) != len(pointers_b):
            raise RuntimeError('Can\'t handle number of pointers for move')
        return [
            (p_a, p_b)
            for p_a, p_b in zip(
                sorted(pointers_a, key=lambda p: str(p)),
                sorted(pointers_b, key=lambda p: str(p))
            )
        ]


class MoveOperation(Operation, MoveRegistrationMixin):

    target_locator: PydanticJSONPath
    constraint_strategy: PointerPairConstraintResolver = Field(default_factory=PointerPairConstraintResolver)

    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):
        source_data_tuple = self.iterate_matches(self.locator, document, none_allowed=True)
        target_data_tuple = self.iterate_matches(self.target_locator, document, none_allowed=True)

        source_pointers = [t[3] for t in source_data_tuple]
        target_pointers = [t[3] for t in target_data_tuple]

        for source_pointer, target_pointer in self.constraint_strategy.resolve(source_pointers, target_pointers):
            try:
                source_pointer.resolve(document)
            except (JSONPointerIndexError, JSONPointerKeyError):
                continue  # this can happen, and we don't consider it an error
            patch_runner.move(source_pointer, target_pointer)


        # TODO check what happens if the target pointer is below the source pointer? will it just insert a copy of the original object or is this referencing each other
        # parent_key_pairs = make_parent_key_pairs(self.locator)
        #
        # assert len(parent_key_pairs) == 1  # we should only have one source-key pair otherwise the behavior is not clear
        # source_matches = list(self.locator.finditer(document))
        #
        # # however for actual matches it is fine if we can find clear pairs of source and target
        # #  e.g. to move several attributes with the same name in multiple classes
        # #   but this is a generic move operation that has no knowledge on what would be okay
        # #   i guess I need another workaround here...
        #
        # source_pointers = sorted([JSONPointer.from_match(match) for match in source_matches])
        #
        # target_matches = self.iterate_matches(self.target_locator, document, none_allowed=False)
        # target_pointers = sorted([JSONPointer.from_match(match) for match in target_matches])
        #
        #
        # for source_pointer, target_pointer in zip(source_pointers, target_pointers):
        #
        # # assert len(source_matches) == 1
        # source_pointer = JSONPointer.from_match(source_matches[0])
        #
        #
        # assert len(matches) == 1  # we should only have one target otherwise the behavior is not clear
        #
        # parent_path, parent_match, selector, pointer = matches[0]
        # patch_runner.move(source_pointer, pointer)



class CopyOperation(Operation, CopyRegistrationMixin):

    target_locator: PydanticJSONPath
    constraint_strategy: PointerPairConstraintResolver = Field(default_factory=OneToManyPointerPairConstraintResolver)
    # target_key: str | int

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._preconditions = [
            Precondition(
                query=self.locator,
                function=IsArrayOrObjectPreconditionFunction()
            )
        ]

    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):
        source_data_tuple = self.iterate_matches(self.locator, document, none_allowed=True,
                                                 only_resolvable_pointers=True)
        target_data_tuple = self.iterate_matches(self.target_locator, document, none_allowed=True)

        source_pointers = [t[3] for t in source_data_tuple]
        target_pointers = [t[3] for t in target_data_tuple]

        for source_pointer, target_pointer in self.constraint_strategy.resolve(source_pointers, target_pointers):
            patch_runner.copy(source_pointer, target_pointer)

        # parent_key_pairs = make_parent_key_pairs(self.locator)
        # assert len(parent_key_pairs) == 1  # we should only have one source otherwise the behavior is not clear
        # source_matches = list(self.locator.finditer(document))
        # assert len(source_matches) == 1
        # source_pointer = JSONPointer.from_match(source_matches[0])
        #
        # for parent_path, parent_match, selector, pointer in (
        #     self.iterate_matches(self.target_locator, document, none_allowed=False)
        # ):
        #     patch_runner.copy(source_pointer, pointer)

    # def _apply(self, onto: Any) -> list[JSONPointer]:
    #     match = self.locator.match(onto)
    #     target_parent = self.target_locator.match(onto)
    #     if isinstance(target_parent.obj, MutableMapping):
    #         target_parent.obj[self.target_key] = match.obj
    #         return get_all_subtree_pointers(
    #             onto,
    #             JSONPointer.from_match(target_parent)
    #             .join(self.target_key)
    #         )
    #     elif isinstance(target_parent.obj, MutableSequence):
    #         target_parent.obj.insert(self.target_key, match.obj)
    #         return get_all_subtree_pointers(
    #             onto,
    #             JSONPointer.from_match(target_parent)
    #             .join(self.target_key)
    #         )
    #     raise RuntimeError('Invalid state')


class RemoveOperation(Operation, RemovalRegistrationMixin):

    # key: str | int
    #
    # def __init__(self, **data: Any):
    #     super().__init__(**data)
    #     # if self.key is not None:
    #     self._preconditions = [
    #         Precondition(
    #             query=self.locator,
    #             function=IsArrayOrObjectPreconditionFunction()
    #         )
    #     ]
        # else:
        #     self._preconditions = [
        #         Precondition(
        #             query=self.locator,
        #             function=IsNotNonePreconditionFunction()
        #         )
        #     ]
    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):
        for parent_path, parent_match, selector, pointer in (
            self.iterate_matches(self.locator, document, none_allowed=False)
        ):
            patch_runner.remove(pointer)

    # def _apply(self, onto: Any) -> list[JSONPointer]:
    #     match = self.locator.match(onto)
    #     # if isinstance(match.obj, (MutableMapping, MutableSequence)):
    #     pointers = get_all_subtree_pointers(
    #         onto,
    #         JSONPointer.from_match(match).join(self.key)
    #     )
    #     del match.obj[self.key]
    #     return pointers

# End RFC 6902 compliant operations

class CompoundOperation(Operation):

    inner_operations: list[Operation]

    def register_rfc_operations(self, document: Any, patch_runner: TrackingJSONPatch):
        for operation in self.inner_operations:
            operation.register_rfc_operations(document, patch_runner)

    def apply_rfc(self, document: Any, change_tracker: ChangeTracker) -> Any:
        if not self.test_preconditions(document):
            return document
        for operation in self.inner_operations:
            document = operation.apply_rfc(document, change_tracker)
        return document

    @field_serializer('inner_operations')
    def _serialize_inner_operations(self, ops: list[Operation]) -> list[dict]:
        return [
            op.model_dump() for op in ops
        ]


def _get_type_designator(obj: Operation) -> str:
    return obj.__class__.__qualname__

# Operation = Annotated[
#     Union[
#         Annotated[AddOperation, Tag('AddOperation')],
#         Annotated[RemoveOperation, Tag('RemoveOperation')],
#         Annotated[CompoundOperation, Tag('CompoundOperation')],
#         Annotated[MoveOperation, Tag('MoveOperation')],
#         Annotated[CopyOperation, Tag('CopyOperation')],
#     ],
#     Discriminator(_get_type_designator)
# ]