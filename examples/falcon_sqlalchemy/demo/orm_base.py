# coding=utf-8

from __future__ import unicode_literals

import inspect
import datetime
import binascii

import sqlalchemy
import sqlalchemy.sql.sqltypes
import sqlalchemy.types
import sqlalchemy.dialects.mysql
from sqlalchemy.ext.declarative import declarative_base
import uuid
from decimal import Decimal


# Create schema metadata with a constraint naming convention so that all
# constraints are named automatically based on the tables and columns they're
# defined upon. This ensures that all constraints will be given a unique name
# regardless of the backend database which allows for `alembic` to create
# comprehensive migrations of the defined schemata.
metadata = sqlalchemy.MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
      }
)
# create declarative base
Base = declarative_base(metadata=metadata)


class OrmBaseMixin(object):
    # take sqla type and value, produce converted value
    _sqla_types_convert = {
        bytes: lambda t, v: binascii.hexlify(v),
        sqlalchemy.types.Binary: lambda t, v: binascii.hexlify(v),
    }

    _python_instance_convert = {
        datetime.datetime: lambda v: v.isoformat() if v else None,
        datetime.date: lambda v: v.isoformat() if v else None,
        Decimal: lambda v: float(v),
        uuid.UUID: lambda v: v.hex,
    }

    @staticmethod
    def _dictify_scalar(scalar, column, serializable=False):
        """Converts scalar values into a serializable format.

        Args:
            scalar: The value to be converted.
            column (sqlalchemy.Column): The SQLAlchemy column the ``scalar``
                was stored under.
            serializable (bool): Whether to convert ``scalar`` into a format
                that can be serialized.

        Returns:
            The (optionally) serialized version of ``scalar``.
        """

        val = scalar

        # if data must be serializable, apply conversions into base types
        if serializable:
            # first check for conversions of the underlying column type
            col_type = None
            try:
                col_type = getattr(column, "type")
            except Exception:
                # "col" might be a list in the case of a one to many join, skip.
                # we'll see it again when the outer loop opens the container
                pass
            if col_type:
                col_type_type = type(col_type)
                if col_type_type in OrmBaseMixin._sqla_types_convert:
                    val = OrmBaseMixin._sqla_types_convert[col_type_type](
                        col_type,
                        scalar
                    )

            # Convert (some) complex python types into base types
            instance_converters = OrmBaseMixin._python_instance_convert.items()
            for instance, converter in instance_converters:
                if isinstance(scalar, instance):
                    val = converter(scalar)
                    break

        return val

    def _collect_attributes(self):
        """Handles removal of any meta/internal data that is not from our
        underlying table.

        Returns:
            dict: A dictionary keyed on the field name with the value being a
                tuple of the column type and value.
        """

        attributes = {}

        obj_type = type(self)
        column_inspection = sqlalchemy.inspect(obj_type).c
        relationship_inspection = sqlalchemy.inspect(obj_type).relationships

        for member_name, member_value in self.__dict__.items():
            # drop magic sqla keys.
            if member_name.startswith("_"):
                continue

            if (
                    inspect.isfunction(member_value) or
                    inspect.ismethod(member_value)
            ):
                continue

            if member_name in column_inspection:
                member_inspection = column_inspection[member_name]
            elif member_name in relationship_inspection:
                member_inspection = relationship_inspection[member_name]
            else:
                continue

            attributes[member_name] = (member_inspection, member_value)

        return attributes

    def to_dict(self, deep=False, serializable=False):
        """Returns a ``dict`` representation of the ORM'ed DB record.

        Args:
            deep (bool): Whether the perform a recursive conversion of joined
                ORM objects and include them into the ``dict``.
            serializable (bool): Whether to convert leaf-nodes into a format
                that can be serialized.

        Returns:
            dict: A ``dict`` representation of the ORM'ed DB record.
        """

        results = {}

        # walk top level
        attributes = self._collect_attributes()
        for attr_name, (attr_column, attr_value) in attributes.items():

            # if value is compound type and deep=True
            # recursively collect contents.
            if isinstance(attr_value, OrmBaseMixin):
                if not deep:
                    continue
                val = attr_value.to_dict(
                    deep=deep,
                    serializable=serializable
                )

            elif isinstance(attr_value, list):
                if not deep:
                    continue

                val = []
                for sub_attr_value in attr_value:
                    val.append(sub_attr_value.to_dict(
                        deep=deep,
                        serializable=serializable
                    ))

            elif isinstance(attr_value, dict):
                if not deep:
                    continue

                val = {}
                for sub_attr_name, sub_attr_value in attr_value.items():
                    val[sub_attr_name] = sub_attr_value.to_dict(
                        deep=deep,
                        serialisable=serializable
                    )

            # value if scalar, perform any final conversions
            else:
                val = self._dictify_scalar(
                    scalar=attr_value,
                    column=attr_column,
                    serializable=serializable
                )

            results[attr_name] = val

        return results

    def to_string(self, deep=False):
        """Returns a unicode string representation of the ORM'ed DB record.

        Args:
            deep (bool): Whether the perform a recursive conversion of joined
                ORM objects and include them into the string.

        Returns:
            str: A unicode string representation of the ORM'ed DB record.
        """

        attributes = self._collect_attributes()

        msg = "<{0}("
        for attr_idx, attr_name in enumerate(attributes.keys()):
            msg += attr_name + "='{" + str(attr_idx + 1) + "}'"
            if attr_idx < len(attributes) - 1:
                msg += ", "
        msg += ")>"

        values = [type(self).__name__]

        for attr_name, (attr_column, attr_value) in attributes.items():

            if isinstance(attr_value, OrmBaseMixin):
                if not deep:
                    val = "<{0}()>".format(type(attr_value).__name__)
                else:
                    val = attr_value.to_string(deep=deep)
            else:
                val = self._dictify_scalar(
                    scalar=attr_value,
                    column=attr_column,
                    serializable=True
                )

            values.append(val)

        return msg.format(*values)

    def __repr__(self):
        """Returns a unicode string representation of the object

        Returns:
            unicode: A unicode string representation of the object.
        """
        return self.to_string(deep=False)
