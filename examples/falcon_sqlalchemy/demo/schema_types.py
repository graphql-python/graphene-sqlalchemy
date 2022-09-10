# coding=utf-8

from typing import List, Dict

import graphql
import graphene
from graphene_sqlalchemy import SQLAlchemyObjectType
import sqlalchemy.orm
from sqlalchemy import func as sqlalchemy_func

from demo.orm import Author
from demo.orm import Book
from demo.orm import AuthorBook


class TypeAuthor(SQLAlchemyObjectType):
    class Meta:
        model = Author


class TypeBook(SQLAlchemyObjectType):
    class Meta:
        model = Book


class TypeAuthorBook(SQLAlchemyObjectType):
    class Meta:
        model = AuthorBook


class TypeCountBooksCoverArtist(graphene.ObjectType):
    cover_artist = graphene.String()
    count_books = graphene.Int()


class TypeStats(graphene.ObjectType):

    count_books_by_cover_artist = graphene.List(
        of_type=TypeCountBooksCoverArtist
    )

    @staticmethod
    def resolve_count_books_by_cover_artist(
        args: Dict,
        info: graphql.execution.base.ResolveInfo,
    ) -> List[TypeCountBooksCoverArtist]:
        # Retrieve the session out of the context as the `get_query` method
        # automatically selects the model.
        session = info.context.get("session")  # type: sqlalchemy.orm.Session

        # Define the `COUNT(books.book_id)` function.
        func_count_books = sqlalchemy_func.count(Book.book_id)

        # Query out the count of books by cover-artist
        query = session.query(Book.cover_artist, func_count_books)
        query = query.group_by(Book.cover_artist)
        results = query.all()

        # Wrap the results of the aggregation in `TypeCountBooksCoverArtist`
        # objects.
        objs = [
            TypeCountBooksCoverArtist(
                cover_artist=result[0],
                count_books=result[1]
            ) for result in results
        ]

        return objs
