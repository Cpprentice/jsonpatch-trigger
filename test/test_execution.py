from typing import Any

import pytest
from jsonpath import JSONPointer

from jsonpatch_trigger import make_jsonpath, OperationExecutionContext, AutomatedOperationProducer, Operation, AddOperation
from jsonpatch_trigger.execution import can_pointer_match_path


def test_can_pointer_match_path():
    p = make_jsonpath('$.a[b,e].c')

    assert can_pointer_match_path(JSONPointer('/a/b/c'), p)

    p = make_jsonpath('$.a[b,e].*')
    assert can_pointer_match_path(JSONPointer('/a/b/c'), p)

    p = make_jsonpath('$.a.*')
    assert not can_pointer_match_path(JSONPointer('/a/b/c'), p)


@pytest.fixture
def listener_class():
    class Listener(AutomatedOperationProducer):
        def run(self, document: Any, modified_pointers: list[JSONPointer]) -> list[Operation]:
            return []

    return Listener


def test_operation_execution_context_serialize_and_deserialize(listener_class):
    ctx = OperationExecutionContext()

    ctx.register(listener_class(triggers=[
        make_jsonpath('$.a.b.c')
    ]))

    ctx.add_custom_operation(AddOperation(locator=make_jsonpath('$'), value={'a': 42}))

    data = ctx.serialize()

    assert 'operations' in data
    assert 'producers' in data

    operation = data['operations'][0]
    producer = data['producers'][0]

    assert 'locator' in operation and operation['locator'] == '$'
    assert 'value' in operation and operation['value'] == {'a': 42}

    assert 'triggers' in producer and "$['a']['b']['c']" in producer['triggers']

    deserialized = OperationExecutionContext.deserialize(data)
    assert len(deserialized.operations) == 1
    assert len(deserialized.listeners) == 1

    assert deserialized.operations[0].locator == make_jsonpath('$')


def test_operation_execution_context_run(listener_class):
    ctx = OperationExecutionContext()

    ctx.register(listener_class(triggers=[
        make_jsonpath('$.a.b.c')
    ]))

    ctx.add_custom_operation(AddOperation(locator=make_jsonpath('$'), value={'a': 42}))
    ctx.register(listener_class(triggers=[
        make_jsonpath('$.a')
    ]))

    doc = ctx.run({})

    assert len(ctx.operations) == 0

    assert doc == {'a': 42
                   }