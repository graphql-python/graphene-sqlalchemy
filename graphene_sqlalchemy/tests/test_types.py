from collections import OrderedDict
from graphene import Field, Int, Interface, ObjectType
from graphene.relay import Node, is_node, Connection
import six
from promise import Promise

from ..registry import Registry
from ..types import SQLAlchemyObjectType, SQLAlchemyObjectTypeOptions
from .models import Article, Reporter
from ..fields import SQLAlchemyConnectionField

registry = Registry()


class Character(SQLAlchemyObjectType):
    """Character description"""

    class Meta:
        model = Reporter
        registry = registry


class Human(SQLAlchemyObjectType):
    """Human description"""

    pub_date = Int()

    class Meta:
        model = Article
        exclude_fields = ("id",)
        registry = registry
        interfaces = (Node,)


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
    assert list(Character._meta.fields.keys()) == [
        "id",
        "first_name",
        "last_name",
        "email",
        "pets",
        "articles",
        "favorite_article",
    ]


# def test_sqlalchemynode_idfield():
#     idfield = Node._meta.fields_map['id']
#     assert isinstance(idfield, GlobalIDField)


# def test_node_idfield():
#     idfield = Human._meta.fields_map['id']
#     assert isinstance(idfield, GlobalIDField)


def test_node_replacedfield():
    idfield = Human._meta.fields["pub_date"]
    assert isinstance(idfield, Field)
    assert idfield.type == Int


def test_object_type():
    class Human(SQLAlchemyObjectType):
        """Human description"""

        pub_date = Int()

        class Meta:
            model = Article
            # exclude_fields = ('id', )
            registry = registry
            interfaces = (Node,)

    assert issubclass(Human, ObjectType)
    assert list(Human._meta.fields.keys()) == [
        "id",
        "headline",
        "pub_date",
        "reporter_id",
        "reporter",
    ]
    assert is_node(Human)


# Test Custom SQLAlchemyObjectType Implementation
class CustomSQLAlchemyObjectType(SQLAlchemyObjectType):
    class Meta:
        abstract = True


class CustomCharacter(CustomSQLAlchemyObjectType):
    """Character description"""

    class Meta:
        model = Reporter
        registry = registry


def test_custom_objecttype_registered():
    assert issubclass(CustomCharacter, ObjectType)
    assert CustomCharacter._meta.model == Reporter
    assert list(CustomCharacter._meta.fields.keys()) == [
        "id",
        "first_name",
        "last_name",
        "email",
        "pets",
        "articles",
        "favorite_article",
    ]


# Test Custom SQLAlchemyObjectType with Custom Options
class CustomOptions(SQLAlchemyObjectTypeOptions):
    custom_option = None
    custom_fields = None


class SQLAlchemyObjectTypeWithCustomOptions(SQLAlchemyObjectType):
    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(
        cls, custom_option=None, custom_fields=None, **options
    ):
        _meta = CustomOptions(cls)
        _meta.custom_option = custom_option
        _meta.fields = custom_fields
        super(SQLAlchemyObjectTypeWithCustomOptions, cls).__init_subclass_with_meta__(
            _meta=_meta, **options
        )


class ReporterWithCustomOptions(SQLAlchemyObjectTypeWithCustomOptions):
    class Meta:
        model = Reporter
        custom_option = "custom_option"
        custom_fields = OrderedDict([("custom_field", Field(Int()))])


def test_objecttype_with_custom_options():
    assert issubclass(ReporterWithCustomOptions, ObjectType)
    assert ReporterWithCustomOptions._meta.model == Reporter
    assert list(ReporterWithCustomOptions._meta.fields.keys()) == [
        "custom_field",
        "id",
        "first_name",
        "last_name",
        "email",
        "pets",
        "articles",
        "favorite_article",
    ]
    assert ReporterWithCustomOptions._meta.custom_option == "custom_option"
    assert isinstance(ReporterWithCustomOptions._meta.fields["custom_field"].type, Int)


def test_promise_connection_resolver():
    class TestConnection(Connection):
        class Meta:
            node = ReporterWithCustomOptions

    resolver = lambda *args, **kwargs: Promise.resolve([])
    result = SQLAlchemyConnectionField.connection_resolver(
        resolver, TestConnection, ReporterWithCustomOptions, None, None
    )
    assert result is not None
