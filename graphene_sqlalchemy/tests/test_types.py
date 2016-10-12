
from graphene import Field, Int, Interface, ObjectType
from graphene.relay import Node, is_node

from ..registry import Registry
from ..types import SQLAlchemyObjectType
from .models import Article, Reporter

registry = Registry()


class Character(SQLAlchemyObjectType):
    '''Character description'''
    class Meta:
        model = Reporter
        registry = registry


class Human(SQLAlchemyObjectType):
    '''Human description'''

    pub_date = Int()

    class Meta:
        model = Article
        exclude_fields = ('id', )
        registry = registry
        interfaces = (Node, )


def test_sqlalchemy_interface():
    assert issubclass(Node, Interface)
    assert issubclass(Node, Node)


# @patch('graphene.contrib.sqlalchemy.tests.models.Article.filter', return_value=Article(id=1))
# def test_sqlalchemy_get_node(get):
#     human = Human.get_node(1, None)
#     get.assert_called_with(id=1)
#     assert human.id == 1


def test_objecttype_registered():
    assert issubclass(Character, ObjectType)
    assert Character._meta.model == Reporter
    assert list(
        Character._meta.fields.keys()) == [
        'id',
        'first_name',
        'last_name',
        'email',
        'pets',
        'articles',
        'favorite_article']


# def test_sqlalchemynode_idfield():
#     idfield = Node._meta.fields_map['id']
#     assert isinstance(idfield, GlobalIDField)


# def test_node_idfield():
#     idfield = Human._meta.fields_map['id']
#     assert isinstance(idfield, GlobalIDField)


def test_node_replacedfield():
    idfield = Human._meta.fields['pub_date']
    assert isinstance(idfield, Field)
    assert idfield.type == Int


def test_object_type():
    assert issubclass(Human, ObjectType)
    assert list(Human._meta.fields.keys()) == ['id', 'headline', 'reporter_id', 'reporter', 'pub_date']
    assert is_node(Human)


def test_abstract_subclass():
    registry = Registry()

    class AbstractSubclass(SQLAlchemyObjectType):
        class Meta:
            registry = registry
            abstract = True

    assert issubclass(AbstractSubclass, SQLAlchemyObjectType)
    assert len(registry._registry) == 0
