from ..fields import SQLAlchemyConnectionField
from ..types import SQLAlchemyObjectType
from ..utils import sort_argument_for_model
from .models import Pet as PetModel, Editor


class Pet(SQLAlchemyObjectType):
    class Meta:
        model = PetModel


def test_sort_added_by_default():
    arg = SQLAlchemyConnectionField(Pet)
    assert 'sort' in arg.args
    assert arg.args['sort'] == sort_argument_for_model(PetModel)


def test_sort_can_be_removed():
    arg = SQLAlchemyConnectionField(Pet, sort=None)
    assert 'sort' not in arg.args


def test_custom_sort():
    arg = SQLAlchemyConnectionField(Pet, sort=sort_argument_for_model(Editor))
    assert arg.args['sort'] == sort_argument_for_model(Editor)