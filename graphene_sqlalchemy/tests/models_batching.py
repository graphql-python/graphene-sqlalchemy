from __future__ import absolute_import

import enum

from sqlalchemy import (Column, Date, Enum, ForeignKey, Integer, String, Table,
                        func, select)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import column_property, relationship

PetKind = Enum("cat", "dog", name="pet_kind")


class HairKind(enum.Enum):
    LONG = "long"
    SHORT = "short"


Base = declarative_base()

association_table = Table(
    "association",
    Base.metadata,
    Column("pet_id", Integer, ForeignKey("pets.id")),
    Column("reporter_id", Integer, ForeignKey("reporters.id")),
)


class Pet(Base):
    __tablename__ = "pets"
    id = Column(Integer(), primary_key=True)
    name = Column(String(30))
    pet_kind = Column(PetKind, nullable=False)
    hair_kind = Column(Enum(HairKind, name="hair_kind"), nullable=False)
    reporter_id = Column(Integer(), ForeignKey("reporters.id"))


class Reporter(Base):
    __tablename__ = "reporters"

    id = Column(Integer(), primary_key=True)
    first_name = Column(String(30), doc="First name")
    last_name = Column(String(30), doc="Last name")
    email = Column(String(), doc="Email")
    favorite_pet_kind = Column(PetKind)
    pets = relationship(
        "Pet",
        secondary=association_table,
        backref="reporters",
        order_by="Pet.id",
    )
    articles = relationship("Article", backref="reporter")
    favorite_article = relationship("Article", uselist=False)

    column_prop = column_property(
        select([func.cast(func.count(id), Integer)]), doc="Column property"
    )


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer(), primary_key=True)
    headline = Column(String(100))
    pub_date = Column(Date())
    reporter_id = Column(Integer(), ForeignKey("reporters.id"))
