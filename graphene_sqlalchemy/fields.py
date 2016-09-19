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
    def get_query(cls, model, context, info, args):
        return get_query(model, context)

    @classmethod
    def connection_resolver(cls, resolver, connection, model, root, args, context, info):
        iterable = resolver(root, args, context, info)
        if iterable is None:
            iterable = cls.get_query(model, context, info, args)
        if isinstance(iterable, Query):
            _len = iterable.count()
        else:
            _len = len(iterable)
        return connection_from_list_slice(
            iterable,
            args,
            slice_start=0,
            list_length=_len,
            list_slice_length=_len,
            connection_type=connection,
            pageinfo_type=PageInfo,
            edge_type=connection.Edge,
        )

    def get_resolver(self, parent_resolver):
        return partial(self.connection_resolver, parent_resolver, self.type, self.model)
