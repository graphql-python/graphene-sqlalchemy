import re
import typing
import warnings
from collections import OrderedDict
from functools import _c3_mro
from importlib.metadata import version as get_version
from typing import Any, Callable, Dict, Optional

from packaging import version
from sqlalchemy import select
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import class_mapper, object_mapper
from sqlalchemy.orm.exc import UnmappedClassError, UnmappedInstanceError

from graphene import NonNull


def get_nullable_type(_type):
    if isinstance(_type, NonNull):
        return _type.of_type
    return _type


def is_sqlalchemy_version_less_than(version_string):
    """Check the installed SQLAlchemy version"""
    return version.parse(get_version("SQLAlchemy")) < version.parse(version_string)


def is_graphene_version_less_than(version_string):  # pragma: no cover
    """Check the installed graphene version"""
    return version.parse(get_version("graphene")) < version.parse(version_string)


SQL_VERSION_HIGHER_EQUAL_THAN_1_4 = False

if not is_sqlalchemy_version_less_than("1.4"):  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

    SQL_VERSION_HIGHER_EQUAL_THAN_1_4 = True


SQL_VERSION_HIGHER_EQUAL_THAN_2 = False

if not is_sqlalchemy_version_less_than("2.0.0b1"):  # pragma: no cover
    SQL_VERSION_HIGHER_EQUAL_THAN_2 = True


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
        if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
            return select(model)
        query = session.query(model)
    return query


def is_mapped_class(cls):
    try:
        class_mapper(cls)
    except ArgumentError as error:
        # Only handle ArgumentErrors for non-class objects
        if "Class object expected" in str(error):
            return False
        raise
    except UnmappedClassError:
        # Unmapped classes return false
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


class singledispatchbymatchfunction:
    """
    Inspired by @singledispatch, this is a variant that works using a matcher function
    instead of relying on the type of the first argument.
    The register method can be used to register a new matcher, which is passed as the first argument:
    """

    def __init__(self, default: Callable):
        self.registry: Dict[Callable, Callable] = OrderedDict()
        self.default = default

    def __call__(self, *args, **kwargs):
        matched_arg = args[0]
        try:
            mro = _c3_mro(matched_arg)
        except Exception:
            # In case of tuples or similar types, we can't use the MRO.
            # Fall back to just matching the original argument.
            mro = [matched_arg]

        for cls in mro:
            for matcher_function, final_method in self.registry.items():
                # Register order is important. First one that matches, runs.
                if matcher_function(cls):
                    return final_method(*args, **kwargs)

        # No match, using default.
        return self.default(*args, **kwargs)

    def register(self, matcher_function: Callable[[Any], bool], func=None):
        if func is None:
            return lambda f: self.register(matcher_function, f)
        self.registry[matcher_function] = func
        return func


def column_type_eq(value: Any) -> Callable[[Any], bool]:
    """A simple function that makes the equality based matcher functions for
    SingleDispatchByMatchFunction prettier"""
    return lambda x: (x == value)


def safe_isinstance(cls):
    def safe_isinstance_checker(arg):
        try:
            return isinstance(arg, cls)
        except TypeError:
            pass

    return safe_isinstance_checker


def safe_issubclass(cls):
    def safe_issubclass_checker(arg):
        try:
            return issubclass(arg, cls)
        except TypeError:
            pass

    return safe_issubclass_checker


def registry_sqlalchemy_model_from_str(model_name: str) -> Optional[Any]:
    from graphene_sqlalchemy.registry import get_global_registry

    try:
        return next(
            filter(
                lambda x: x.__name__ == model_name,
                list(get_global_registry()._registry.keys()),
            )
        )
    except StopIteration:
        pass


def is_list(x):
    return getattr(x, "__origin__", None) in [list, typing.List]


class DummyImport:
    """The dummy module returns 'object' for a query for any member"""

    def __getattr__(self, name):
        return object
