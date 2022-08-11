import re

import graphene
from graphene.types.inputobjecttype import InputObjectTypeOptions


class ObjectTypeFilter(graphene.InputObjectType):
    pass


class RelationshipFilter(graphene.InputObjectType):
    pass


class AbstractType:
    """Dummy class for generic filters"""
    pass


class ScalarFilter(graphene.InputObjectType):
    """Basic Filter for Scalars in Graphene.
    We want this filter to use Dynamic fields so it provides the base
    filtering methods ("eq, nEq") for different types of scalars.
    The Dynamic fields will resolve to Meta.filtered_type"""

    @classmethod
    def __init_subclass_with_meta__(cls, type=None, _meta=None, **options):
        print(type)  # The type from the Meta Class

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
        super(ScalarFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    # Abstract methods can be marked using AbstractType. See comment on the init method
    @classmethod
    def eq_filter(cls, val: AbstractType) -> bool:
        # TBD filtering magic
        pass


class StringFilter(ScalarFilter):
    class Meta:
        type = graphene.String


class NumberFilter(ScalarFilter):
    """Intermediate Filter class since all Numbers are in an order relationship (support <, > etc)"""

    class Meta:
        abstract = True

    @classmethod
    def gt_filter(cls, val: str) -> bool:
        # TBD filtering magic
        pass


class FloatFilter(NumberFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        type = graphene.Float
