"""
SQLAlchemy declarative base and database engine setup.

Uses SQLAlchemy 2.0 style with async support.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


# Define naming convention for constraints
# This ensures consistent naming across migrations
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Create metadata with naming convention
metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """
    Base class for all database models.

    All models inherit from this class.
    """
    # Use the metadata with naming convention
    metadata = metadata
