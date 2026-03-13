from typing import MutableSequence, MutableMapping, Any

from jsonpath import JSONPath
from pydantic import BaseModel

from jsonpath_ops.compat import PydanticJSONPath


class PreconditionFunction(BaseModel):
    def __neq__(self, other) -> bool:
        return not self.__eq__(other)


class IsObjectPreconditionFunction(PreconditionFunction):
    def __eq__(self, other):
        return isinstance(other, MutableMapping)


class IsArrayPreconditionFunction(PreconditionFunction):
    def __eq__(self, other):
        return isinstance(other, MutableSequence)


class IsArrayOrObjectPreconditionFunction(PreconditionFunction):
    def __eq__(self, other):
        return isinstance(other, (MutableMapping, MutableSequence))


class ValuePreconditionFunction(PreconditionFunction):
    value: Any
    def __eq__(self, other):
        return other == self.value


class IsNonePreconditionFunction(PreconditionFunction):
    def __eq__(self, other):
        return other is None


class IsNotNonePreconditionFunction(PreconditionFunction):
    def __eq__(self, other):
        return other is not None


class ExistsPreconditionFunction(PreconditionFunction):
    ...


class DoesNotExistPreconditionFunction(PreconditionFunction):
    ...


class Precondition(BaseModel):
    query: PydanticJSONPath
    function: PreconditionFunction
    # def __init__(self, query: JSONPath, function: PreconditionFunction):
    #     self.query = query
    #     self.function = function
