import re
from typing import Any, Dict, List, Tuple, Type, TypeVar, Union

from graphql import Undefined
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Query, aliased  # , selectinload

import graphene
from graphene.types.inputobjecttype import (
    InputObjectTypeContainer,
    InputObjectTypeOptions,
)
from graphene_sqlalchemy.utils import is_list

BaseTypeFilterSelf = TypeVar(
    "BaseTypeFilterSelf", Dict[str, Any], InputObjectTypeContainer
)


class SQLAlchemyFilterInputField(graphene.InputField):
    def __init__(
        self,
        type_,
        model_attr,
        name=None,
        default_value=Undefined,
        deprecation_reason=None,
        description=None,
        required=False,
        _creation_counter=None,
        **extra_args,
    ):
        super(SQLAlchemyFilterInputField, self).__init__(
            type_,
            name,
            default_value,
            deprecation_reason,
            description,
            required,
            _creation_counter,
            **extra_args,
        )

        self.model_attr = model_attr


def _get_functions_by_regex(
    regex: str, subtract_regex: str, class_: Type
) -> List[Tuple[str, Dict[str, Any]]]:
    function_regex = re.compile(regex)

    matching_functions = []

    # Search the entire class for functions matching the filter regex
    for fn in dir(class_):
        func_attr = getattr(class_, fn)
        # Check if attribute is a function
        if callable(func_attr) and function_regex.match(fn):
            # add function and attribute name to the list
            matching_functions.append(
                (re.sub(subtract_regex, "", fn), func_attr.__annotations__)
            )
    return matching_functions


class BaseTypeFilter(graphene.InputObjectType):
    @classmethod
    def __init_subclass_with_meta__(
        cls, filter_fields=None, model=None, _meta=None, **options
    ):
        from graphene_sqlalchemy.converter import convert_sqlalchemy_type

        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = InputObjectTypeOptions(cls)

        logic_functions = _get_functions_by_regex(".+_logic$", "_logic$", cls)

        new_filter_fields = {}
        # Generate Graphene Fields from the filter functions based on type hints
        for field_name, _annotations in logic_functions:
            assert (
                "val" in _annotations
            ), "Each filter method must have a value field with valid type annotations"
            # If type is generic, replace with actual type of filter class

            replace_type_vars = {BaseTypeFilterSelf: cls}
            field_type = convert_sqlalchemy_type(
                _annotations.get("val", str), replace_type_vars=replace_type_vars
            )
            new_filter_fields.update({field_name: graphene.InputField(field_type)})
        # Add all fields to the meta options. graphene.InputObjectType will take care of the rest

        if _meta.fields:
            _meta.fields.update(filter_fields)
        else:
            _meta.fields = filter_fields
        _meta.fields.update(new_filter_fields)

        _meta.model = model

        super(BaseTypeFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def and_logic(
        cls,
        query,
        filter_type: "BaseTypeFilter",
        val: List[BaseTypeFilterSelf],
        model_alias=None,
    ):
        # # Get the model to join on the Filter Query
        # joined_model = filter_type._meta.model
        # # Always alias the model
        # joined_model_alias = aliased(joined_model)
        clauses = []
        for value in val:
            # # Join the aliased model onto the query
            # query = query.join(model_field.of_type(joined_model_alias))

            query, _clauses = filter_type.execute_filters(
                query, value, model_alias=model_alias
            )  # , model_alias=joined_model_alias)
            clauses += _clauses

        return query, [and_(*clauses)]

    @classmethod
    def or_logic(
        cls,
        query,
        filter_type: "BaseTypeFilter",
        val: List[BaseTypeFilterSelf],
        model_alias=None,
    ):
        # # Get the model to join on the Filter Query
        # joined_model = filter_type._meta.model
        # # Always alias the model
        # joined_model_alias = aliased(joined_model)

        clauses = []
        for value in val:
            # # Join the aliased model onto the query
            # query = query.join(model_field.of_type(joined_model_alias))

            query, _clauses = filter_type.execute_filters(
                query, value, model_alias=model_alias
            )  # , model_alias=joined_model_alias)
            clauses += _clauses

        return query, [or_(*clauses)]

    @classmethod
    def execute_filters(
        cls, query, filter_dict: Dict[str, Any], model_alias=None
    ) -> Tuple[Query, List[Any]]:
        model = cls._meta.model
        if model_alias:
            model = model_alias

        clauses = []

        for field, field_filters in filter_dict.items():
            # Relationships are Dynamic, we need to resolve them fist
            # Maybe we can cache these dynamics to improve efficiency
            # Check with a profiler is required to determine necessity
            input_field = cls._meta.fields[field]
            if isinstance(input_field, graphene.Dynamic):
                input_field = input_field.get_type()
                field_filter_type = input_field.type
            else:
                field_filter_type = cls._meta.fields[field].type
            # raise Exception
            # TODO we need to save the relationship props in the meta fields array
            #  to conduct joins and alias the joins (in case there are duplicate joins: A->B A->C B->C)
            if field == "and":
                query, _clauses = cls.and_logic(
                    query, field_filter_type.of_type, field_filters, model_alias=model
                )
                clauses.extend(_clauses)
            elif field == "or":
                query, _clauses = cls.or_logic(
                    query, field_filter_type.of_type, field_filters, model_alias=model
                )
                clauses.extend(_clauses)
            else:
                # Get the model attr from the inputfield in case the field is aliased in graphql
                model_field = getattr(model, input_field.model_attr or field)
                if issubclass(field_filter_type, BaseTypeFilter):
                    # Get the model to join on the Filter Query
                    joined_model = field_filter_type._meta.model
                    # Always alias the model
                    joined_model_alias = aliased(joined_model)
                    # Join the aliased model onto the query
                    query = query.join(model_field.of_type(joined_model_alias))
                    # Pass the joined query down to the next object type filter for processing
                    query, _clauses = field_filter_type.execute_filters(
                        query, field_filters, model_alias=joined_model_alias
                    )
                    clauses.extend(_clauses)
                if issubclass(field_filter_type, RelationshipFilter):
                    # TODO see above; not yet working
                    relationship_prop = field_filter_type._meta.model
                    # Always alias the model
                    # joined_model_alias = aliased(relationship_prop)

                    # Join the aliased model onto the query
                    # query = query.join(model_field.of_type(joined_model_alias))
                    # todo should we use selectinload here instead of join for large lists?

                    query, _clauses = field_filter_type.execute_filters(
                        query, model, model_field, field_filters, relationship_prop
                    )
                    clauses.extend(_clauses)
                elif issubclass(field_filter_type, FieldFilter):
                    query, _clauses = field_filter_type.execute_filters(
                        query, model_field, field_filters
                    )
                    clauses.extend(_clauses)

        return query, clauses


ScalarFilterInputType = TypeVar("ScalarFilterInputType")


class FieldFilterOptions(InputObjectTypeOptions):
    graphene_type: Type = None


class FieldFilter(graphene.InputObjectType):
    """Basic Filter for Scalars in Graphene.
    We want this filter to use Dynamic fields so it provides the base
    filtering methods ("eq, nEq") for different types of scalars.
    The Dynamic fields will resolve to Meta.filtered_type"""

    @classmethod
    def __init_subclass_with_meta__(cls, graphene_type=None, _meta=None, **options):
        from .converter import convert_sqlalchemy_type

        # get all filter functions

        filter_functions = _get_functions_by_regex(".+_filter$", "_filter$", cls)

        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = FieldFilterOptions(cls)

        if not _meta.graphene_type:
            _meta.graphene_type = graphene_type

        new_filter_fields = {}
        # Generate Graphene Fields from the filter functions based on type hints
        for field_name, _annotations in filter_functions:
            assert (
                "val" in _annotations
            ), "Each filter method must have a value field with valid type annotations"
            # If type is generic, replace with actual type of filter class
            replace_type_vars = {ScalarFilterInputType: _meta.graphene_type}
            field_type = convert_sqlalchemy_type(
                _annotations.get("val", str), replace_type_vars=replace_type_vars
            )
            new_filter_fields.update({field_name: graphene.InputField(field_type)})

        # Add all fields to the meta options. graphene.InputbjectType will take care of the rest
        if _meta.fields:
            _meta.fields.update(new_filter_fields)
        else:
            _meta.fields = new_filter_fields

        # Pass modified meta to the super class
        super(FieldFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    # Abstract methods can be marked using ScalarFilterInputType. See comment on the init method
    @classmethod
    def eq_filter(
        cls, query, field, val: ScalarFilterInputType
    ) -> Union[Tuple[Query, Any], Any]:
        return field == val

    @classmethod
    def n_eq_filter(
        cls, query, field, val: ScalarFilterInputType
    ) -> Union[Tuple[Query, Any], Any]:
        return not_(field == val)

    @classmethod
    def in_filter(cls, query, field, val: List[ScalarFilterInputType]):
        return field.in_(val)

    @classmethod
    def not_in_filter(cls, query, field, val: List[ScalarFilterInputType]):
        return field.notin_(val)

    # TODO add like/ilike

    @classmethod
    def execute_filters(
        cls, query, field, filter_dict: Dict[str, any]
    ) -> Tuple[Query, List[Any]]:
        clauses = []
        for filt, val in filter_dict.items():
            clause = getattr(cls, filt + "_filter")(query, field, val)
            if isinstance(clause, tuple):
                query, clause = clause
            clauses.append(clause)

        return query, clauses


class SQLEnumFilter(FieldFilter):
    """Basic Filter for Scalars in Graphene.
    We want this filter to use Dynamic fields so it provides the base
    filtering methods ("eq, nEq") for different types of scalars.
    The Dynamic fields will resolve to Meta.filtered_type"""

    class Meta:
        graphene_type = graphene.Enum

    # Abstract methods can be marked using ScalarFilterInputType. See comment on the init method
    @classmethod
    def eq_filter(
        cls, query, field, val: ScalarFilterInputType
    ) -> Union[Tuple[Query, Any], Any]:
        return field == val.value

    @classmethod
    def n_eq_filter(
        cls, query, field, val: ScalarFilterInputType
    ) -> Union[Tuple[Query, Any], Any]:
        return not_(field == val.value)


class PyEnumFilter(FieldFilter):
    """Basic Filter for Scalars in Graphene.
    We want this filter to use Dynamic fields so it provides the base
    filtering methods ("eq, nEq") for different types of scalars.
    The Dynamic fields will resolve to Meta.filtered_type"""

    class Meta:
        graphene_type = graphene.Enum

    # Abstract methods can be marked using ScalarFilterInputType. See comment on the init method
    @classmethod
    def eq_filter(
        cls, query, field, val: ScalarFilterInputType
    ) -> Union[Tuple[Query, Any], Any]:
        return field == val

    @classmethod
    def n_eq_filter(
        cls, query, field, val: ScalarFilterInputType
    ) -> Union[Tuple[Query, Any], Any]:
        return not_(field == val)


class StringFilter(FieldFilter):
    class Meta:
        graphene_type = graphene.String

    @classmethod
    def like_filter(cls, query, field, val: ScalarFilterInputType) -> bool:
        return field.like(val)

    @classmethod
    def ilike_filter(cls, query, field, val: ScalarFilterInputType) -> bool:
        return field.ilike(val)

    @classmethod
    def notlike_filter(cls, query, field, val: ScalarFilterInputType) -> bool:
        return field.notlike(val)


class BooleanFilter(FieldFilter):
    class Meta:
        graphene_type = graphene.Boolean


class OrderedFilter(FieldFilter):
    class Meta:
        abstract = True

    @classmethod
    def gt_filter(cls, query, field, val: ScalarFilterInputType) -> bool:
        return field > val

    @classmethod
    def gte_filter(cls, query, field, val: ScalarFilterInputType) -> bool:
        return field >= val

    @classmethod
    def lt_filter(cls, query, field, val: ScalarFilterInputType) -> bool:
        return field < val

    @classmethod
    def lte_filter(cls, query, field, val: ScalarFilterInputType) -> bool:
        return field <= val


class NumberFilter(OrderedFilter):
    """Intermediate Filter class since all Numbers are in an order relationship (support <, > etc)"""

    class Meta:
        abstract = True


class FloatFilter(NumberFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        graphene_type = graphene.Float


class IntFilter(NumberFilter):
    class Meta:
        graphene_type = graphene.Int


class DateFilter(OrderedFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        graphene_type = graphene.Date


class DateTimeFilter(OrderedFilter):
    """Concrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        graphene_type = graphene.DateTime


class IdFilter(FieldFilter):
    class Meta:
        graphene_type = graphene.ID


class RelationshipFilter(graphene.InputObjectType):
    @classmethod
    def __init_subclass_with_meta__(
        cls, base_type_filter=None, model=None, _meta=None, **options
    ):
        if not base_type_filter:
            raise Exception("Relationship Filters must be specific to an object type")
        # Init meta options class if it doesn't exist already
        if not _meta:
            _meta = InputObjectTypeOptions(cls)

        # get all filter functions
        filter_functions = _get_functions_by_regex(".+_filter$", "_filter$", cls)

        relationship_filters = {}

        # Generate Graphene Fields from the filter functions based on type hints
        for field_name, _annotations in filter_functions:
            assert (
                "val" in _annotations
            ), "Each filter method must have a value field with valid type annotations"
            # If type is generic, replace with actual type of filter class
            if is_list(_annotations["val"]):
                relationship_filters.update(
                    {field_name: graphene.InputField(graphene.List(base_type_filter))}
                )
            else:
                relationship_filters.update(
                    {field_name: graphene.InputField(base_type_filter)}
                )

        # Add all fields to the meta options. graphene.InputObjectType will take care of the rest
        if _meta.fields:
            _meta.fields.update(relationship_filters)
        else:
            _meta.fields = relationship_filters

        _meta.model = model
        _meta.base_type_filter = base_type_filter
        super(RelationshipFilter, cls).__init_subclass_with_meta__(
            _meta=_meta, **options
        )

    @classmethod
    def contains_filter(
        cls,
        query,
        parent_model,
        field,
        relationship_prop,
        val: List[ScalarFilterInputType],
    ):
        clauses = []
        for v in val:
            # Always alias the model
            joined_model_alias = aliased(relationship_prop)

            # Join the aliased model onto the query
            query = query.join(field.of_type(joined_model_alias)).distinct()
            # pass the alias so group can join group
            query, _clauses = cls._meta.base_type_filter.execute_filters(
                query, v, model_alias=joined_model_alias
            )
            clauses.append(and_(*_clauses))
        return query, [or_(*clauses)]

    @classmethod
    def contains_exactly_filter(
        cls,
        query,
        parent_model,
        field,
        relationship_prop,
        val: List[ScalarFilterInputType],
    ):
        raise NotImplementedError

    @classmethod
    def execute_filters(
        cls: Type[FieldFilter],
        query,
        parent_model,
        field,
        filter_dict: Dict,
        relationship_prop,
    ) -> Tuple[Query, List[Any]]:
        query, clauses = (query, [])

        for filt, val in filter_dict.items():
            query, _clauses = getattr(cls, filt + "_filter")(
                query, parent_model, field, relationship_prop, val
            )
            clauses += _clauses

        return query, clauses
