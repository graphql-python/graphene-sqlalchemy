import datetime
import sys
import typing
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional, TypeVar, Union, cast

from sqlalchemy import types as sqa_types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    ColumnProperty,
    RelationshipProperty,
    class_mapper,
    interfaces,
    strategies,
)

import graphene
from graphene.types.json import JSONString

from .batching import get_batch_resolver
from .enums import enum_for_sa_enum
from .registry import Registry, get_global_registry
from .resolvers import get_attr_resolver, get_custom_resolver
from .utils import (
    SQL_VERSION_HIGHER_EQUAL_THAN_1_4,
    DummyImport,
    column_type_eq,
    registry_sqlalchemy_model_from_str,
    safe_isinstance,
    safe_issubclass,
    singledispatchbymatchfunction,
)

# Import path changed in 1.4
if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
    from sqlalchemy.orm import DeclarativeMeta
else:
    from sqlalchemy.ext.declarative import DeclarativeMeta

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

"""
Flag for whether to generate stricter non-null fields for many-relationships.

For many-relationships, both the list element and the list field itself will be
non-null by default. This better matches ORM semantics, where there is always a
list for a many relationship (even if it is empty), and it never contains None.

This option can be set to False to revert to pre-3.0 behavior.

For example, given a User model with many Comments:

    class User(Base):
        comments = relationship("Comment")

The Schema will be:

    type User {
        comments: [Comment!]!
    }

When set to False, the pre-3.0 behavior gives:

    type User {
        comments: [Comment]
    }
"""
use_non_null_many_relationships = True


def set_non_null_many_relationships(non_null_flag):
    global use_non_null_many_relationships
    use_non_null_many_relationships = non_null_flag


def get_column_doc(column):
    return getattr(column, "doc", None)


def is_column_nullable(column):
    return bool(getattr(column, "nullable", True))


def convert_sqlalchemy_association_proxy(
    parent,
    assoc_prop,
    obj_type,
    registry,
    connection_field_factory,
    batching,
    resolver,
    **field_kwargs,
):
    def dynamic_type():
        prop = class_mapper(parent).attrs[assoc_prop.target_collection]
        scalar = not prop.uselist
        model = prop.mapper.class_
        attr = class_mapper(model).attrs[assoc_prop.value_attr]

        if isinstance(attr, ColumnProperty):
            field = convert_sqlalchemy_column(attr, registry, resolver, **field_kwargs)
            if not scalar:
                # repackage as List
                field.__dict__["_type"] = graphene.List(field.type)
            return field
        elif isinstance(attr, RelationshipProperty):
            return convert_sqlalchemy_relationship(
                attr,
                obj_type,
                connection_field_factory,
                field_kwargs.pop("batching", batching),
                assoc_prop.value_attr,
                **field_kwargs,
            ).get_type()
        else:
            raise TypeError(
                "Unsupported association proxy target type: {} for prop {} on type {}. "
                "Please disable the conversion of this field using an ORMField.".format(
                    type(attr), assoc_prop, obj_type
                )
            )
        # else, not supported

    return graphene.Dynamic(dynamic_type)


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
    from .fields import BatchSQLAlchemyConnectionField, default_connection_field_factory

    child_type = obj_type._meta.registry.get_type_for_model(
        relationship_prop.mapper.entity
    )

    if not child_type._meta.connection:
        # check if we need to use non-null fields
        list_type = (
            graphene.NonNull(graphene.List(graphene.NonNull(child_type)))
            if use_non_null_many_relationships
            else graphene.List(child_type)
        )

        return graphene.Field(list_type, **field_kwargs)

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
    # The converter expects a type to find the right conversion function.
    # If we get an instance instead, we need to convert it to a type.
    # The conversion function will still be able to access the instance via the column argument.
    if "type_" not in field_kwargs:
        column_type = getattr(column, "type", None)
        if not isinstance(column_type, type):
            column_type = type(column_type)
        field_kwargs.setdefault(
            "type_",
            convert_sqlalchemy_type(column_type, column=column, registry=registry),
        )
    field_kwargs.setdefault("required", not is_column_nullable(column))
    field_kwargs.setdefault("description", get_column_doc(column))

    return graphene.Field(resolver=resolver, **field_kwargs)


@singledispatchbymatchfunction
def convert_sqlalchemy_type(  # noqa
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    replace_type_vars: typing.Dict[str, Any] = None,
    **kwargs,
):
    if replace_type_vars and type_arg in replace_type_vars:
        return replace_type_vars[type_arg]

    # No valid type found, raise an error

    raise TypeError(
        "Don't know how to convert the SQLAlchemy field %s (%s, %s). "
        "Please add a type converter or set the type manually using ORMField(type_=your_type)"
        % (column, column.__class__ or "no column provided", type_arg)
    )


@convert_sqlalchemy_type.register(safe_isinstance(DeclarativeMeta))
def convert_sqlalchemy_model_using_registry(
    type_arg: Any, registry: Registry = None, **kwargs
):
    registry_ = registry or get_global_registry()

    def get_type_from_registry():
        existing_graphql_type = registry_.get_type_for_model(type_arg)
        if existing_graphql_type:
            return existing_graphql_type

        raise TypeError(
            "No model found in Registry for type %s. "
            "Only references to SQLAlchemy Models mapped to "
            "SQLAlchemyObjectTypes are allowed." % type_arg
        )

    return get_type_from_registry()


@convert_sqlalchemy_type.register(safe_issubclass(graphene.ObjectType))
def convert_object_type(type_arg: Any, **kwargs):
    return type_arg


@convert_sqlalchemy_type.register(safe_issubclass(graphene.Scalar))
def convert_scalar_type(type_arg: Any, **kwargs):
    return type_arg


@convert_sqlalchemy_type.register(safe_isinstance(TypeVar))
def convert_type_var(type_arg: Any, replace_type_vars: Dict[TypeVar, Any], **kwargs):
    return replace_type_vars[type_arg]


@convert_sqlalchemy_type.register(column_type_eq(str))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.String))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Text))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Unicode))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.UnicodeText))
@convert_sqlalchemy_type.register(column_type_eq(postgresql.INET))
@convert_sqlalchemy_type.register(column_type_eq(postgresql.CIDR))
@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.TSVectorType))
@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.EmailType))
@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.URLType))
@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.IPAddressType))
def convert_column_to_string(type_arg: Any, **kwargs):
    return graphene.String


@convert_sqlalchemy_type.register(column_type_eq(postgresql.UUID))
@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.UUIDType))
@convert_sqlalchemy_type.register(column_type_eq(uuid.UUID))
def convert_column_to_uuid(
    type_arg: Any,
    **kwargs,
):
    return graphene.UUID


@convert_sqlalchemy_type.register(column_type_eq(sqa_types.DateTime))
@convert_sqlalchemy_type.register(column_type_eq(datetime.datetime))
def convert_column_to_datetime(
    type_arg: Any,
    **kwargs,
):
    return graphene.DateTime


@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Time))
@convert_sqlalchemy_type.register(column_type_eq(datetime.time))
def convert_column_to_time(
    type_arg: Any,
    **kwargs,
):
    return graphene.Time


@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Date))
@convert_sqlalchemy_type.register(column_type_eq(datetime.date))
def convert_column_to_date(
    type_arg: Any,
    **kwargs,
):
    return graphene.Date


@convert_sqlalchemy_type.register(column_type_eq(sqa_types.SmallInteger))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Integer))
@convert_sqlalchemy_type.register(column_type_eq(int))
def convert_column_to_int_or_id(
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    # fixme drop the primary key processing from here in another pr
    if column is not None:
        if getattr(column, "primary_key", False) is True:
            return graphene.ID
    return graphene.Int


@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Boolean))
@convert_sqlalchemy_type.register(column_type_eq(bool))
def convert_column_to_boolean(
    type_arg: Any,
    **kwargs,
):
    return graphene.Boolean


@convert_sqlalchemy_type.register(column_type_eq(float))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Float))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Numeric))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.BigInteger))
def convert_column_to_float(
    type_arg: Any,
    **kwargs,
):
    return graphene.Float


@convert_sqlalchemy_type.register(column_type_eq(postgresql.ENUM))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Enum))
def convert_enum_to_enum(
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    if column is None or isinstance(column, hybrid_property):
        raise Exception("SQL-Enum conversion requires a column")

    return lambda: enum_for_sa_enum(column.type, registry or get_global_registry())


# TODO Make ChoiceType conversion consistent with other enums
@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.ChoiceType))
def convert_choice_to_enum(
    type_arg: sqa_utils.ChoiceType,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    **kwargs,
):
    if column is None or isinstance(column, hybrid_property):
        raise Exception("ChoiceType conversion requires a column")

    name = "{}_{}".format(column.table.name, column.key).upper()
    if isinstance(column.type.type_impl, EnumTypeImpl):
        # type.choices may be Enum/IntEnum, in ChoiceType both presented as EnumMeta
        # do not use from_enum here because we can have more than one enum column in table
        return graphene.Enum(name, list((v.name, v.value) for v in column.type.choices))
    else:
        return graphene.Enum(name, column.type.choices)


@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.ScalarListType))
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


@convert_sqlalchemy_type.register(column_type_eq(sqa_types.ARRAY))
@convert_sqlalchemy_type.register(column_type_eq(postgresql.ARRAY))
def convert_array_to_list(
    type_arg: Any,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    if column is None or isinstance(column, hybrid_property):
        raise Exception("SQL-Array conversion requires a column")
    item_type = column.type.item_type
    if not isinstance(item_type, type):
        item_type = type(item_type)
    inner_type = convert_sqlalchemy_type(
        item_type, column=column, registry=registry, **kwargs
    )
    return graphene.List(
        init_array_list_recursive(inner_type, (column.type.dimensions or 1) - 1)
    )


@convert_sqlalchemy_type.register(column_type_eq(postgresql.HSTORE))
@convert_sqlalchemy_type.register(column_type_eq(postgresql.JSON))
@convert_sqlalchemy_type.register(column_type_eq(postgresql.JSONB))
def convert_json_to_string(
    type_arg: Any,
    **kwargs,
):
    return JSONString


@convert_sqlalchemy_type.register(column_type_eq(sqa_utils.JSONType))
@convert_sqlalchemy_type.register(column_type_eq(sqa_types.JSON))
def convert_json_type_to_string(
    type_arg: Any,
    **kwargs,
):
    return JSONString


@convert_sqlalchemy_type.register(column_type_eq(sqa_types.Variant))
def convert_variant_to_impl_type(
    type_arg: sqa_types.Variant,
    column: Optional[Union[MapperProperty, hybrid_property]] = None,
    registry: Registry = None,
    **kwargs,
):
    if column is None or isinstance(column, hybrid_property):
        raise Exception("Vaiant conversion requires a column")

    type_impl = column.type.impl
    if not isinstance(type_impl, type):
        type_impl = type(type_impl)
    return convert_sqlalchemy_type(
        type_impl, column=column, registry=registry, **kwargs
    )


@convert_sqlalchemy_type.register(column_type_eq(Decimal))
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

    # TODO redo this for , *args, **kwargs
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
            raise TypeError(
                "No model found in Registry for forward reference for type %s. "
                "Only forward references to other SQLAlchemy Models mapped to "
                "SQLAlchemyObjectTypes are allowed." % type_arg
            )
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
    return_type_annotation = hybrid_prop.fget.__annotations__.get("return", None)
    if not return_type_annotation:
        raise TypeError(
            "Cannot convert hybrid property type {} to a valid graphene type. "
            "Please make sure to annotate the return type of the hybrid property or use the "
            "type_ attribute of ORMField to set the type.".format(hybrid_prop)
        )

    return convert_sqlalchemy_type(return_type_annotation, column=hybrid_prop)
