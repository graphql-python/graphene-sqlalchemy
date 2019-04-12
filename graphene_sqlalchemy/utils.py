import re
import warnings
from collections import OrderedDict

from sqlalchemy.exc import ArgumentError
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import class_mapper, object_mapper
from sqlalchemy.orm.exc import UnmappedClassError, UnmappedInstanceError

from graphene import Argument, List


def get_session(context):
    return context.get("session")


def get_query(model, context):
    query = getattr(model, "query", None)
    if not query:
        session = get_session(context)
        if not session:
            raise Exception(
                "A query in the model Base or a session in the schema is required for querying.\n"
                "Read more http://docs.graphene-python.org/projects/sqlalchemy/en/latest/tips/#querying"
            )
        query = session.query(model)
    return query


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


def to_type_name(name):
    """Convert the given name to a GraphQL type name."""
    return ''.join(part[:1].upper() + part[1:] for part in name.split('_'))


_re_enum_value_name_1 = re.compile('(.)([A-Z][a-z]+)')
_re_enum_value_name_2 = re.compile('([a-z0-9])([A-Z])')


def to_enum_value_name(name):
    """Convert the given name to a GraphQL enum value name."""
    return _re_enum_value_name_2.sub(
        r'\1_\2', _re_enum_value_name_1.sub(r'\1_\2', name)).upper()


def default_symbol_name(column_name, is_asc):
    return to_enum_value_name(column_name) + ("_ASC" if is_asc else "_DESC")


def plain_symbol_name(column_name, is_asc):
    return column_name + ("_asc" if is_asc else "_desc")


class EnumValue(str):
    """Subclass of str that stores a string and an arbitrary value in the "value" property"""

    def __new__(cls, str_value, value):
        return super(EnumValue, cls).__new__(cls, str_value)

    def __init__(self, str_value, value):
        super(EnumValue, self).__init__()
        self.value = value


def create_sort_enum_for_model(
        cls, name=None, symbol_name=default_symbol_name, registry=None):
    """Create a Graphene Enum type for defining a sort order for the given model class.

    The created Enum type and sort order will then be registered for that class.

    Parameters
    - cls : SQLAlchemy model class
        Model used to create the sort enumerator type
    - name : str, optional, default None
        Name to use for the enumerator. If not provided it will be set to the name
        of the class with a 'SortEnum' postfix
    - symbol_name : function, optional, default `default_symbol_name`
        Function which takes the column name and a boolean indicating if the sort
        direction is ascending, and returns the enum symbol name for the current column
        and sort direction. The default function will create, for a column named 'foo',
        the symbols 'FOO_ASC' and 'FOO_DESC'.
    - registry: if not specified, the global registry will be used
    Returns
    - tuple with the Graphene Enum type and the default sort argument for the model
    """
    if not name:
        name = cls.__name__ + "SortEnum"
    if registry is None:
        from .registry import get_global_registry
        registry = get_global_registry()
    members = OrderedDict()
    default_sort = []
    for column in inspect(cls).columns.values():
        asc_name = symbol_name(column.name, True)
        asc_value = EnumValue(asc_name, column.asc())
        members[asc_name] = asc_value
        if column.primary_key:
            default_sort.append(asc_value)
        desc_name = symbol_name(column.name, False)
        desc_value = EnumValue(desc_name, column.desc())
        members[desc_name] = desc_value
    graphene_enum = registry.register_enum(name, members)
    registry.register_sort_params(graphene_enum, default_sort)
    return graphene_enum, default_sort


def get_sort_enum_for_model(cls, registry=None):
    """Get the Graphene Enum type for defining a sort order for the given model class.

    If no Enum type has been registered, create a default one and register it.

    Parameters
    - cls : SQLAlchemy model class
    - registry: if not specified, the global registry will be used
    Returns
    - The Graphene Enum type
    """
    if registry is None:
        from .registry import get_global_registry
        registry = get_global_registry()
    sort_params = registry.get_sort_params_for_model(cls)
    if not sort_params:
        sort_params = create_sort_enum_for_model(cls, registry=registry)
    return sort_params[0]


def sort_enum_for_model(cls, name=None, symbol_name=plain_symbol_name):
    warnings.warn(
        "sort_argument_for_model() is deprecated;"
        " use get_sort_argument_for_model() and create_sort_argument_for_model()",
        DeprecationWarning, stacklevel=2)
    if not name and not symbol_name:
        return get_sort_enum_for_model(cls)
    sort_params = create_sort_enum_for_model(cls, name, symbol_name)
    return sort_params[0]


def get_sort_argument_for_model(cls, has_default=True, registry=None):
    """Returns a Graphene Argument for defining a sort order for the given model class.

    The Argument that is returned accepts a list of sorting directions for the model.
    If `has_default` is set to False, no sorting will happen when this argument is not
    passed. Otherwise results will be sortied by the primary key(s) of the model.
    """
    if registry is None:
        from .registry import get_global_registry
        registry = get_global_registry()
    sort_params = registry.get_sort_params_for_model(cls)
    if not sort_params:
        sort_params = create_sort_enum_for_model(cls, registry=registry)
    enum, default = sort_params
    if not has_default:
        default = None
    return Argument(List(enum), default_value=default)


def sort_argument_for_model(cls, has_default=True):
    warnings.warn(
        "sort_argument_for_model() is deprecated; use get_sort_argument_for_model().",
        DeprecationWarning, stacklevel=2)
    return get_sort_argument_for_model(cls, has_default=has_default)
