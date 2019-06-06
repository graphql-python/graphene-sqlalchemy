import re
import warnings
from collections import OrderedDict

from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import class_mapper, object_mapper
from sqlalchemy.orm.exc import UnmappedClassError, UnmappedInstanceError


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
    return "".join(part[:1].upper() + part[1:] for part in name.split("_"))


_re_enum_value_name_1 = re.compile("(.)([A-Z][a-z]+)")
_re_enum_value_name_2 = re.compile("([a-z0-9])([A-Z])")


def to_enum_value_name(name):
    """Convert the given name to a GraphQL enum value name."""
    return _re_enum_value_name_2.sub(
        r"\1_\2", _re_enum_value_name_1.sub(r"\1_\2", name)
    ).upper()


class EnumValue(str):
    """String that has an additional value attached.

    This is used to attach SQLAlchemy model columns to Enum symbols.
    """

    def __new__(cls, s, value):
        return super(EnumValue, cls).__new__(cls, s)

    def __init__(self, _s, value):
        super(EnumValue, self).__init__()
        self.value = value


def _deprecated_default_symbol_name(column_name, sort_asc):
    return column_name + ("_asc" if sort_asc else "_desc")


# unfortunately, we cannot use lru_cache because we still support Python 2
_deprecated_object_type_cache = {}


def _deprecated_object_type_for_model(cls, name):
    try:
        return _deprecated_object_type_cache[cls, name]
    except KeyError:
        from .types import SQLAlchemyObjectType

        obj_type_name = name or cls.__name__

        class ObjType(SQLAlchemyObjectType):
            class Meta:
                name = obj_type_name
                model = cls

        _deprecated_object_type_cache[cls, name] = ObjType
        return ObjType


def sort_enum_for_model(cls, name=None, symbol_name=None):
    """Get a Graphene Enum for sorting the given model class.

    This is deprecated, please use object_type.sort_enum() instead.
    """
    warnings.warn(
        "sort_enum_for_model() is deprecated; use object_type.sort_enum() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from .enums import sort_enum_for_object_type

    return sort_enum_for_object_type(
        _deprecated_object_type_for_model(cls, name),
        name,
        get_symbol_name=symbol_name or _deprecated_default_symbol_name,
    )


def pluralize_name(name):
    s1 = re.sub("y$", "ie", name)
    return "{}s".format(s1)


def sort_argument_for_model(cls, has_default=True):
    """Get a Graphene Argument for sorting the given model class.

    This is deprecated, please use object_type.sort_argument() instead.
    """
    warnings.warn(
        "sort_argument_for_model() is deprecated;"
        " use object_type.sort_argument() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from graphene import Argument, List
    from .enums import sort_enum_for_object_type

    enum = sort_enum_for_object_type(
        _deprecated_object_type_for_model(cls, None),
        get_symbol_name=_deprecated_default_symbol_name,
    )
    if not has_default:
        enum.default = None

    return Argument(List(enum), default_value=enum.default)


argument_cache = {}
field_cache = {}


class FilterArgument:
    pass


class FilterField:
    pass


def create_filter_field(column):
    from graphene import InputObjectType, Field
    from .converter import convert_sqlalchemy_type

    graphene_type = convert_sqlalchemy_type(column.type, column)
    if graphene_type.__class__ == Field:
        return None

    name = "{}Filter".format(str(graphene_type.__class__))
    if name in field_cache:
        return Field(field_cache[name])

    fields = OrderedDict((key, Field(graphene_type.__class__))
                         for key in ["equal", "notEqual", "lessThan", "greaterThan", "like"])
    field_class: InputObjectType = type(name, (FilterField, InputObjectType), {})
    field_class._meta.fields.update(fields)

    field_cache[name] = field_class
    return Field(field_class)


def create_filter_argument(cls):
    from graphene import Argument, InputObjectType
    from sqlalchemy import inspect
    name = "{}Filter".format(cls.__name__)
    if name in argument_cache:
        return Argument(argument_cache[name])
    import re

    NAME_PATTERN = r"^[_a-zA-Z][_a-zA-Z0-9]*$"
    COMPILED_NAME_PATTERN = re.compile(NAME_PATTERN)
    fields = OrderedDict((column.name, field)
                         for column, field in [(column, create_filter_field(column))
                                               for column in inspect(cls).columns.values()] if field and COMPILED_NAME_PATTERN.match(column.name))
    argument_class: InputObjectType = type(name, (FilterArgument, InputObjectType), {})
    argument_class._meta.fields.update(fields)
    argument_cache[name] = argument_class
    return Argument(argument_class)
