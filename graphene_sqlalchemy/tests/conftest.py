from typing import Literal

import graphene
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from graphene_sqlalchemy.utils import SQL_VERSION_HIGHER_EQUAL_THAN_1_4
from .models import Base, CompositeFullName
from ..converter import convert_sqlalchemy_composite
from ..registry import reset_global_registry

if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@pytest.fixture(autouse=True)
def reset_registry():
    reset_global_registry()

    # Prevent tests that implicitly depend on Reporter from raising
    # Tests that explicitly depend on this behavior should re-register a converter
    @convert_sqlalchemy_composite.register(CompositeFullName)
    def convert_composite_class(composite, registry):
        return graphene.Field(graphene.Int)


# make a typed literal for session one is sync and one is async
SESSION_TYPE = Literal["sync", "session_factory"]


@pytest.fixture(params=["sync", "async"])
def session_type(request) -> SESSION_TYPE:
    return request.param


@pytest.fixture
def async_session(session_type):
    return session_type == "async"


@pytest.fixture
def test_db_url(session_type: SESSION_TYPE):
    if session_type == "async":
        return "sqlite+aiosqlite://"
    else:
        return "sqlite://"


@pytest.mark.asyncio
@pytest_asyncio.fixture(scope="function")
async def session_factory(session_type: SESSION_TYPE, test_db_url: str):
    if session_type == "async":
        if not SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
            pytest.skip("Async Sessions only work in sql alchemy 1.4 and above")
        engine = create_async_engine(test_db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        await engine.dispose()
    else:
        engine = create_engine(test_db_url)
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, expire_on_commit=False)
        # SQLite in-memory db is deleted when its connection is closed.
        # https://www.sqlite.org/inmemorydb.html
        engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def sync_session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    # SQLite in-memory db is deleted when its connection is closed.
    # https://www.sqlite.org/inmemorydb.html
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
def session(session_factory):
    return session_factory()
