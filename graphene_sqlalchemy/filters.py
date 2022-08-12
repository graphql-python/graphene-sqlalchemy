import re
from typing import List

import graphene
from graphene.types.inputobjecttype import InputObjectTypeOptions
from graphene_sqlalchemy.utils import is_list


class AbstractType:
    """Dummy class for generic filters"""
    pass


class ObjectTypeFilter(graphene.InputObjectType):
    @classmethod
    def __init_subclass_with_meta__(cls, filter_fields=None, _meta=None, **options):

        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = InputObjectTypeOptions(cls)

        # Add all fields to the meta options. graphene.InputObjectType will take care of the rest
        if _meta.fields:
            _meta.fields.update(filter_fields)
        else:
            _meta.fields = filter_fields

        super(ObjectTypeFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def and_logic(cls, val: list["ObjectTypeFilter"]):
        # TODO
        pass


class RelationshipFilter(graphene.InputObjectType):
    @classmethod
    def __init_subclass_with_meta__(cls, object_type_filter=None, _meta=None, **options):
        if not object_type_filter:
            raise Exception("Relationship Filters must be specific to an object type")
        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = InputObjectTypeOptions(cls)

        # get all filter functions
        filter_function_regex = re.compile(".+_filter$")

        filter_functions = []

        # Search the entire class for functions matching the filter regex
        for func in dir(cls):
            func_attr = getattr(cls, func)
            # Check if attribute is a function
            if callable(func_attr) and filter_function_regex.match(func):
                # add function and attribute name to the list
                filter_functions.append((func.removesuffix("_filter"), func_attr.__annotations__))

        relationship_filters = {}

        # Generate Graphene Fields from the filter functions based on type hints
        for field_name, annotations in filter_functions:
            assert "val" in annotations, "Each filter method must have a value field with valid type annotations"
            # If type is generic, replace with actual type of filter class
            if is_list(annotations["val"]):
                relationship_filters.update({field_name: graphene.InputField(graphene.List(object_type_filter))})
            else:
                relationship_filters.update({field_name: graphene.InputField(object_type_filter)})

        # Add all fields to the meta options. graphene.InputObjectType will take care of the rest
        if _meta.fields:
            _meta.fields.update(relationship_filters)
        else:
            _meta.fields = relationship_filters

        super(RelationshipFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def contains_filter(cls, val: List["RelationshipFilter"]):
        # TODO
        pass


class FieldFilter(graphene.InputObjectType):
    """Basic Filter for Scalars in Graphene.
    We want this filter to use Dynamic fields so it provides the base
    filtering methods ("eq, nEq") for different types of scalars.
    The Dynamic fields will resolve to Meta.filtered_type"""

    @classmethod
    def __init_subclass_with_meta__(cls, type=None, _meta=None, **options):

        # get all filter functions
        filter_function_regex = re.compile(".+_filter$")

        filter_functions = []

        # Search the entire class for functions matching the filter regex
        for func in dir(cls):
            func_attr = getattr(cls, func)
            # Check if attribute is a function
            if callable(func_attr) and filter_function_regex.match(func):
                # add function and attribute name to the list
                filter_functions.append((
                    re.sub("\_filter$", "", func), func_attr.__annotations__)
                )

        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = InputObjectTypeOptions(cls)

        new_filter_fields = {}

        # Generate Graphene Fields from the filter functions based on type hints
        for field_name, annotations in filter_functions:
            assert "val" in annotations, "Each filter method must have a value field with valid type annotations"
            # If type is generic, replace with actual type of filter class
            if annotations["val"] == AbstractType:
                # TODO Maybe there is an existing class or a more elegant way to solve this
                # One option would be to only annotate non-abstract filters
                new_filter_fields.update({field_name: graphene.InputField(type)})
            else:
                # TODO this is a place holder, we need to convert the type of val to a valid graphene
                # type that we can pass to the InputField. We could re-use converter.convert_hybrid_property_return_type
                new_filter_fields.update({field_name: graphene.InputField(graphene.String)})

        # Add all fields to the meta options. graphene.InputbjectType will take care of the rest
        if _meta.fields:
            _meta.fields.update(new_filter_fields)
        else:
            _meta.fields = new_filter_fields

        # Pass modified meta to the super class
        super(FieldFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    # Abstract methods can be marked using AbstractType. See comment on the init method
    @classmethod
    def eq_filter(cls, val: AbstractType) -> bool:
        # TBD filtering magic
        pass


class StringFilter(FieldFilter):
    class Meta:
        type = graphene.String


class BooleanFilter(FieldFilter):
    class Meta:
        type = graphene.Boolean


class NumberFilter(FieldFilter):
    """Intermediate Filter class since all Numbers are in an order relationship (support <, > etc)"""

    class Meta:
        abstract = True

    @classmethod
    def gt_filter(cls, val: AbstractType) -> bool:
        # TBD filtering magic
        pass


class FloatFilter(NumberFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        type = graphene.Float


class IntFilter(NumberFilter):
    class Meta:
        type = graphene.Int


class DateFilter(NumberFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        type = graphene.Date
