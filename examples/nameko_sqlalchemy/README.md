Example Nameko+Graphene-SQLAlchemy Project
================================

This example is for those who are not using frameworks like Flask | Django which already have a View wrapper implemented to handle graphql request and response accordingly

If you need a [graphiql](https://github.com/graphql/graphiql) interface on your application, kindly look at [flask_sqlalchemy](../flask_sqlalchemy).

Using [nameko](https://github.com/nameko/nameko) as an example, but you can get rid of `service.py`

The project contains two models, one named `Department` and another
named `Employee`.

Getting started
---------------

First you'll need to get the source of the project. Do this by cloning the
whole Graphene repository:

```bash
# Get the example project code
git clone https://github.com/graphql-python/graphene-sqlalchemy.git
cd graphene-sqlalchemy/examples/nameko_sqlalchemy
```

It is good idea (but not required) to create a virtual environment
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

Now we can install our dependencies:

```bash
pip install -r requirements.txt
```

Now the following command will setup the database, and start the server:

```bash
./run.sh

```

Now head on over to postman and send POST request to:
[http://127.0.0.1:5000/graphql](http://127.0.0.1:5000/graphql)
and run some queries!