from graphene import ObjectType, Schema, String

from ..utils import get_session, get_operator_function


def test_get_session():
    session = 'My SQLAlchemy session'

    class Query(ObjectType):
        x = String()

        def resolve_x(self, info):
            return get_session(info.context)

    query = '''
        query ReporterQuery {
            x
        }
    '''

    schema = Schema(query=Query)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    assert result.data['x'] == session


def test_get_operator_function():
    func = get_operator_function('=')
    assert func(1, 1)
    assert not func(1, 2)

    func = get_operator_function('!=')
    assert not func(1, 1)
    assert func(1, 2)

    class DummyLike:
        def __init__(self, value):
            self.value = value

        def like(self, other):
            return self.value == other

    func = get_operator_function('like')
    assert func(DummyLike(1), 1)
    assert not func(DummyLike(1), 2)

    func = get_operator_function(lambda x, y: x > y)
    assert func(5, 3)
    assert not func(3, 5)
