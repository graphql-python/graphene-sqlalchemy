from functools import partial
from promise import is_thenable, Promise
from sqlalchemy.orm.query import Query

from graphene.relay import ConnectionField
from graphene.relay.connection import PageInfo
from graphql_relay.connection.arrayconnection import connection_from_list_slice

from .utils import get_query


class SQLAlchemyConnectionField(ConnectionField):

    @property
    def model(self):
        return self.type._meta.node._meta.model

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
        return partial(self.connection_resolver, parent_resolver, self.type, self.model)


__connectionFactory = SQLAlchemyConnectionField


def createConnectionField(_type):
    return __connectionFactory(_type)


def registerConnectionFieldFactory(factoryMethod):
    global __connectionFactory
    __connectionFactory = factoryMethod


def unregisterConnectionFieldFactory():
    global __connectionFactory
    __connectionFactory = SQLAlchemyConnectionField
