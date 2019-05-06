import pytest
from promise import Promise

from graphene.relay import Connection

from ..fields import SQLAlchemyConnectionField
from ..types import SQLAlchemyObjectType
from .models import Editor as EditorModel
from .models import Pet as PetModel


class Pet(SQLAlchemyObjectType):
    class Meta:
        model = PetModel


class Editor(SQLAlchemyObjectType):
    class Meta:
        model = EditorModel


class PetConnection(Connection):
    class Meta:
        node = Pet


def test_promise_connection_resolver():
    def resolver(_obj, _info):
        return Promise.resolve([])

    result = SQLAlchemyConnectionField.connection_resolver(
        resolver, PetConnection, Pet, None, None
    )
    assert isinstance(result, Promise)


def test_sort_added_by_default():
    field = SQLAlchemyConnectionField(PetConnection)
    assert "sort" in field.args
    assert field.args["sort"] == Pet.sort_argument()


def test_sort_can_be_removed():
    field = SQLAlchemyConnectionField(PetConnection, sort=None)
    assert "sort" not in field.args


def test_custom_sort():
    field = SQLAlchemyConnectionField(PetConnection, sort=Editor.sort_argument())
    assert field.args["sort"] == Editor.sort_argument()


def test_init_raises():
    with pytest.raises(TypeError, match="Cannot create sort"):
        SQLAlchemyConnectionField(Connection)
