import warnings
from functools import partial

import six
from promise import Promise, is_thenable
from sqlalchemy.orm.query import Query

from graphene import NonNull
from graphene.relay import Connection, ConnectionField
from graphene.relay.connection import PageInfo
from graphql_relay.connection.arrayconnection import connection_from_list_slice

from .batching import get_batch_resolver
from .utils import get_query


class UnsortedSQLAlchemyConnectionField(ConnectionField):
    @property
    def type(self):
        from .types import SQLAlchemyObjectType

        _type = super(ConnectionField, self).type
        nullable_type = get_nullable_type(_type)
        if issubclass(nullable_type, Connection):
            return _type
        assert issubclass(nullable_type, SQLAlchemyObjectType), (
            "SQLALchemyConnectionField only accepts SQLAlchemyObjectType types, not {}"
        ).format(nullable_type.__name__)
        assert (
            nullable_type.connection
        ), "The type {} doesn't have a connection".format(
            nullable_type.__name__
        )
        assert _type == nullable_type, (
            "Passing a SQLAlchemyObjectType instance is deprecated. "
            "Pass the connection type instead accessible via SQLAlchemyObjectType.connection"
        )
        return nullable_type.connection

    @property
    def model(self):
        return get_nullable_type(self.type)._meta.node._meta.model

    @classmethod
    def get_query(cls, model, info, **args):
        return get_query(model, info.context)

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
        return partial(
            self.connection_resolver,
            parent_resolver,
            get_nullable_type(self.type),
            self.model,
        )


# TODO Rename this to SortableSQLAlchemyConnectionField
class SQLAlchemyConnectionField(UnsortedSQLAlchemyConnectionField):
    def __init__(self, type, *args, **kwargs):
        nullable_type = get_nullable_type(type)
        if "sort" not in kwargs and issubclass(nullable_type, Connection):
            # Let super class raise if type is not a Connection
            try:
                kwargs.setdefault("sort", nullable_type.Edge.node._type.sort_argument())
            except (AttributeError, TypeError):
                raise TypeError(
                    'Cannot create sort argument for {}. A model is required. Set the "sort" argument'
                    " to None to disabling the creation of the sort query argument".format(
                        nullable_type.__name__
                    )
                )
        elif "sort" in kwargs and kwargs["sort"] is None:
            del kwargs["sort"]
        super(SQLAlchemyConnectionField, self).__init__(type, *args, **kwargs)

    @classmethod
    def get_query(cls, model, info, sort=None, **args):
        query = get_query(model, info.context)
        if sort is not None:
            if isinstance(sort, six.string_types):
                query = query.order_by(sort.value)
            else:
                query = query.order_by(*(col.value for col in sort))
        return query


class BatchSQLAlchemyConnectionField(UnsortedSQLAlchemyConnectionField):
    """
    This is currently experimental.
    The API and behavior may change in future versions.
    Use at your own risk.
    """

    def get_resolver(self, parent_resolver):
        return partial(
            self.connection_resolver,
            self.resolver,
            get_nullable_type(self.type),
            self.model,
        )

    @classmethod
    def from_relationship(cls, relationship, registry, **field_kwargs):
        model = relationship.mapper.entity
        model_type = registry.get_type_for_model(model)
        return cls(model_type.connection, resolver=get_batch_resolver(relationship), **field_kwargs)


def default_connection_field_factory(relationship, registry, **field_kwargs):
    model = relationship.mapper.entity
    model_type = registry.get_type_for_model(model)
    return __connectionFactory(model_type, **field_kwargs)


# TODO Remove in next major version
__connectionFactory = UnsortedSQLAlchemyConnectionField


def createConnectionField(_type, **field_kwargs):
    warnings.warn(
        'createConnectionField is deprecated and will be removed in the next '
        'major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.',
        DeprecationWarning,
    )
    return __connectionFactory(_type, **field_kwargs)


def registerConnectionFieldFactory(factoryMethod):
    warnings.warn(
        'registerConnectionFieldFactory is deprecated and will be removed in the next '
        'major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.',
        DeprecationWarning,
    )
    global __connectionFactory
    __connectionFactory = factoryMethod


def unregisterConnectionFieldFactory():
    warnings.warn(
        'registerConnectionFieldFactory is deprecated and will be removed in the next '
        'major version. Use SQLAlchemyObjectType.Meta.connection_field_factory instead.',
        DeprecationWarning,
    )
    global __connectionFactory
    __connectionFactory = UnsortedSQLAlchemyConnectionField


def get_nullable_type(_type):
    if isinstance(_type, NonNull):
        return _type.of_type
    return _type
