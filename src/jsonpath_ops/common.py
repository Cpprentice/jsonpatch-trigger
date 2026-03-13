from typing import Sequence, Any, Mapping

import jsonpath
from jsonpath import JSONPath
from pydantic import TypeAdapter
from pydantic_core import core_schema

json_type = str | int | float | bool | None | Sequence[Any] | Mapping[str, Any]


def make_jsonpath(path_string: str) -> JSONPath:
    return jsonpath.compile(str(jsonpath.compile(path_string)))


def normalize_jsonpath(path: JSONPath) -> JSONPath:
    return jsonpath.compile(str(path))


def serialize_jsonpath(path: JSONPath) -> str:
    return str(path)


#
#
# class ThirdPartyPydanticAdapter:
#     @staticmethod
#     def __get_pydantic_core_schema__(source_type, handler: GetCoreSchemaHandler):
#         return core_schema.no_info_wrap_validator_function(
#             make_jsonpath,
#             core_schema.str_schema(),
#             serialization=core_schema.plain_serializer_function_ser_schema(
#                 serialize_jsonpath,
#                 return_schema=core_schema.str_schema(),
#             )
#         )
#
#
# class JSONPathAdapter(TypeAdapter):
#
#     @classmethod
#     def __get_pydantic_core_schema__(cls, source_type, handler):
#         return core_schema.chain_schema([
#             core_schema.str_schema(),
#             core_schema.no_info_after_validator_function(
#                 make_jsonpath,
#                 serialization=core_schema.plain_serializer_function_ser_schema(
#                     serialize_jsonpath
#                 )
#             )
#         ])
