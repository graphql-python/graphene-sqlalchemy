# coding: utf-8

"""Main module."""

import sqlalchemy.orm

from demo.api import create_app
from demo.schema import schema


def main():

    # Create engine to local SQLite database.
    engine = sqlalchemy.create_engine("sqlite:///demo.db", echo=True)

    # Prepare a DB session.
    session_maker = sqlalchemy.orm.sessionmaker(bind=engine)
    scoped_session = sqlalchemy.orm.scoped_session(session_maker)

    app = create_app(
        schema=schema,
        scoped_session=scoped_session,
        do_enable_graphiql=True,
    )

    return app


# main sentinel
if __name__ == "__main__":
    main()
