import pytest
from sqlalchemy import select

import graphene
from graphene_sqlalchemy.tests.utils import eventually_await_session
from graphene_sqlalchemy.utils import get_session, is_sqlalchemy_version_less_than

from ..types import SQLAlchemyObjectType
from .models import HairKind, Pet, Reporter
from .test_query import add_test_data, to_std_dicts

if not is_sqlalchemy_version_less_than("1.4"):
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_query_pet_kinds(session, session_factory):
    await add_test_data(session)
    await eventually_await_session(session, "close")

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter

    class Query(graphene.ObjectType):
        reporter = graphene.Field(ReporterType)
        reporters = graphene.List(ReporterType)
        pets = graphene.List(
            PetType, kind=graphene.Argument(PetType.enum_for_field("pet_kind"))
        )

        async def resolve_reporter(self, _info):
            session = get_session(_info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                return (await session.scalars(select(Reporter))).unique().first()
            return session.query(Reporter).first()

        async def resolve_reporters(self, _info):
            session = get_session(_info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                return (await session.scalars(select(Reporter))).unique().all()
            return session.query(Reporter)

        async def resolve_pets(self, _info, kind):
            session = get_session(_info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                query = select(Pet)
                if kind:
                    query = query.filter(Pet.pet_kind == kind.value)
                return (await session.scalars(query)).unique().all()
            query = session.query(Pet)
            if kind:
                query = query.filter_by(pet_kind=kind.value)
            return query

    query = """
        query ReporterQuery {
          reporter {
            firstName
            lastName
            email
            favoritePetKind
            pets {
              name
              petKind
            }
          }
          reporters {
            firstName
            favoritePetKind
          }
          pets(kind: DOG) {
            name
            petKind
          }
        }
    """
    expected = {
        "reporter": {
            "firstName": "John",
            "lastName": "Doe",
            "email": None,
            "favoritePetKind": "CAT",
            "pets": [{"name": "Garfield", "petKind": "CAT"}],
        },
        "reporters": [
            {
                "firstName": "John",
                "favoritePetKind": "CAT",
            },
            {
                "firstName": "Jane",
                "favoritePetKind": "DOG",
            },
        ],
        "pets": [{"name": "Lassie", "petKind": "DOG"}],
    }
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(
        query, context_value={"session": session_factory()}
    )
    assert not result.errors
    assert result.data == expected


@pytest.mark.asyncio
async def test_query_more_enums(session):
    await add_test_data(session)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    class Query(graphene.ObjectType):
        pet = graphene.Field(PetType)

        async def resolve_pet(self, _info):
            session = get_session(_info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                return (await session.scalars(select(Pet))).first()
            return session.query(Pet).first()

    query = """
        query PetQuery {
          pet {
            name,
            petKind
            hairKind
          }
        }
    """
    expected = {"pet": {"name": "Garfield", "petKind": "CAT", "hairKind": "SHORT"}}
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


@pytest.mark.asyncio
async def test_enum_as_argument(session):
    await add_test_data(session)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    class Query(graphene.ObjectType):
        pet = graphene.Field(
            PetType, kind=graphene.Argument(PetType.enum_for_field("pet_kind"))
        )

        async def resolve_pet(self, info, kind=None):
            session = get_session(info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                query = select(Pet)
                if kind:
                    query = query.filter(Pet.pet_kind == kind.value)
                return (await session.scalars(query)).first()
            query = session.query(Pet)
            if kind:
                query = query.filter(Pet.pet_kind == kind.value)
            return query.first()

    query = """
        query PetQuery($kind: PetKind) {
          pet(kind: $kind) {
            name,
            petKind
            hairKind
          }
        }
    """

    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(
        query, variables={"kind": "CAT"}, context_value={"session": session}
    )
    assert not result.errors
    expected = {"pet": {"name": "Garfield", "petKind": "CAT", "hairKind": "SHORT"}}
    assert result.data == expected
    result = await schema.execute_async(
        query, variables={"kind": "DOG"}, context_value={"session": session}
    )
    assert not result.errors
    expected = {"pet": {"name": "Lassie", "petKind": "DOG", "hairKind": "LONG"}}
    result = to_std_dicts(result.data)
    assert result == expected


@pytest.mark.asyncio
async def test_py_enum_as_argument(session):
    await add_test_data(session)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    class Query(graphene.ObjectType):
        pet = graphene.Field(
            PetType,
            kind=graphene.Argument(PetType._meta.fields["hair_kind"].type.of_type),
        )

        async def resolve_pet(self, _info, kind=None):
            session = get_session(_info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                return (
                    await session.scalars(
                        select(Pet).filter(Pet.hair_kind == HairKind(kind))
                    )
                ).first()
            query = session.query(Pet)
            if kind:
                # enum arguments are expected to be strings, not PyEnums
                query = query.filter(Pet.hair_kind == HairKind(kind))
            return query.first()

    query = """
        query PetQuery($kind: HairKind) {
          pet(kind: $kind) {
            name,
            petKind
            hairKind
          }
        }
    """

    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(
        query, variables={"kind": "SHORT"}, context_value={"session": session}
    )
    assert not result.errors
    expected = {"pet": {"name": "Garfield", "petKind": "CAT", "hairKind": "SHORT"}}
    assert result.data == expected
    result = await schema.execute_async(
        query, variables={"kind": "LONG"}, context_value={"session": session}
    )
    assert not result.errors
    expected = {"pet": {"name": "Lassie", "petKind": "DOG", "hairKind": "LONG"}}
    result = to_std_dicts(result.data)
    assert result == expected
