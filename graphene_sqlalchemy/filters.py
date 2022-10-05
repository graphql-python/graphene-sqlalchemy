from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Type, TypeVar, Union

from sqlalchemy import not_
from sqlalchemy.orm import Query, aliased

import graphene
from graphene.types.inputobjecttype import InputObjectTypeOptions
from graphene_sqlalchemy.utils import is_list


class AbstractType:
    """Dummy class for generic filters"""
    pass


class ObjectTypeFilter(graphene.InputObjectType):
    @classmethod
    def __init_subclass_with_meta__(cls, filter_fields=None, model=None, _meta=None, **options):

        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = InputObjectTypeOptions(cls)

        # Add all fields to the meta options. graphene.InputObjectType will take care of the rest
        if _meta.fields:
            _meta.fields.update(filter_fields)
        else:
            _meta.fields = filter_fields

        _meta.model = model

        super(ObjectTypeFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def and_logic(cls, query, field, val: list["ObjectTypeFilter"]):
        # TODO
        pass

    @classmethod
    def execute_filters(cls: Type[FieldFilter], query, filter_dict: Dict, model_alias=None) -> Tuple[Query, List[Any]]:
        model = cls._meta.model
        if model_alias:
            model = model_alias

        clauses = []
        for field, filt_dict in filter_dict.items():
            # Relationships are Dynamic, we need to resolve them fist
            # Maybe we can cache these dynamics to improve efficiency
            # Check with a profiler is required to determine necessity
            input_field = cls._meta.fields[field]
            if isinstance(input_field, graphene.Dynamic):
                field_filter_type = input_field.get_type().type
            else:
                field_filter_type = cls._meta.fields[field].type
            # TODO we need to save the relationship props in the meta fields array
            #  to conduct joins and alias the joins (in case there are duplicate joins: A->B A->C B->C)
            model_field = getattr(model, field)
            if issubclass(field_filter_type, ObjectTypeFilter):
                # Get the model to join on the Filter Query
                joined_model = field_filter_type._meta.model
                # Always alias the model
                joined_model_alias = aliased(joined_model)

                # Join the aliased model onto the query
                query = query.join(model_field.of_type(joined_model_alias))

                # Pass the joined query down to the next object type filter for processing
                query, _clauses = field_filter_type.execute_filters(query, filt_dict, model_alias=joined_model_alias)
                clauses.extend(_clauses)
            if issubclass(field_filter_type, RelationshipFilter):
                # TODO see above; not yet working
                relationship_prop = None
                query, _clauses = field_filter_type.execute_filters(query, filt_dict, relationship_prop)
                clauses.extend(_clauses)
            elif issubclass(field_filter_type, FieldFilter):
                query, _clauses = field_filter_type.execute_filters(query, model_field, filt_dict)
                clauses.extend(_clauses)

        return query, clauses


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
                filter_functions.append((re.sub("_filter$", "", func), func_attr.__annotations__))

        relationship_filters = {}

        # Generate Graphene Fields from the filter functions based on type hints
        for field_name, _annotations in filter_functions:
            assert "val" in _annotations, "Each filter method must have a value field with valid type annotations"
            # If type is generic, replace with actual type of filter class
            if is_list(_annotations["val"]):
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

    @classmethod
    def execute_filters(cls: Type[FieldFilter], query, filter_dict: Dict, relationship_prop) -> Tuple[Query, List[Any]]:
        query, clauses = (query, [])
        # TODO
        return query, clauses


any_field_filter = TypeVar('any_field_filter', bound="FieldFilter")


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
                    re.sub("_filter$", "", func), func_attr.__annotations__)
                )

        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = InputObjectTypeOptions(cls)

        new_filter_fields = {}
        print(f"Generating Fields for {cls.__name__} with type {type} ")
        # Generate Graphene Fields from the filter functions based on type hints
        for field_name, _annotations in filter_functions:
            assert "val" in _annotations, "Each filter method must have a value field with valid type annotations"
            # If type is generic, replace with actual type of filter class
            print(f"Field: {field_name} with annotation {_annotations['val']}")
            if _annotations["val"] == "AbstractType":
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
    def eq_filter(cls, query, field, val: AbstractType) -> Union[Tuple[Query, Any], Any]:
        return field == val

    @classmethod
    def n_eq_filter(cls, query, field, val: AbstractType) -> Union[Tuple[Query, Any], Any]:
        return not_(field == val)

    @classmethod
    def execute_filters(cls: Type[FieldFilter], query, field, filter_dict: any_field_filter) -> Tuple[Query, List[Any]]:
        clauses = []
        for filt, val in filter_dict.items():
            clause = getattr(cls, filt + "_filter")(query, field, val)
            if isinstance(clause, tuple):
                query, clause = clause
            clauses.append(clause)

        return query, clauses


class StringFilter(FieldFilter):
    class Meta:
        type = graphene.String


class BooleanFilter(FieldFilter):
    class Meta:
        type = graphene.Boolean


class OrderedFilter(FieldFilter):
    class Meta:
        abstract = True

    @classmethod
    def gt_filter(cls, query, field, val: AbstractType) -> bool:
        return field > val

    @classmethod
    def gte_filter(cls, query, field, val: AbstractType) -> bool:
        return field >= val

    @classmethod
    def lt_filter(cls, query, field, val: AbstractType) -> bool:
        return field < val

    @classmethod
    def lte_filter(cls, query, field, val: AbstractType) -> bool:
        return field <= val


class NumberFilter(OrderedFilter):
    """Intermediate Filter class since all Numbers are in an order relationship (support <, > etc)"""

    class Meta:
        abstract = True


class FloatFilter(NumberFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        type = graphene.Float


class IntFilter(NumberFilter):
    class Meta:
        type = graphene.Int


class DateFilter(OrderedFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        type = graphene.Date


class IdFilter(FieldFilter):
    class Meta:
        type = graphene.ID
