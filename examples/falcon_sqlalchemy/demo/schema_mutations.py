# coding=utf-8

from typing import Dict

import graphql
import graphene
import sqlalchemy.orm

from demo.orm import Author
from demo.schema_types import TypeAuthor


class InputAuthor(graphene.InputObjectType):
    name_first = graphene.String(required=True)
    name_last = graphene.String(required=True)


class MutationAuthorCreate(graphene.Mutation):

    class Arguments:
        author = InputAuthor(required=True)

    author = graphene.Field(TypeAuthor)

    @staticmethod
    def mutate(
        args: Dict,
        info: graphql.execution.base.ResolveInfo,
        author=None
    ):

        # Retrieve the session out of the context as the `get_query` method
        # automatically selects the model.
        session = info.context.get("session")  # type: sqlalchemy.orm.Session

        obj = Author()
        obj.name_first = author.name_first
        obj.name_last = author.name_last

        session.add(obj)
        session.commit()

        return MutationAuthorCreate(author=obj)
