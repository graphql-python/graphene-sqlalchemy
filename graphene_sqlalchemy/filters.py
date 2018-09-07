import graphene

from collections import OrderedDict
from graphene import Argument, Field
from sqlalchemy import inspect

# Cache for the generated classes, to avoid name clash
_INPUT_CACHE = {}
_INPUT_FIELDS_CACHE = {}


class Filter:
    @staticmethod
    def add_filter_to_query(query, model, field, value):
        [(operator, value)] = value.items()
        if operator == 'eq':
            query = query.filter(getattr(model, field) == value)
        elif operator == 'ne':
            query = query.filter(getattr(model, field) == value)
        elif operator == 'lt':
            query = query.filter(getattr(model, field) < value)
        elif operator == 'gt':
            query = query.filter(getattr(model, field) > value)
        elif operator == 'like':
            query = query.filter(getattr(model, field).like(value))
        return query


def filter_class_for_module(cls):
    name = cls.__name__ + "InputFilter"
    if name in _INPUT_CACHE:
        return Argument(_INPUT_CACHE[name])

    class InputFilterBase:
        pass

    fields = OrderedDict()
    for column in inspect(cls).columns.values():
        maybe_field = create_input_filter_field(column)
        if maybe_field:
            fields[column.name] = maybe_field
    input_class = type(name, (InputFilterBase, graphene.InputObjectType), {})
    input_class._meta.fields.update(fields)
    _INPUT_CACHE[name] = input_class
    return Argument(input_class)


def create_input_filter_field(column):
    from .converter import convert_sqlalchemy_type
    graphene_type = convert_sqlalchemy_type(column.type, column)
    if graphene_type.__class__ == Field:  # TODO enum not supported
        return None
    name = str(graphene_type.__class__) + 'Filter'

    if name in _INPUT_FIELDS_CACHE:
        return Field(_INPUT_FIELDS_CACHE[name])

    field_class = Filter
    fields = OrderedDict()
    fields['eq'] = Field(graphene_type.__class__, description='Field should be equal to given value')
    fields['ne'] = Field(graphene_type.__class__, description='Field should not be equal to given value')
    fields['lt'] = Field(graphene_type.__class__, description='Field should be less then given value')
    fields['gt'] = Field(graphene_type.__class__, description='Field should be great then given value')
    fields['like'] = Field(graphene_type.__class__, description='Field should have a pattern of given value')
    # TODO construct operators based on __class__
    # TODO complex filter support: OR

    field_class = type(name, (field_class, graphene.InputObjectType), {})
    field_class._meta.fields.update(fields)
    _INPUT_FIELDS_CACHE[name] = field_class
    return Field(field_class)
