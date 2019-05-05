import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from ..registry import reset_global_registry
from .models import Base

test_db_url = 'sqlite://'  # use in-memory database for tests


@pytest.fixture(autouse=True)
def reset_registry():
    reset_global_registry()


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
