from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, echo=True
)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy.orm import scoped_session as scoped_session_factory

scoped_session = scoped_session_factory(session_factory)

Base.query = scoped_session.query_property()
Base.metadata.bind = engine


def init_db():
    from models import Person, Pet, Toy

    Base.metadata.create_all()
    scoped_session.execute("PRAGMA foreign_keys=on")
    db = scoped_session()

    person1 = Person(name="A")
    person2 = Person(name="B")

    pet1 = Pet(name="Spot", kind="dog")
    pet2 = Pet(name="Milo", kind="cat")

    toy1 = Toy(name="disc")
    toy2 = Toy(name="ball")

    person1.pet = pet1
    person2.pet = pet2

    pet1.toys.append(toy1)
    pet2.toys.append(toy1)
    pet2.toys.append(toy2)

    db.add(person1)
    db.add(person2)
    db.add(pet1)
    db.add(pet2)
    db.add(toy1)
    db.add(toy2)

    db.commit()
