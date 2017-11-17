from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import class_mapper, object_mapper
from sqlalchemy.orm.exc import UnmappedClassError, UnmappedInstanceError
from graphene.utils.str_converters import to_camel_case, to_snake_case


def get_session(context):
    return context.get('session')


def get_query(model, context):
    query = getattr(model, 'query', None)
    if not query:
        session = get_session(context)
        if not session:
            raise Exception('A query in the model Base or a session in the schema is required for querying.\n'
                            'Read more http://graphene-python.org/docs/sqlalchemy/tips/#querying')
        query = session.query(model)
    return query


_operator_aliases = {
    '==': lambda x, y: x == y,
    '=': lambda x, y: x == y,
    '>=': lambda x, y: x >= y,
    '>': lambda x, y: x > y,
    '<=': lambda x, y: x <= y,
    '<': lambda x, y: x < y,
    '!=': lambda x, y: x != y
}


def get_operator_function(operator=None):
    if not operator:
        def operator(x, y):
            return x == y

    if not callable(operator):
        operator_attr = operator

        if operator in _operator_aliases:
            operator = _operator_aliases[operator_attr]
        else:
            def operator(x, y):
                return getattr(x, operator_attr)(y)

    return operator


def get_snake_or_camel_attr(model, attr):
    try:
        return getattr(model, to_snake_case(attr))
    except Exception:
        pass
    try:
        return getattr(model, to_camel_case(attr))
    except Exception:
        pass
    return getattr(model, attr)


def is_mapped_class(cls):
    try:
        class_mapper(cls)
    except (ArgumentError, UnmappedClassError):
        return False
    else:
        return True


def is_mapped_instance(cls):
    try:
        object_mapper(cls)
    except (ArgumentError, UnmappedInstanceError):
        return False
    else:
        return True
