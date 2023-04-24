Example Filters Project
================================

This example highlights the ability to filter queries in graphene-sqlalchemy.

The project contains two models, one named `Department` and another
named `Employee`.

Getting started
---------------

First you'll need to get the source of the project. Do this by cloning the
whole Graphene-SQLAlchemy repository:

```bash
# Get the example project code
git clone https://github.com/graphql-python/graphene-sqlalchemy.git
cd graphene-sqlalchemy/examples/filters
```

It is recommended to create a virtual environment
for this project. We'll do this using
[virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/)
to keep things simple,
but you may also find something like
[virtualenvwrapper](https://virtualenvwrapper.readthedocs.org/en/latest/)
to be useful:

```bash
# Create a virtualenv in which we can install the dependencies
virtualenv env
source env/bin/activate
```

Install our dependencies:

```bash
pip install -r requirements.txt
```

The following command will setup the database, and start the server:

```bash
python app.py
```

Now head over to your favorite GraphQL client, POST to [http://127.0.0.1:5000/graphql](http://127.0.0.1:5000/graphql) and run some queries!
