"""Portable SQLAlchemy column types for PostgreSQL and SQLite.

* ``GUID`` — stores UUIDs natively on PostgreSQL and as CHAR(32) on SQLite.
* ``PortableJSON`` — uses the dialect-native JSON on PostgreSQL and the
  generic ``sqlalchemy.types.JSON`` everywhere else.
"""

import uuid

from sqlalchemy import types
from sqlalchemy.dialects import postgresql


class GUID(types.TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's native ``UUID`` type when available, otherwise stores
    as ``CHAR(32)`` (hex without dashes).
    """

    impl = types.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(types.CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        # SQLite: store as 32-char hex string.
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


# Alias — resolves to the dialect-native JSON on every backend SQLAlchemy
# supports (including SQLite via the built-in ``types.JSON``).
PortableJSON = types.JSON
