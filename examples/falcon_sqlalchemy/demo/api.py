# coding=utf-8

import sqlalchemy.orm
import falcon
import graphene

from demo.resources import ResourceGraphQlSqlAlchemy
from demo.resources import ResourceGraphiQL


def create_app(
    schema: graphene.Schema,
    scoped_session: sqlalchemy.orm.scoped_session,
    do_enable_graphiql: bool,
):
    # Create the API.
    app = falcon.API()

    app.add_route(
        uri_template="/graphql",
        resource=ResourceGraphQlSqlAlchemy(
            schema=schema,
            scoped_session=scoped_session,
        )
    )

    if do_enable_graphiql:
        app.add_route(
            uri_template="/graphiql/",
            resource=ResourceGraphiQL(
                path_graphiql="graphiql",
            )
        )
        app.add_route(
            uri_template="/graphiql/{static_file}",
            resource=ResourceGraphiQL(
                path_graphiql="graphiql",
            )
        )

    return app
