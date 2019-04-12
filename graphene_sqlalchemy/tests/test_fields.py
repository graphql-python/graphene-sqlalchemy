import pytest

from graphene.relay import Connection

from ..fields import SQLAlchemyConnectionField
from ..types import SQLAlchemyObjectType
from ..utils import get_sort_argument_for_model
from .models import Editor
from .models import Pet as PetModel


class Pet(SQLAlchemyObjectType):
    class Meta:
        model = PetModel


class PetConn(Connection):
    class Meta:
        node = Pet


def test_sort_added_by_default():
    arg = SQLAlchemyConnectionField(PetConn)
    assert "sort" in arg.args
    assert arg.args["sort"] == get_sort_argument_for_model(PetModel)


def test_sort_can_be_removed():
    arg = SQLAlchemyConnectionField(PetConn, sort=None)
    assert "sort" not in arg.args


def test_custom_sort():
    arg = SQLAlchemyConnectionField(PetConn, sort=get_sort_argument_for_model(Editor))
    assert arg.args["sort"] == get_sort_argument_for_model(Editor)


def test_init_raises():
    with pytest.raises(Exception, match="Cannot create sort"):
        SQLAlchemyConnectionField(Connection)
