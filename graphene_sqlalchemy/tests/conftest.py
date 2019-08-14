import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import graphene

from ..converter import convert_sqlalchemy_composite
from ..registry import reset_global_registry
from .models import Base, CompositeFullName

test_db_url = 'sqlite://'  # use in-memory database for tests


@pytest.fixture(autouse=True)
def reset_registry():
    reset_global_registry()

    # Prevent tests that implicitly depend on Reporter from raising
    # Tests that explicitly depend on this behavior should re-register a converter
    @convert_sqlalchemy_composite.register(CompositeFullName)
    def convert_composite_class(composite, registry):
        return graphene.Field(graphene.Int)


@pytest.yield_fixture(scope="function")
def session():
    db = create_engine(test_db_url)
    connection = db.engine.connect()
    transaction = connection.begin()
    Base.metadata.create_all(connection)

    # options = dict(bind=connection, binds={})
    session_factory = sessionmaker(bind=connection)
    session = scoped_session(session_factory)

    yield session

    # Finalize test here
    transaction.rollback()
    connection.close()
    session.remove()
