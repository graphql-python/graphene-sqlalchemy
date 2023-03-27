from database import init_db
from fastapi import FastAPI
from schema import schema
from starlette_graphene3 import GraphQLApp, make_playground_handler


def create_app() -> FastAPI:
    init_db()
    app = FastAPI()

    app.mount("/graphql", GraphQLApp(schema, on_get=make_playground_handler()))

    return app


app = create_app()
