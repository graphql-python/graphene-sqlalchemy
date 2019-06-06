import logging
from collections import OrderedDict
from functools import partial
from typing import Mapping
from uuid import UUID

from graphene import Argument, InputObjectType, Field, List
from graphene.utils.str_converters import to_snake_case
from graphql import ResolveInfo
from promise import Promise, is_thenable
from sqlalchemy import inspect, func
from sqlalchemy.orm.query import Query

from graphene.relay import Connection, ConnectionField
from graphene.relay.connection import PageInfo
from graphql_relay.connection.arrayconnection import connection_from_list_slice

from graphene_sqlalchemy.converter import convert_sqlalchemy_type
from .utils import get_query

log = logging.getLogger()

argument_cache = {}
field_cache = {}


class UnsortedSQLAlchemyConnectionField(ConnectionField):
    @property
    def type(self, assert_type: bool= True):
        from .types import SQLAlchemyObjectType, SQLAlchemyInputObjectType
        from .interfaces import SQLAlchemyInterface
        _type = super(ConnectionField, self).type
        if issubclass(_type, Connection):
            return _type

        if assert_type:
            assert issubclass(_type, (SQLAlchemyObjectType, SQLAlchemyInterface, SQLAlchemyInputObjectType)), (
                "SQLALchemyConnectionField only accepts {} types, not {}"
            ).format([x.__name__ for x in (SQLAlchemyObjectType, SQLAlchemyInterface, SQLAlchemyInputObjectType)], _type.__name__)
        assert _type._meta.connection\
            , "The type {} doesn't have a connection".format(
            _type.__name__
        )
        return _type._meta.connection

    @property
    def model(self):
        return self.type._meta.node._meta.model

    @classmethod
    def get_query(cls, model, info, sort=None, **args):
        query = get_query(model, info.context)
        if sort is not None:
            if isinstance(sort, str):
                query = query.order_by(sort.value)
            else:
                query = query.order_by(*(col.value for col in sort))
        return query

    @classmethod
    def resolve_connection(cls, connection_type, model, info, args, resolved):
        if resolved is None:
            resolved = cls.get_query(model, info, **args)
        if isinstance(resolved, Query):
            _len = resolved.count()
        else:
            _len = len(resolved)
        connection = connection_from_list_slice(
            resolved,
            args,
            slice_start=0,
            list_length=_len,
            list_slice_length=_len,
            connection_type=connection_type,
            pageinfo_type=PageInfo,
            edge_type=connection_type.Edge,
        )
        connection.iterable = resolved
        connection.length = _len
        return connection

    @classmethod
    def connection_resolver(cls, resolver, connection_type, model, root, info, **args):
        resolved = resolver(root, info, **args)

        on_resolve = partial(cls.resolve_connection, connection_type, model, info, args)
        if is_thenable(resolved):
            return Promise.resolve(resolved).then(on_resolve)

        return on_resolve(resolved)

    def get_resolver(self, parent_resolver):
        return partial(self.connection_resolver, parent_resolver, self.type, self.model)


class SQLAlchemyConnectionField(UnsortedSQLAlchemyConnectionField):
    def __init__(self, type, *args, **kwargs):
        if "sort" not in kwargs and issubclass(type, Connection):
            # Let super class raise if type is not a Connection
            try:
                kwargs.setdefault("sort", type.Edge.node._type.sort_argument())
            except (AttributeError, TypeError):
                raise TypeError(
                    'Cannot create sort argument for {}. A model is required. Set the "sort" argument'
                    " to None to disabling the creation of the sort query argument".format(
                        type.__name__
                    )
                )
        elif "sort" in kwargs and kwargs["sort"] is None:
            del kwargs["sort"]
        super(SQLAlchemyConnectionField, self).__init__(type, *args, **kwargs)


class FilterArgument:
    pass


class FilterField:
    pass


def create_filter_argument(cls):
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

def filter_query(query, model, field, value):
    if isinstance(value, Mapping):
        [(operator, value)] = value.items()
        # does not work on UUID columns
        if operator is "equal":
            query = query.filter(getattr(model, field) == value)
        elif operator is "notEqual":
            query = query.filter(getattr(model, field) != value)
        elif operator is "lessThan":
            query = query.filter(getattr(model, field) < value)
        elif operator is "greaterThan":
            query = query.filter(getattr(model, field) > value)
        elif operator is "like":
            query = query.filter(func.lower(getattr(model, field)).like(func.lower(f'%{value}%')))
        elif operator is "in":
            query = query.filter(getattr(model, field).in_(value))
    elif isinstance(value, (str, int, UUID)):
        query = query.filter(getattr(model, field) == value)
    else:
        raise NotImplementedError(f'Filter for value type {type(value)} for {field} of model {model} is not implemented')
    return query


def create_filter_field(column):
    graphene_type = convert_sqlalchemy_type(column.type, column)
    if graphene_type.__class__ == Field:
        return None

    name = "{}Filter".format(str(graphene_type.__class__))
    if name in field_cache:
        return Field(field_cache[name])

    fields = OrderedDict((key, Field(graphene_type.__class__))
                         for key in ["equal", "notEqual", "lessThan", "greaterThan", "like"])
    fields['in'] = Field(List(graphene_type.__class__))
    field_class: InputObjectType = type(name, (FilterField, InputObjectType), {})
    field_class._meta.fields.update(fields)

    field_cache[name] = field_class
    return Field(field_class)


class SQLAlchemyFilteredConnectionField(SQLAlchemyConnectionField):
    def __init__(self, type_, *args, **kwargs):
        model = type_._meta.model
        kwargs.setdefault("filter", create_filter_argument(model))
        super(SQLAlchemyFilteredConnectionField, self).__init__(type_, *args, **kwargs)

    @classmethod
    def get_query(cls, model, info: ResolveInfo, filter=None, sort=None, group_by=None, order_by=None, **kwargs):
        query = super().get_query(model, info, sort=None, **kwargs)
        # columns = inspect(model).columns.values()
        from graphene_sqlalchemy.types import SQLAlchemyInputObjectType

        for filter_name, filter_value in kwargs.items():
            model_filter_column = getattr(model, filter_name, None)
            if not model_filter_column:
                continue
            if isinstance(filter_value, SQLAlchemyInputObjectType):
                filter_model = filter_value.sqla_model
                q = super().get_query(filter_model, info, sort=None, **kwargs)
                # noinspection PyArgumentList
                query.filter(model_filter_column == q.filter_by(**filter_value).one())
        if filter:
            for filter_name, filter_value in filter.items():
                query = filter_query(query, model, filter_name, filter_value)
        return query

    @classmethod
    def resolve_connection(cls, connection_type, model, info, args, resolved):
        filters = args.get("filter", {})
        field = getattr(info.schema._query, to_snake_case(info.field_name))
        if field and hasattr(field, 'required') and field.required:
            required_filters = [rf.key for rf in field.required]

            if required_filters:
                missing_filters = set(required_filters) - set(filters.keys())
                if missing_filters:
                    raise Exception(missing_filters)

        return super(SQLAlchemyFilteredConnectionField, cls).resolve_connection(
            connection_type, model, info, args, resolved)


def default_connection_field_factory(relationship, registry):
    model = relationship.mapper.entity
    model_type = registry.get_type_for_model(model)
    return createConnectionField(model_type)


# TODO Remove in next major version
__connectionFactory = UnsortedSQLAlchemyConnectionField


def createConnectionField(_type):
    log.warning(
        'createConnectionField is deprecated and will be removed in the next '
        'major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.'
    )
    return __connectionFactory(_type)


def registerConnectionFieldFactory(factoryMethod):
    log.warning(
        'registerConnectionFieldFactory is deprecated and will be removed in the next '
        'major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.'
    )
    global __connectionFactory
    __connectionFactory = factoryMethod


def unregisterConnectionFieldFactory():
    log.warning(
        'registerConnectionFieldFactory is deprecated and will be removed in the next '
        'major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.'
    )
    global __connectionFactory
    __connectionFactory = UnsortedSQLAlchemyConnectionField
