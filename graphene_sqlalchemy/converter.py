import datetime
import sys
import typing
import uuid
from decimal import Decimal
from typing import Any, Optional, Union, cast

from sqlalchemy import types as sqa_types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import interfaces, strategies

import graphene
from graphene.types.json import JSONString

from .batching import get_batch_resolver
from .enums import enum_for_sa_enum
from .fields import BatchSQLAlchemyConnectionField, default_connection_field_factory
from .registry import Registry, get_global_registry
from .resolvers import get_attr_resolver, get_custom_resolver
from .utils import (
    DummyImport,
    registry_sqlalchemy_model_from_str,
    safe_isinstance,
    singledispatchbymatchfunction,
    value_equals,
    value_equals_strict,
)

# We just use MapperProperties for type hints, they don't exist in sqlalchemy < 1.4
try:
    from sqlalchemy import MapperProperty
except ImportError:
    # sqlalchemy < 1.4
    MapperProperty = Any

try:
    from typing import ForwardRef
except ImportError:
    # python 3.6
    from typing import _ForwardRef as ForwardRef

try:
    from sqlalchemy_utils.types.choice import EnumTypeImpl
except ImportError:
    EnumTypeImpl = object

try:
    import sqlalchemy_utils as sqa_utils
except ImportError:
    sqa_utils = DummyImport()

is_selectin_available = getattr(strategies, "SelectInLoader", None)


def get_column_doc(column):
    return getattr(column, "doc", None)


def is_column_nullable(column):
    return bool(getattr(column, "nullable", True))


def convert_sqlalchemy_relationship(
    relationship_prop,
    obj_type,
    connection_field_factory,
    batching,
    orm_field_name,
    **field_kwargs,
):
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
        child_type = obj_type._meta.registry.get_type_for_model(
            relationship_prop.mapper.entity
        )
        batching_ = batching if is_selectin_available else False

        if not child_type:
            return None

        if direction == interfaces.MANYTOONE or not relationship_prop.uselist:
            return _convert_o2o_or_m2o_relationship(
                relationship_prop, obj_type, batching_, orm_field_name, **field_kwargs
            )

        if direction in (interfaces.ONETOMANY, interfaces.MANYTOMANY):
            return _convert_o2m_or_m2m_relationship(
                relationship_prop,
                obj_type,
                batching_,
                connection_field_factory,
                **field_kwargs,
            )

    return graphene.Dynamic(dynamic_type)


def _convert_o2o_or_m2o_relationship(
    relationship_prop, obj_type, batching, orm_field_name, **field_kwargs
):
    """
    Convert one-to-one or many-to-one relationshsip. Return an object field.

    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param bool batching:
    :param str orm_field_name:
    :param dict field_kwargs:
    :rtype: Field
    """
    child_type = obj_type._meta.registry.get_type_for_model(
        relationship_prop.mapper.entity
    )

    resolver = get_custom_resolver(obj_type, orm_field_name)
    if resolver is None:
        resolver = (
            get_batch_resolver(relationship_prop)
            if batching
            else get_attr_resolver(obj_type, relationship_prop.key)
        )

    return graphene.Field(child_type, resolver=resolver, **field_kwargs)


def _convert_o2m_or_m2m_relationship(
    relationship_prop, obj_type, batching, connection_field_factory, **field_kwargs
):
    """
    Convert one-to-many or many-to-many relationshsip. Return a list field or a connection field.

    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param bool batching:
    :param function|None connection_field_factory:
    :param dict field_kwargs:
    :rtype: Field
    """
    child_type = obj_type._meta.registry.get_type_for_model(
        relationship_prop.mapper.entity
    )

    if not child_type._meta.connection:
        return graphene.Field(graphene.List(child_type), **field_kwargs)

    # TODO Allow override of connection_field_factory and resolver via ORMField
    if connection_field_factory is None:
        connection_field_factory = (
            BatchSQLAlchemyConnectionField.from_relationship
            if batching
            else default_connection_field_factory
        )

    return connection_field_factory(
        relationship_prop, obj_type._meta.registry, **field_kwargs
    )


def convert_sqlalchemy_hybrid_method(hybrid_prop, resolver, **field_kwargs):
    if "type_" not in field_kwargs:
        field_kwargs["type_"] = convert_hybrid_property_return_type(hybrid_prop)

    if "description" not in field_kwargs:
        field_kwargs["description"] = getattr(hybrid_prop, "__doc__", None)

    return graphene.Field(resolver=resolver, **field_kwargs)


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

    field_kwargs.setdefault(
        "type_",
        convert_sqlalchemy_type(
            getattr(column, "type", None), column=column, registry=registry
        ),
    )
    field_kwargs.setdefault("required", not is_column_nullable(column))
    field_kwargs.setdefault("description", get_column_doc(column))

    return graphene.Field(resolver=resolver, **field_kwargs)


@singledispatchbymatchfunction
def convert_sqlalchemy_type(
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    existing_graphql_type = get_global_registry().get_type_for_model(type_arg)
    if existing_graphql_type:
        return existing_graphql_type

    if isinstance(type_arg, type(graphene.ObjectType)):
        return type_arg

    if isinstance(type_arg, type(graphene.Scalar)):
        return type_arg

    # No valid type found, warn and fall back to graphene.String
    raise Exception(
        "Don't know how to convert the SQLAlchemy field %s (%s, %s)"
        % (column, column.__class__ or "no column provided", type_arg)
    )


@convert_sqlalchemy_type.register(value_equals_strict(str))
@convert_sqlalchemy_type.register(value_equals(sqa_types.String))
@convert_sqlalchemy_type.register(value_equals(sqa_types.Text))
@convert_sqlalchemy_type.register(value_equals(sqa_types.Unicode))
@convert_sqlalchemy_type.register(value_equals(sqa_types.UnicodeText))
@convert_sqlalchemy_type.register(value_equals(postgresql.INET))
@convert_sqlalchemy_type.register(value_equals(postgresql.CIDR))
@convert_sqlalchemy_type.register(value_equals(sqa_utils.TSVectorType))
@convert_sqlalchemy_type.register(value_equals(sqa_utils.EmailType))
@convert_sqlalchemy_type.register(value_equals(sqa_utils.URLType))
@convert_sqlalchemy_type.register(value_equals(sqa_utils.IPAddressType))
def convert_column_to_string(type_arg: Any, **kwargs):
    return graphene.String


@convert_sqlalchemy_type.register(value_equals(postgresql.UUID))
@convert_sqlalchemy_type.register(value_equals(sqa_utils.UUIDType))
@convert_sqlalchemy_type.register(value_equals(uuid.UUID))
def convert_column_to_uuid(
    type_arg: Any,
    **kwargs,
):
    return graphene.UUID


@convert_sqlalchemy_type.register(value_equals(sqa_types.DateTime))
@convert_sqlalchemy_type.register(value_equals(datetime.datetime))
def convert_column_to_datetime(
    type_arg: Any,
    **kwargs,
):
    return graphene.DateTime


@convert_sqlalchemy_type.register(value_equals(sqa_types.Time))
@convert_sqlalchemy_type.register(value_equals(datetime.time))
def convert_column_to_time(
    type_arg: Any,
    **kwargs,
):
    return graphene.Time


@convert_sqlalchemy_type.register(value_equals(sqa_types.Date))
@convert_sqlalchemy_type.register(value_equals(datetime.date))
def convert_column_to_date(
    type_arg: Any,
    **kwargs,
):
    return graphene.Date


@convert_sqlalchemy_type.register(value_equals(sqa_types.SmallInteger))
@convert_sqlalchemy_type.register(value_equals(sqa_types.Integer))
@convert_sqlalchemy_type.register(value_equals_strict(int))
def convert_column_to_int_or_id(
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    return (
        graphene.ID if (column is not None) and column.primary_key else graphene.Int
    )  # fixme drop the primary key processing in another pr


@convert_sqlalchemy_type.register(value_equals(sqa_types.Boolean))
@convert_sqlalchemy_type.register(value_equals_strict(bool))
def convert_column_to_boolean(
    type_arg: Any,
    **kwargs,
):
    return graphene.Boolean


@convert_sqlalchemy_type.register(value_equals_strict(float))
@convert_sqlalchemy_type.register(value_equals(sqa_types.Float))
@convert_sqlalchemy_type.register(value_equals(sqa_types.Numeric))
@convert_sqlalchemy_type.register(value_equals(sqa_types.BigInteger))
def convert_column_to_float(
    type_arg: Any,
    **kwargs,
):
    return graphene.Float


@convert_sqlalchemy_type.register(value_equals(postgresql.ENUM))
@convert_sqlalchemy_type.register(value_equals(sqa_types.Enum))
def convert_enum_to_enum(
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    return lambda: enum_for_sa_enum(type_arg, registry or get_global_registry())


# TODO Make ChoiceType conversion consistent with other enums
@convert_sqlalchemy_type.register(value_equals(sqa_utils.ChoiceType))
def convert_choice_to_enum(
    type_arg: sqa_utils.ChoiceType,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
):
    name = "{}_{}".format(column.table.name, column.key).upper()
    if isinstance(type_arg.type_impl, EnumTypeImpl):
        # type.choices may be Enum/IntEnum, in ChoiceType both presented as EnumMeta
        # do not use from_enum here because we can have more than one enum column in table
        return graphene.Enum(name, list((v.name, v.value) for v in type_arg.choices))
    else:
        return graphene.Enum(name, type_arg.choices)


@convert_sqlalchemy_type.register(value_equals(sqa_utils.ScalarListType))
def convert_scalar_list_to_list(
    type_arg: Any,
    **kwargs,
):
    return graphene.List(graphene.String)


def init_array_list_recursive(inner_type, n):
    return (
        inner_type
        if n == 0
        else graphene.List(init_array_list_recursive(inner_type, n - 1))
    )


@convert_sqlalchemy_type.register(value_equals(sqa_types.ARRAY))
@convert_sqlalchemy_type.register(value_equals(postgresql.ARRAY))
def convert_array_to_list(
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    inner_type = convert_sqlalchemy_type(
        column.type.item_type, column=column, registry=registry, **kwargs
    )
    return graphene.List(
        init_array_list_recursive(inner_type, (column.type.dimensions or 1) - 1)
    )


@convert_sqlalchemy_type.register(value_equals(postgresql.HSTORE))
@convert_sqlalchemy_type.register(value_equals(postgresql.JSON))
@convert_sqlalchemy_type.register(value_equals(postgresql.JSONB))
def convert_json_to_string(
    type_arg: Any,
    **kwargs,
):
    return JSONString


@convert_sqlalchemy_type.register(value_equals(sqa_utils.JSONType))
@convert_sqlalchemy_type.register(value_equals(sqa_types.JSON))
def convert_json_type_to_string(
    type_arg: Any,
    **kwargs,
):
    return JSONString


@convert_sqlalchemy_type.register(value_equals(sqa_types.Variant))
def convert_variant_to_impl_type(
    type_arg: sqa_types.Variant,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    return convert_sqlalchemy_type(
        type_arg.impl, column=column, registry=registry, **kwargs
    )


@convert_sqlalchemy_type.register(value_equals_strict(Decimal))
def convert_sqlalchemy_hybrid_property_type_decimal(type_arg: Any, **kwargs):
    # The reason Decimal should be serialized as a String is because this is a
    # base10 type used in things like money, and string allows it to not
    # lose precision (which would happen if we downcasted to a Float, for example)
    return graphene.String


def is_union(type_arg: Any, **kwargs) -> bool:
    if sys.version_info >= (3, 10):
        from types import UnionType

        if isinstance(type_arg, UnionType):
            return True
    return getattr(type_arg, "__origin__", None) == typing.Union


def graphene_union_for_py_union(
    obj_types: typing.List[graphene.ObjectType], registry
) -> graphene.Union:
    union_type = registry.get_union_for_object_types(obj_types)

    if union_type is None:
        # Union Name is name of the three
        union_name = "".join(sorted(obj_type._meta.name for obj_type in obj_types))
        union_type = graphene.Union.create_type(union_name, types=obj_types)
        registry.register_union_type(union_type, obj_types)

    return union_type


@convert_sqlalchemy_type.register(is_union)
def convert_sqlalchemy_hybrid_property_union(type_arg: Any, **kwargs):
    """
    Converts Unions (Union[X,Y], or X | Y for python > 3.10) to the corresponding graphene schema object.
    Since Optionals are internally represented as Union[T, <class NoneType>], they are handled here as well.

    The GQL Spec currently only allows for ObjectType unions:
    GraphQL Unions represent an object that could be one of a list of GraphQL Object types, but provides for no
    guaranteed fields between those types.
    That's why we have to check for the nested types to be instances of graphene.ObjectType, except for the union case.

    type(x) == _types.UnionType is necessary to support X | Y notation, but might break in future python releases.
    """
    from .registry import get_global_registry

    # Option is actually Union[T, <class NoneType>]
    # Just get the T out of the list of arguments by filtering out the NoneType
    nested_types = list(filter(lambda x: not type(None) == x, type_arg.__args__))

    # Map the graphene types to the nested types.
    # We use convert_sqlalchemy_hybrid_property_type instead of the registry to account for ForwardRefs, Lists,...
    graphene_types = list(map(convert_sqlalchemy_type, nested_types))

    # If only one type is left after filtering out NoneType, the Union was an Optional
    if len(graphene_types) == 1:
        return graphene_types[0]

    # Now check if every type is instance of an ObjectType
    if not all(
        isinstance(graphene_type, type(graphene.ObjectType))
        for graphene_type in graphene_types
    ):
        raise ValueError(
            "Cannot convert hybrid_property Union to graphene.Union: the Union contains scalars. "
            "Please add the corresponding hybrid_property to the excluded fields in the ObjectType, "
            "or use an ORMField to override this behaviour."
        )

    return graphene_union_for_py_union(
        cast(typing.List[graphene.ObjectType], list(graphene_types)),
        get_global_registry(),
    )


@convert_sqlalchemy_type.register(
    lambda x: getattr(x, "__origin__", None) in [list, typing.List]
)
def convert_sqlalchemy_hybrid_property_type_list_t(type_arg: Any, **kwargs):
    # type is either list[T] or List[T], generic argument at __args__[0]
    internal_type = type_arg.__args__[0]

    graphql_internal_type = convert_sqlalchemy_type(internal_type, **kwargs)

    return graphene.List(graphql_internal_type)


@convert_sqlalchemy_type.register(safe_isinstance(ForwardRef))
def convert_sqlalchemy_hybrid_property_forwardref(type_arg: Any, **kwargs):
    """
    Generate a lambda that will resolve the type at runtime
    This takes care of self-references
    """
    from .registry import get_global_registry

    def forward_reference_solver():
        model = registry_sqlalchemy_model_from_str(type_arg.__forward_arg__)
        if not model:
            return graphene.String
        # Always fall back to string if no ForwardRef type found.
        return get_global_registry().get_type_for_model(model)

    return forward_reference_solver


@convert_sqlalchemy_type.register(safe_isinstance(str))
def convert_sqlalchemy_hybrid_property_bare_str(type_arg: str, **kwargs):
    """
    Convert Bare String into a ForwardRef
    """

    return convert_sqlalchemy_type(ForwardRef(type_arg), **kwargs)


def convert_hybrid_property_return_type(hybrid_prop):
    # Grab the original method's return type annotations from inside the hybrid property
    return_type_annotation = hybrid_prop.fget.__annotations__.get("return", str)

    return convert_sqlalchemy_type(return_type_annotation)
