"""Shared test fixtures and environment setup.

Sets DATABASE_URL before any app modules are imported so that the
import-time engine creation in ``app.database`` doesn't fail when
no real database is available.
"""

import os

# Ensure a DATABASE_URL is set so the app module can import without error.
# Unit tests never touch the database — this value is only used to satisfy
# the import-time engine creation in app.database.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/testdb",
)
