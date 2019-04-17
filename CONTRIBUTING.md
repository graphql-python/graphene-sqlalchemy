## Local Development

Set up our development dependencies:

```sh
pip install -e ".[dev]"
pre-commit install
```

We use `tox` to test this library against different versions of `python` and `SQLAlchemy`.
While developping locally, it is usually fine to run the tests against the most recent versions:

```sh
tox -e py37  # Python 3.7, SQLAlchemy < 2.0
tox -e py37 -- -v -s  # Verbose output
tox -e py37 -- -k test_query  # Only test_query.py
```

Our linters will run automatically when committing via git hooks but you can also run them manually:

```sh
tox -e pre-commit
```

## Release Process

1. Update the version number in graphene_sqlalchemy/__init__.py via a PR.

2. Once the PR is merged, tag the commit on master with the new version (only maintainers of the repo can do this). For example, "v2.1.2". Travis will then automatically build this tag and release it to Pypi.

3. Make sure to create a new release on github (via the release tab) that lists all the changes that went into the new version.
