import enum

import pytest
from sqlalchemy import Column, func, select, types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import column_property, composite
from sqlalchemy_utils import ChoiceType, JSONType, ScalarListType

import graphene
from graphene.relay import Node
from graphene.types.datetime import DateTime
from graphene.types.json import JSONString

from ..converter import (convert_sqlalchemy_column,
                         convert_sqlalchemy_composite,
                         convert_sqlalchemy_relationship)
from ..fields import (UnsortedSQLAlchemyConnectionField,
                      default_connection_field_factory)
from ..registry import Registry, get_global_registry
from ..types import SQLAlchemyObjectType
from .models import Article, CompositeFullName, Pet, Reporter


def mock_resolver():
    pass


def get_field(sqlalchemy_type, **column_kwargs):
    class Model(declarative_base()):
        __tablename__ = 'model'
        id_ = Column(types.Integer, primary_key=True)
        column = Column(sqlalchemy_type, doc="Custom Help Text", **column_kwargs)

    column_prop = inspect(Model).column_attrs['column']
    return convert_sqlalchemy_column(column_prop, get_global_registry(), mock_resolver)


def get_field_from_column(column_):
    class Model(declarative_base()):
        __tablename__ = 'model'
        id_ = Column(types.Integer, primary_key=True)
        column = column_

    column_prop = inspect(Model).column_attrs['column']
    return convert_sqlalchemy_column(column_prop, get_global_registry(), mock_resolver)


def test_should_unknown_sqlalchemy_field_raise_exception():
    re_err = "Don't know how to convert the SQLAlchemy field"
    with pytest.raises(Exception, match=re_err):
        # support legacy Binary type and subsequent LargeBinary
        get_field(getattr(types, 'LargeBinary', types.Binary)())


def test_should_date_convert_string():
    assert get_field(types.Date()).type == graphene.String


def test_should_datetime_convert_datetime():
    assert get_field(types.DateTime()).type == DateTime


def test_should_time_convert_string():
    assert get_field(types.Time()).type == graphene.String


def test_should_string_convert_string():
    assert get_field(types.String()).type == graphene.String


def test_should_text_convert_string():
    assert get_field(types.Text()).type == graphene.String


def test_should_unicode_convert_string():
    assert get_field(types.Unicode()).type == graphene.String


def test_should_unicodetext_convert_string():
    assert get_field(types.UnicodeText()).type == graphene.String


def test_should_enum_convert_enum():
    field = get_field(types.Enum(enum.Enum("TwoNumbers", ("one", "two"))))
    field_type = field.type()
    assert isinstance(field_type, graphene.Enum)
    assert field_type._meta.name == "TwoNumbers"
    assert hasattr(field_type, "ONE")
    assert not hasattr(field_type, "one")
    assert hasattr(field_type, "TWO")
    assert not hasattr(field_type, "two")

    field = get_field(types.Enum("one", "two", name="two_numbers"))
    field_type = field.type()
    assert isinstance(field_type, graphene.Enum)
    assert field_type._meta.name == "TwoNumbers"
    assert hasattr(field_type, "ONE")
    assert not hasattr(field_type, "one")
    assert hasattr(field_type, "TWO")
    assert not hasattr(field_type, "two")


def test_should_not_enum_convert_enum_without_name():
    field = get_field(types.Enum("one", "two"))
    re_err = r"No type name specified for Enum\('one', 'two'\)"
    with pytest.raises(TypeError, match=re_err):
        field.type()


def test_should_small_integer_convert_int():
    assert get_field(types.SmallInteger()).type == graphene.Int


def test_should_big_integer_convert_int():
    assert get_field(types.BigInteger()).type == graphene.Float


def test_should_integer_convert_int():
    assert get_field(types.Integer()).type == graphene.Int


def test_should_primary_integer_convert_id():
    assert get_field(types.Integer(), primary_key=True).type == graphene.NonNull(graphene.ID)


def test_should_boolean_convert_boolean():
    assert get_field(types.Boolean()).type == graphene.Boolean


def test_should_float_convert_float():
    assert get_field(types.Float()).type == graphene.Float


def test_should_numeric_convert_float():
    assert get_field(types.Numeric()).type == graphene.Float


def test_should_choice_convert_enum():
    field = get_field(ChoiceType([(u"es", u"Spanish"), (u"en", u"English")]))
    graphene_type = field.type
    assert issubclass(graphene_type, graphene.Enum)
    assert graphene_type._meta.name == "MODEL_COLUMN"
    assert graphene_type._meta.enum.__members__["es"].value == "Spanish"
    assert graphene_type._meta.enum.__members__["en"].value == "English"


def test_should_enum_choice_convert_enum():
    class TestEnum(enum.Enum):
        es = u"Spanish"
        en = u"English"

    field = get_field(ChoiceType(TestEnum, impl=types.String()))
    graphene_type = field.type
    assert issubclass(graphene_type, graphene.Enum)
    assert graphene_type._meta.name == "MODEL_COLUMN"
    assert graphene_type._meta.enum.__members__["es"].value == "Spanish"
    assert graphene_type._meta.enum.__members__["en"].value == "English"


def test_should_intenum_choice_convert_enum():
    class TestEnum(enum.IntEnum):
        one = 1
        two = 2

    field = get_field(ChoiceType(TestEnum, impl=types.String()))
    graphene_type = field.type
    assert issubclass(graphene_type, graphene.Enum)
    assert graphene_type._meta.name == "MODEL_COLUMN"
    assert graphene_type._meta.enum.__members__["one"].value == 1
    assert graphene_type._meta.enum.__members__["two"].value == 2


def test_should_columproperty_convert():
    field = get_field_from_column(column_property(
        select([func.sum(func.cast(id, types.Integer))]).where(id == 1)
    ))

    assert field.type == graphene.Int


def test_should_scalar_list_convert_list():
    field = get_field(ScalarListType())
    assert isinstance(field.type, graphene.List)
    assert field.type.of_type == graphene.String


def test_should_jsontype_convert_jsonstring():
    assert get_field(JSONType()).type == JSONString


def test_should_manytomany_convert_connectionorlist():
    class A(SQLAlchemyObjectType):
        class Meta:
            model = Article

    dynamic_field = convert_sqlalchemy_relationship(
        Reporter.pets.property, A, default_connection_field_factory, True, 'orm_field_name',
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    assert not dynamic_field.get_type()


def test_should_manytomany_convert_connectionorlist_list():
    class A(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    dynamic_field = convert_sqlalchemy_relationship(
        Reporter.pets.property, A, default_connection_field_factory, True, 'orm_field_name',
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert isinstance(graphene_type.type, graphene.List)
    assert graphene_type.type.of_type == A


def test_should_manytomany_convert_connectionorlist_connection():
    class A(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces = (Node,)

    dynamic_field = convert_sqlalchemy_relationship(
        Reporter.pets.property, A, default_connection_field_factory, True, 'orm_field_name',
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    assert isinstance(dynamic_field.get_type(), UnsortedSQLAlchemyConnectionField)


def test_should_manytoone_convert_connectionorlist():
    class A(SQLAlchemyObjectType):
        class Meta:
            model = Article

    dynamic_field = convert_sqlalchemy_relationship(
        Reporter.pets.property, A, default_connection_field_factory, True, 'orm_field_name',
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    assert not dynamic_field.get_type()


def test_should_manytoone_convert_connectionorlist_list():
    class A(SQLAlchemyObjectType):
        class Meta:
            model = Reporter

    dynamic_field = convert_sqlalchemy_relationship(
        Article.reporter.property, A, default_connection_field_factory, True, 'orm_field_name',
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == A


def test_should_manytoone_convert_connectionorlist_connection():
    class A(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (Node,)

    dynamic_field = convert_sqlalchemy_relationship(
        Article.reporter.property, A, default_connection_field_factory, True, 'orm_field_name',
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == A


def test_should_onetoone_convert_field():
    class A(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    dynamic_field = convert_sqlalchemy_relationship(
        Reporter.favorite_article.property, A, default_connection_field_factory, True, 'orm_field_name',
    )
    assert isinstance(dynamic_field, graphene.Dynamic)
    graphene_type = dynamic_field.get_type()
    assert isinstance(graphene_type, graphene.Field)
    assert graphene_type.type == A


def test_should_postgresql_uuid_convert():
    assert get_field(postgresql.UUID()).type == graphene.String


def test_should_postgresql_enum_convert():
    field = get_field(postgresql.ENUM("one", "two", name="two_numbers"))
    field_type = field.type()
    assert isinstance(field_type, graphene.Enum)
    assert field_type._meta.name == "TwoNumbers"
    assert hasattr(field_type, "ONE")
    assert not hasattr(field_type, "one")
    assert hasattr(field_type, "TWO")
    assert not hasattr(field_type, "two")


def test_should_postgresql_py_enum_convert():
    field = get_field(postgresql.ENUM(enum.Enum("TwoNumbers", "one two"), name="two_numbers"))
    field_type = field.type()
    assert field_type._meta.name == "TwoNumbers"
    assert isinstance(field_type, graphene.Enum)
    assert hasattr(field_type, "ONE")
    assert not hasattr(field_type, "one")
    assert hasattr(field_type, "TWO")
    assert not hasattr(field_type, "two")


def test_should_postgresql_array_convert():
    field = get_field(postgresql.ARRAY(types.Integer))
    assert isinstance(field.type, graphene.List)
    assert field.type.of_type == graphene.Int


def test_should_array_convert():
    field = get_field(types.ARRAY(types.Integer))
    assert isinstance(field.type, graphene.List)
    assert field.type.of_type == graphene.Int


def test_should_postgresql_json_convert():
    assert get_field(postgresql.JSON()).type == graphene.JSONString


def test_should_postgresql_jsonb_convert():
    assert get_field(postgresql.JSONB()).type == graphene.JSONString


def test_should_postgresql_hstore_convert():
    assert get_field(postgresql.HSTORE()).type == graphene.JSONString


def test_should_composite_convert():
    registry = Registry()

    class CompositeClass:
        def __init__(self, col1, col2):
            self.col1 = col1
            self.col2 = col2

    @convert_sqlalchemy_composite.register(CompositeClass, registry)
    def convert_composite_class(composite, registry):
        return graphene.String(description=composite.doc)

    field = convert_sqlalchemy_composite(
        composite(CompositeClass, (Column(types.Unicode(50)), Column(types.Unicode(50))), doc="Custom Help Text"),
        registry,
        mock_resolver,
    )
    assert isinstance(field, graphene.String)


def test_should_unknown_sqlalchemy_composite_raise_exception():
    class CompositeClass:
        def __init__(self, col1, col2):
            self.col1 = col1
            self.col2 = col2

    re_err = "Don't know how to convert the composite field"
    with pytest.raises(Exception, match=re_err):
        convert_sqlalchemy_composite(
            composite(CompositeFullName, (Column(types.Unicode(50)), Column(types.Unicode(50)))),
            Registry(),
            mock_resolver,
        )
