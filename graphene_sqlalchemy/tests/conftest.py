import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .models import Article, Base, Editor, Reporter
from ..registry import reset_global_registry

db = create_engine('sqlite:///test_sqlalchemy.sqlite3')


@pytest.yield_fixture(scope='function')
def session():
    reset_global_registry()
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

@pytest.yield_fixture(scope='function')
def setup_fixtures(session):
    reporter = Reporter(first_name='ABA', last_name='X')
    session.add(reporter)
    reporter2 = Reporter(first_name='ABO', last_name='Y')
    session.add(reporter2)
    article = Article(headline='Hi!')
    article.reporter = reporter
    session.add(article)
    editor = Editor(name="John")
    session.add(editor)
    session.commit()
