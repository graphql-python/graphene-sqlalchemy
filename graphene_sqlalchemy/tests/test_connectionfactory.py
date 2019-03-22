from graphene_sqlalchemy.fields import (
    SQLAlchemyConnectionField,
    register_connection_field_factory,
    unregister_connection_field_factory,
    registerConnectionFieldFactory,
    unregisterConnectionFieldFactory,
)
from graphene_sqlalchemy.types import SQLAlchemyObjectType
from graphene_sqlalchemy.tests.models import Article, Reporter
from graphene_sqlalchemy.registry import Registry
from graphene import Connection, Node


def define_types():
    _registry = Registry()

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            registry = _registry
            interfaces = (Node,)


    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            registry = _registry
            interfaces = (Node,)

    return {
        'ReporterType': ReporterType,
        'ArticleType': ArticleType,
    }


def test_register_connection_field_factory():
    def connection_field_factory(relationship, registry):
        model = relationship.mapper.entity
        _type = registry.get_type_for_model(model)
        return SQLAlchemyConnectionField(_type._meta.connection)

    register_connection_field_factory(connection_field_factory)

    types = define_types()

    assert isinstance(types['ReporterType']._meta.fields['articles'].type(), SQLAlchemyConnectionField)


def test_unregister_connection_field_factory():
    register_connection_field_factory(lambda: None)
    unregister_connection_field_factory()

    types = define_types()

    assert not isinstance(types['ReporterType']._meta.fields['articles'].type(), SQLAlchemyConnectionField)


def test_deprecated_registerConnectionFieldFactory():
    registerConnectionFieldFactory(SQLAlchemyConnectionField)
    types = define_types()
    assert isinstance(types['ReporterType']._meta.fields['articles'].type(), SQLAlchemyConnectionField)


def test_deprecated_unregisterConnectionFieldFactory():
    registerConnectionFieldFactory(SQLAlchemyConnectionField)
    unregisterConnectionFieldFactory()
    types = define_types()

    assert not isinstance(types['ReporterType']._meta.fields['articles'].type(), SQLAlchemyConnectionField)
