"""TiDB database backend for Django 5.2+ using mysql-connector-python.

Extends Oracle's mysql.connector.django to provide full compatibility
with modern Django (4.2 / 5.x) database version checks and TiDB's MySQL 8.0 compatibility.
"""
from typing import Tuple
from django.utils.functional import cached_property
from mysql.connector.django.base import (
    DatabaseWrapper as BaseConnectorDatabaseWrapper,
    DatabaseFeatures as BaseConnectorDatabaseFeatures,
    DatabaseOperations,
    DatabaseClient,
    DatabaseCreation,
    DatabaseIntrospection,
    DatabaseValidation,
    DatabaseSchemaEditor,
    CursorWrapper,
    Error,
    IntegrityError,
    DatabaseError,
    OperationalError,
    ProgrammingError,
    NotSupportedError,
)

__all__ = [
    "DatabaseWrapper",
    "DatabaseFeatures",
    "DatabaseOperations",
    "DatabaseClient",
    "DatabaseCreation",
    "DatabaseIntrospection",
    "DatabaseValidation",
    "DatabaseSchemaEditor",
    "CursorWrapper",
    "Error",
    "IntegrityError",
    "DatabaseError",
    "OperationalError",
    "ProgrammingError",
    "NotSupportedError",
]

DatabaseFeatures = BaseConnectorDatabaseFeatures


class DatabaseWrapper(BaseConnectorDatabaseWrapper):
    vendor = "mysql"
    display_name = "TiDB Cloud (MySQL-compatible)"

    @cached_property
    def mysql_is_mariadb(self) -> bool:
        """TiDB is MySQL-compatible, not MariaDB."""
        return False

    @cached_property
    def is_tidb(self) -> bool:
        """Determine if connected server is PingCAP TiDB."""
        try:
            with self.temporary_connection() as cursor:
                cursor.execute("SELECT VERSION()")
                row = cursor.fetchone()
                if row and "tidb" in str(row[0]).lower():
                    return True
        except Exception:
            pass
        return False

    def get_database_version(self) -> Tuple[int, ...]:
        """Return database version compatible with Django 5.x version checks.

        TiDB provides MySQL 8.0 features (window functions, CTEs, JSON, utf8mb4),
        but defaults its initial protocol handshake string to '5.7.25-TiDB-...'
        for broad legacy MySQL client compatibility. When TiDB is detected,
        we report (8, 0, 11) so Django 5.x recognizes full MySQL 8.0 feature support.
        """
        raw_version = self.mysql_version
        if self.is_tidb and raw_version < (8, 0, 11):
            return (8, 0, 11)
        return raw_version
