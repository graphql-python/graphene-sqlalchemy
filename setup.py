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
    "graphene>=3.0.0b7",
    "promise>=2.3",
    "SQLAlchemy>=1.1",
    "aiodataloader>=0.2.0,<1.0",
    "packaging>=23.0",
]

tests_require = [
    "pytest>=6.2.0,<7.0",
    "pytest-asyncio>=0.18.3",
    "pytest-cov>=2.11.0,<3.0",
    "sqlalchemy_utils>=0.37.0,<1.0",
    "pytest-benchmark>=3.4.0,<4.0",
    "aiosqlite>=0.17.0",
    "nest-asyncio",
    "greenlet",
]

setup(
    name="graphene-sqlalchemy",
    version=version,
    description="Graphene SQLAlchemy integration",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/graphql-python/graphene-sqlalchemy",
    project_urls={
        "Documentation": "https://docs.graphene-python.org/projects/sqlalchemy/en/latest",
    },
    author="Syrus Akbary",
    author_email="me@syrusakbary.com",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    keywords="api graphql protocol rest relay graphene sqlalchemy",
    packages=find_packages(exclude=["tests"]),
    install_requires=requirements,
    extras_require={
        "dev": [
            "tox==3.7.0",  # Should be kept in sync with tox.ini
            "pre-commit==2.19",
            "flake8==4.0.0",
        ],
        "test": tests_require,
    },
    tests_require=tests_require,
)
