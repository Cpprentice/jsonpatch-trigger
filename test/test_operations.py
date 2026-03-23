from typing import Any, Generator
from unittest.mock import MagicMock
import unittest.mock

import pytest
from jsonpath import JSONPointer

from jsonpatch_trigger import make_jsonpath
from jsonpatch_trigger.operations import CompoundOperation, Operation, AddOperation


@pytest.fixture
def compound_operation() -> CompoundOperation:
    operation_mock = MagicMock(spec=Operation)
    return CompoundOperation(
        inner_operations=[
            operation_mock
        ],
        locator=make_jsonpath('$')
    )

@pytest.fixture
def compound_operation_with_preconditions() -> Generator[tuple[CompoundOperation, MagicMock], Any, None]:
    operation_mock = MagicMock(spec=Operation)
    op = CompoundOperation(
        inner_operations=[
            operation_mock
        ],
        locator=make_jsonpath('$')
    )
    with unittest.mock.patch.object(CompoundOperation, 'test_preconditions', MagicMock(return_value=False)) as test_preconditions_mock:
        yield op, test_preconditions_mock


def test_compound_operation_register_rfc_operations(compound_operation):
    compound_operation.register_rfc_operations({}, None)
    mock = compound_operation.inner_operations[0]

    assert mock.register_rfc_operations.call_count == 1
    assert mock.register_rfc_operations.call_args_list[0].args == ({}, None)


def test_compound_operation_apply_rfc(compound_operation):
    compound_operation.apply_rfc({}, None)
    mock = compound_operation.inner_operations[0]

    assert mock.apply_rfc.call_count == 1
    assert mock.apply_rfc.call_args_list[0].args == ({}, None)


def test_compound_operation_apply_rfc_preconditions(compound_operation_with_preconditions):
    compound_op, test_preconditions_mock = compound_operation_with_preconditions
    compound_op.apply_rfc({}, None)

    assert test_preconditions_mock.call_count == 1
    assert test_preconditions_mock.return_value == False

    mock = compound_op.inner_operations[0]
    assert mock.apply_rfc.call_count == 0


def test_operation_iterate_matches():
    matches = Operation.iterate_matches(make_jsonpath('$.a.b'), {
        "a": {"b": 42}
    }, none_allowed=False)

    assert len(matches) == 1
    path, match, selector, pointer = matches[0]
    assert path == make_jsonpath('$.a')
    assert str(selector) == "'b'"
    assert pointer == JSONPointer('/a/b')

    with pytest.raises(NotImplementedError):
        Operation.iterate_matches(make_jsonpath('$.a.~'), {
            "a": {"b": 42}
        })

    matches = Operation.iterate_matches(make_jsonpath('$'), {
        "a": 42
    }, none_allowed=True)
    assert len(matches) == 1
    path, match, selector, pointer = matches[0]
    assert path == make_jsonpath('$')
    assert selector is None
    assert pointer == JSONPointer('')


def test_operation_iterate_matches_complex():
    matches = Operation.iterate_matches(make_jsonpath('$.classes.*.attributes.attributeA'), {
        "classes": {
            "ABC": {
                "attributes": {
                    "attributeA": {
                        "name": "attributeA"
                    }
                }
            },
            "DEF": {
                "attributes": {
                    "other": {
                        "name": "other"
                    }
                }
            }
        }
    }, none_allowed=True, only_resolvable_pointers=True)
    assert len(matches) == 1
    _ = 42


def test_add_operation():
    tracker = MagicMock()
    op = AddOperation(locator=make_jsonpath('$.a.b'), value=[42])
    document = {'a': {'c': 21}}
    op.apply_rfc(document, tracker)

    assert document['a']['b'] == [42]
