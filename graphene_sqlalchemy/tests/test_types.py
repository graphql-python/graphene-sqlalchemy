
from graphene import Field, Int, Interface, ObjectType, Connection, Schema
from graphene.relay import Node, is_node

from ..registry import Registry
from ..types import SQLAlchemyObjectType
from ..fields import SQLAlchemyConnectionField
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


    class Human(SQLAlchemyObjectType):
        '''Human description'''

        pub_date = Int()

        class Meta:
            model = Article
            # exclude_fields = ('id', )
            registry = registry
            interfaces = (Node, )

    assert issubclass(Human, ObjectType)
    assert list(Human._meta.fields.keys()) == ['id', 'headline', 'pub_date', 'reporter_id', 'reporter']
    assert is_node(Human)



# Test Custom SQLAlchemyObjectType Implementation
class CustomSQLAlchemyObjectType(SQLAlchemyObjectType):
    class Meta:
        abstract = True


class CustomCharacter(CustomSQLAlchemyObjectType):
    '''Character description'''
    class Meta:
        model = Reporter
        registry = registry


def test_custom_objecttype_registered():
    assert issubclass(CustomCharacter, ObjectType)
    assert CustomCharacter._meta.model == Reporter
    assert list(
        CustomCharacter._meta.fields.keys()) == [
        'id',
        'first_name',
        'last_name',
        'email',
        'pets',
        'articles',
        'favorite_article']


def test_custom_connection(session, setup_fixtures):
    exp_counter = 123

    class CustomConnection(Connection):
        class Meta:
            abstract = True

        counter = Int()

        @staticmethod
        def resolve_counter(*args, **kwargs):
            return exp_counter

    class ArticleType(SQLAlchemyObjectType, interfaces=[Node]):
        class Meta:
            model = Article
            connection = CustomConnection
            interfaces = (Node,)
            registry = registry

    class Query(ObjectType):
        articles = SQLAlchemyConnectionField(ArticleType)

    schema = Schema(query=Query)
    result = schema.execute("query { articles { counter edges { node { headline }}}}",
                            context_value={'session': session})

    assert not result.errors
    assert result.data['articles']['counter'] == exp_counter
    assert result.data['articles']['edges'][0]['node']['headline'] == 'Hi!'
