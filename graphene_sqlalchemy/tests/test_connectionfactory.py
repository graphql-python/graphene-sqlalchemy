from graphene_sqlalchemy.fields import (
    SQLAlchemyConnectionField,
    registerConnectionFieldFactory,
    unregisterConnectionFieldFactory,
)
import graphene


def test_register():
    class LXConnectionField(SQLAlchemyConnectionField):
        @classmethod
        def _applyQueryArgs(cls, model, q, args):
            return q

        @classmethod
        def connection_resolver(
            cls, resolver, connection, model, root, args, context, info
        ):
            def LXResolver(root, args, context, info):
                iterable = resolver(root, args, context, info)
                if iterable is None:
                    iterable = cls.get_query(model, context, info, args)

                # We accept always a query here. All LX-queries can be filtered and sorted
                iterable = cls._applyQueryArgs(model, iterable, args)
                return iterable

            return SQLAlchemyConnectionField.connection_resolver(
                LXResolver, connection, model, root, args, context, info
            )

    def createLXConnectionField(table):
        class LXConnection(graphene.relay.Connection):
            class Meta:
                node = table

        return LXConnectionField(
            LXConnection,
            filter=table.filter(),
            order_by=graphene.List(of_type=table.order_by),
        )

    registerConnectionFieldFactory(createLXConnectionField)
    unregisterConnectionFieldFactory()
