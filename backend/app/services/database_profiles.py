"""
Database Profiles Registry — preconfigured database environment for compliance control runs.
Confined strictly to Default Compliance DB (SQLite) [SQLITE].
"""

from typing import Any, Optional

DATABASE_PROFILES: list[dict[str, Any]] = [
    {
        "id": "sqlite_default",
        "name": "Default Compliance DB (SQLite)",
        "dialect": "sqlite",
        "host": "Localhost (File)",
        "database": "ai_controls.db",
        "description": "Local operational and compliance database with real active (source_transactions) and archive (archive_transactions) tables.",
        "tables": ["source_transactions", "archive_transactions"],
        "is_active": True,
        "color": "#003B57",
        "icon": "sqlite",
    },
]


def get_all_profiles() -> list[dict[str, Any]]:
    """Return configured database profiles (confined to SQLite)."""
    return DATABASE_PROFILES


def get_profile_by_id(profile_id: Optional[str] = None) -> dict[str, Any]:
    """Retrieve database profile by ID, defaulting to Default Compliance DB (SQLite)."""
    return DATABASE_PROFILES[0]
