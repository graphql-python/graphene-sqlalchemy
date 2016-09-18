#!/bin/bash

# Install the required scripts with
# pip install autoflake autopep8 isort
autoflake ./examples/ ./graphene_sqlalchemy/ -r --remove-unused-variables --remove-all-unused-imports --in-place
autopep8 ./examples/ ./graphene_sqlalchemy/ -r --in-place --experimental --aggressive --max-line-length 120
isort -rc ./examples/ ./graphene_sqlalchemy/
