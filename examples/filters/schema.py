from models import Person as PersonModel
from models import Pet as PetModel
from models import Toy as ToyModel

import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType
from graphene_sqlalchemy.fields import SQLAlchemyConnectionField


class Pet(SQLAlchemyObjectType):
    class Meta:
        model = PetModel
        name = "Pet"
        interfaces = (relay.Node,)
        batching = True


class Person(SQLAlchemyObjectType):
    class Meta:
        model = PersonModel
        name = "Person"
        interfaces = (relay.Node,)
        batching = True


class Toy(SQLAlchemyObjectType):
    class Meta:
        model = ToyModel
        name = "Toy"
        interfaces = (relay.Node,)
        batching = True


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    pets = SQLAlchemyConnectionField(Pet.connection)
    people = SQLAlchemyConnectionField(Person.connection)
    toys = SQLAlchemyConnectionField(Toy.connection)


schema = graphene.Schema(query=Query)
