import ast
import re
import sys

from setuptools import find_packages, setup

_version_re = re.compile(r"__version__\s+=\s+(.*)")

with open("graphene_sqlalchemy/__init__.py", "rb") as f:
    version = str(
        ast.literal_eval(_version_re.search(f.read().decode("utf-8")).group(1))
    )

requirements = [
    # To keep things simple, we only support newer versions of Graphene
    "graphene>=2.1.3,<3",
    "promise>=2.3",
    # Tests fail with 1.0.19
    "SQLAlchemy>=1.2,<2",
    "six>=1.10.0,<2",
    "singledispatch>=3.4.0.3,<4",
]
try:
    import enum
except ImportError:  # Python < 2.7 and Python 3.3
    requirements.append("enum34 >= 1.1.6")

tests_require = [
    "pytest==4.3.1",
    "mock==2.0.0",
    "pytest-cov==2.6.1",
    "sqlalchemy_utils==0.33.9",
    "pytest-benchmark==3.2.1",
]

setup(
    name="graphene-sqlalchemy",
    version=version,
    description="Graphene SQLAlchemy integration",
    long_description=open("README.rst").read(),
    url="https://github.com/graphql-python/graphene-sqlalchemy",
    author="Syrus Akbary",
    author_email="me@syrusakbary.com",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    keywords="api graphql protocol rest relay graphene",
    packages=find_packages(exclude=["tests"]),
    install_requires=requirements,
    extras_require={
        "dev": [
            "tox==3.7.0",  # Should be kept in sync with tox.ini
            "coveralls==1.10.0",
            "pre-commit==1.14.4",
        ],
        "test": tests_require,
    },
    tests_require=tests_require,
)
