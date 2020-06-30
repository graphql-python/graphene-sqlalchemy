# coding=utf-8

from typing import List, Dict, Union

import graphql
import graphene

from demo.orm import Author
from demo.orm import Book
from demo.schema_types import TypeAuthor
from demo.schema_types import TypeBook
from demo.schema_types import TypeAuthorBook
from demo.schema_types import TypeStats
from demo.schema_types import TypeCountBooksCoverArtist
from demo.schema_mutations import MutationAuthorCreate
from demo.utils import apply_requested_fields


class Query(graphene.ObjectType):

    author = graphene.Field(
        TypeAuthor,
        author_id=graphene.Argument(type=graphene.Int, required=False),
        name_first=graphene.Argument(type=graphene.String, required=False),
        name_last=graphene.Argument(type=graphene.String, required=False),
    )

    books = graphene.List(
        of_type=TypeBook,
        title=graphene.Argument(type=graphene.String, required=False),
        year=graphene.Argument(type=graphene.Int, required=False),
    )

    stats = graphene.Field(type=TypeStats)

    @staticmethod
    def resolve_stats(
        args: Dict,
        info: graphql.execution.base.ResolveInfo,
    ):
        return TypeStats

    @staticmethod
    def resolve_author(
        args: Dict,
        info: graphql.execution.base.ResolveInfo,
        author_id: Union[int, None] = None,
        name_first: Union[str, None] = None,
        name_last: Union[str, None] = None,
    ):

        query = TypeAuthor.get_query(info=info)

        if author_id:
            query = query.filter(Author.author_id == author_id)

        if name_first:
            query = query.filter(Author.name_first == name_first)

        if name_last:
            query = query.filter(Author.name_last == name_last)

        # Limit query to the requested fields only.
        query = apply_requested_fields(info=info, query=query, orm_class=Author)

        author = query.first()

        return author

    @staticmethod
    def resolve_books(
        args: Dict,
        info: graphql.execution.base.ResolveInfo,
        title: Union[str, None] = None,
        year: Union[int, None] = None,
    ):
        query = TypeBook.get_query(info=info)

        if title:
            query = query.filter(Book.title == title)

        if year:
            query = query.filter(Book.year == year)

        # Limit query to the requested fields only.
        query = apply_requested_fields(info=info, query=query, orm_class=Book)

        books = query.all()

        return books


class Mutation(graphene.ObjectType):
    create_author = MutationAuthorCreate.Field()


schema = graphene.Schema(
    query=Query,
    mutation=Mutation,
    types=[
        TypeAuthor,
        TypeBook,
        TypeAuthorBook,
        TypeStats,
        TypeCountBooksCoverArtist
    ]
)
