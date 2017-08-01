from functools import partial

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

    @property
    def type(self):
        from .types import SQLAlchemyObjectType
        _type = super(ConnectionField, self).type
        assert issubclass(_type, SQLAlchemyObjectType), (
            "SQLAlchemyConnectionField only accepts SQLAlchemyObjectType types"
        )
        assert _type._meta.connection, "The type {} doesn't have a connection".format(_type.__name__)
        return _type._meta.connection

    @classmethod
    def connection_resolver(cls, resolver, connection, model, root, info, **args):
        iterable = resolver(root, info, **args)
        if iterable is None:
            iterable = cls.get_query(model, info, **args)
        if isinstance(iterable, Query):
            _len = iterable.count()
        else:
            _len = len(iterable)
        connection = connection_from_list_slice(
            iterable,
            args,
            slice_start=0,
            list_length=_len,
            list_slice_length=_len,
            connection_type=connection,
            pageinfo_type=PageInfo,
            edge_type=connection.Edge,
        )
        connection.iterable = iterable
        connection.length = _len
        return connection

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
