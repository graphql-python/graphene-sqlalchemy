import datetime
from functools import singledispatch
from typing import Any

from sqlalchemy import types
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import interfaces, strategies

from graphene import (ID, Boolean, Date, DateTime, Dynamic, Enum, Field, Float,
                      Int, List, String, Time)
from graphene.types.json import JSONString

from .batching import get_batch_resolver
from .enums import enum_for_sa_enum
from .fields import (BatchSQLAlchemyConnectionField,
                     default_connection_field_factory)
from .registry import get_global_registry
from .resolvers import get_attr_resolver, get_custom_resolver
from .utils import singledispatchbymatchfunction, value_equals

try:
    from sqlalchemy_utils import ChoiceType, JSONType, ScalarListType, TSVectorType
except ImportError:
    ChoiceType = JSONType = ScalarListType = TSVectorType = object

try:
    from sqlalchemy_utils.types.choice import EnumTypeImpl
except ImportError:
    EnumTypeImpl = object

is_selectin_available = getattr(strategies, 'SelectInLoader', None)


def get_column_doc(column):
    return getattr(column, "doc", None)


def is_column_nullable(column):
    return bool(getattr(column, "nullable", True))


def convert_sqlalchemy_relationship(relationship_prop, obj_type, connection_field_factory, batching,
                                    orm_field_name, **field_kwargs):
    """
    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param function|None connection_field_factory:
    :param bool batching:
    :param str orm_field_name:
    :param dict field_kwargs:
    :rtype: Dynamic
    """

    def dynamic_type():
        """:rtype: Field|None"""
        direction = relationship_prop.direction
        child_type = obj_type._meta.registry.get_type_for_model(relationship_prop.mapper.entity)
        batching_ = batching if is_selectin_available else False

        if not child_type:
            return None

        if direction == interfaces.MANYTOONE or not relationship_prop.uselist:
            return _convert_o2o_or_m2o_relationship(relationship_prop, obj_type, batching_, orm_field_name,
                                                    **field_kwargs)

        if direction in (interfaces.ONETOMANY, interfaces.MANYTOMANY):
            return _convert_o2m_or_m2m_relationship(relationship_prop, obj_type, batching_,
                                                    connection_field_factory, **field_kwargs)

    return Dynamic(dynamic_type)


def _convert_o2o_or_m2o_relationship(relationship_prop, obj_type, batching, orm_field_name, **field_kwargs):
    """
    Convert one-to-one or many-to-one relationshsip. Return an object field.

    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param bool batching:
    :param str orm_field_name:
    :param dict field_kwargs:
    :rtype: Field
    """
    child_type = obj_type._meta.registry.get_type_for_model(relationship_prop.mapper.entity)

    resolver = get_custom_resolver(obj_type, orm_field_name)
    if resolver is None:
        resolver = get_batch_resolver(relationship_prop) if batching else \
            get_attr_resolver(obj_type, relationship_prop.key)

    return Field(child_type, resolver=resolver, **field_kwargs)


def _convert_o2m_or_m2m_relationship(relationship_prop, obj_type, batching, connection_field_factory, **field_kwargs):
    """
    Convert one-to-many or many-to-many relationshsip. Return a list field or a connection field.

    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param bool batching:
    :param function|None connection_field_factory:
    :param dict field_kwargs:
    :rtype: Field
    """
    child_type = obj_type._meta.registry.get_type_for_model(relationship_prop.mapper.entity)

    if not child_type._meta.connection:
        return Field(List(child_type), **field_kwargs)

    # TODO Allow override of connection_field_factory and resolver via ORMField
    if connection_field_factory is None:
        connection_field_factory = BatchSQLAlchemyConnectionField.from_relationship if batching else \
            default_connection_field_factory

    return connection_field_factory(relationship_prop, obj_type._meta.registry, **field_kwargs)


def convert_sqlalchemy_hybrid_method(hybrid_prop, resolver, **field_kwargs):
    if 'type_' not in field_kwargs:
        field_kwargs['type_'] = convert_hybrid_property_return_type(hybrid_prop)

    return Field(
        resolver=resolver,
        **field_kwargs
    )


def convert_sqlalchemy_composite(composite_prop, registry, resolver):
    converter = registry.get_converter_for_composite(composite_prop.composite_class)
    if not converter:
        try:
            raise Exception(
                "Don't know how to convert the composite field %s (%s)"
                % (composite_prop, composite_prop.composite_class)
            )
        except AttributeError:
            # handle fields that are not attached to a class yet (don't have a parent)
            raise Exception(
                "Don't know how to convert the composite field %r (%s)"
                % (composite_prop, composite_prop.composite_class)
            )

    # TODO Add a way to override composite fields default parameters
    return converter(composite_prop, registry)


def _register_composite_class(cls, registry=None):
    if registry is None:
        from .registry import get_global_registry

        registry = get_global_registry()

    def inner(fn):
        registry.register_composite_converter(cls, fn)

    return inner


convert_sqlalchemy_composite.register = _register_composite_class


def convert_sqlalchemy_column(column_prop, registry, resolver, **field_kwargs):
    column = column_prop.columns[0]

    field_kwargs.setdefault('type_', convert_sqlalchemy_type(getattr(column, "type", None), column, registry))
    field_kwargs.setdefault('required', not is_column_nullable(column))
    field_kwargs.setdefault('description', get_column_doc(column))

    return Field(
        resolver=resolver,
        **field_kwargs
    )


@singledispatch
def convert_sqlalchemy_type(type, column, registry=None):
    raise Exception(
        "Don't know how to convert the SQLAlchemy field %s (%s)"
        % (column, column.__class__)
    )


@convert_sqlalchemy_type.register(types.Date)
@convert_sqlalchemy_type.register(types.Time)
@convert_sqlalchemy_type.register(types.String)
@convert_sqlalchemy_type.register(types.Text)
@convert_sqlalchemy_type.register(types.Unicode)
@convert_sqlalchemy_type.register(types.UnicodeText)
@convert_sqlalchemy_type.register(postgresql.UUID)
@convert_sqlalchemy_type.register(postgresql.INET)
@convert_sqlalchemy_type.register(postgresql.CIDR)
@convert_sqlalchemy_type.register(TSVectorType)
def convert_column_to_string(type, column, registry=None):
    return String


@convert_sqlalchemy_type.register(types.DateTime)
def convert_column_to_datetime(type, column, registry=None):
    from graphene.types.datetime import DateTime
    return DateTime


@convert_sqlalchemy_type.register(types.SmallInteger)
@convert_sqlalchemy_type.register(types.Integer)
def convert_column_to_int_or_id(type, column, registry=None):
    return ID if column.primary_key else Int


@convert_sqlalchemy_type.register(types.Boolean)
def convert_column_to_boolean(type, column, registry=None):
    return Boolean


@convert_sqlalchemy_type.register(types.Float)
@convert_sqlalchemy_type.register(types.Numeric)
@convert_sqlalchemy_type.register(types.BigInteger)
def convert_column_to_float(type, column, registry=None):
    return Float


@convert_sqlalchemy_type.register(types.Enum)
def convert_enum_to_enum(type, column, registry=None):
    return lambda: enum_for_sa_enum(type, registry or get_global_registry())


# TODO Make ChoiceType conversion consistent with other enums
@convert_sqlalchemy_type.register(ChoiceType)
def convert_choice_to_enum(type, column, registry=None):
    name = "{}_{}".format(column.table.name, column.name).upper()
    if isinstance(type.type_impl, EnumTypeImpl):
        # type.choices may be Enum/IntEnum, in ChoiceType both presented as EnumMeta
        # do not use from_enum here because we can have more than one enum column in table
        return Enum(name, list((v.name, v.value) for v in type.choices))
    else:
        return Enum(name, type.choices)


@convert_sqlalchemy_type.register(ScalarListType)
def convert_scalar_list_to_list(type, column, registry=None):
    return List(String)


def init_array_list_recursive(inner_type, n):
    return inner_type if n == 0 else List(init_array_list_recursive(inner_type, n - 1))


@convert_sqlalchemy_type.register(types.ARRAY)
@convert_sqlalchemy_type.register(postgresql.ARRAY)
def convert_array_to_list(_type, column, registry=None):
    inner_type = convert_sqlalchemy_type(column.type.item_type, column)
    return List(init_array_list_recursive(inner_type, (column.type.dimensions or 1) - 1))


@convert_sqlalchemy_type.register(postgresql.HSTORE)
@convert_sqlalchemy_type.register(postgresql.JSON)
@convert_sqlalchemy_type.register(postgresql.JSONB)
def convert_json_to_string(type, column, registry=None):
    return JSONString


@convert_sqlalchemy_type.register(JSONType)
def convert_json_type_to_string(type, column, registry=None):
    return JSONString


@singledispatchbymatchfunction
def convert_hybrid_property_return_type_inner(arg: Any):
    existing_graphql_type = get_global_registry().get_type_for_model(arg)
    if existing_graphql_type:
        return existing_graphql_type
    raise Exception(f"I don't know how to generate a GraphQL type out of a \"{arg}\" type")


@convert_hybrid_property_return_type_inner.register(value_equals(str))
def convert_hybrid_property_return_type_inner_str(arg):
    return String


@convert_hybrid_property_return_type_inner.register(value_equals(int))
def convert_hybrid_property_return_type_inner_int(arg):
    return Int


@convert_hybrid_property_return_type_inner.register(value_equals(float))
def convert_hybrid_property_return_type_inner_float(arg):
    return Float


@convert_hybrid_property_return_type_inner.register(value_equals(bool))
def convert_hybrid_property_return_type_inner_bool(arg):
    return Boolean


@convert_hybrid_property_return_type_inner.register(value_equals(datetime.datetime))
def convert_hybrid_property_return_type_inner_datetime(arg):
    return DateTime


@convert_hybrid_property_return_type_inner.register(value_equals(datetime.date))
def convert_hybrid_property_return_type_inner_date(arg):
    return Date


@convert_hybrid_property_return_type_inner.register(value_equals(datetime.time))
def convert_hybrid_property_return_type_inner_time(arg):
    return Time


@convert_hybrid_property_return_type_inner.register(lambda x: getattr(x, '__origin__', None) == list)
def convert_hybrid_property_return_type_inner_list(arg):
    # type is either list[T] or List[T], generic argument at __args__[0]
    internal_type = arg.__args__[0]

    graphql_internal_type = convert_hybrid_property_return_type_inner(internal_type)

    return List(graphql_internal_type)


def convert_hybrid_property_return_type(hybrid_prop):
    # Grab the original method's return type annotations from inside the hybrid property
    return_type_annotation = hybrid_prop.fget.__annotations__.get('return', str)

    return convert_hybrid_property_return_type_inner(return_type_annotation)
