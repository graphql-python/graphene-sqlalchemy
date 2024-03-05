import sqlalchemy
from database import Base
from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

PetKind = Enum("cat", "dog", name="pet_kind")


class Pet(Base):
    __tablename__ = "pets"
    id = Column(Integer(), primary_key=True)
    name = Column(String(30))
    age = Column(Integer())
    kind = Column(PetKind)
    person_id = Column(Integer(), ForeignKey("people.id"))


class Person(Base):
    __tablename__ = "people"
    id = Column(Integer(), primary_key=True)
    name = Column(String(100))
    pets = relationship("Pet", backref="person")


pets_toys_table = sqlalchemy.Table(
    "pets_toys",
    Base.metadata,
    Column("pet_id", ForeignKey("pets.id")),
    Column("toy_id", ForeignKey("toys.id")),
)


class Toy(Base):
    __tablename__ = "toys"
    id = Column(Integer(), primary_key=True)
    name = Column(String(30))
    pets = relationship("Pet", secondary=pets_toys_table, backref="toys")
