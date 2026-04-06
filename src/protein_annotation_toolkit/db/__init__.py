"""
Database package.

Exports key database components: models, session management, and base classes.
"""

from protein_annotation_toolkit.db.base import Base
from protein_annotation_toolkit.db.models import (
    BlastHit,
    BlastSearch,
    GOTerm,
    IngestionLog,
    KEGGPathway,
    Organism,
    PDBCrossref,
    Protein,
    ProteinGOTerm,
    ProteinKEGGPathway,
)
from protein_annotation_toolkit.db.session import (
    drop_db,
    get_async_db_session,
    get_async_engine,
    get_db_session,
    get_sync_engine,
    init_db,
)

__all__ = [
    # Base
    "Base",
    # Models
    "Organism",
    "Protein",
    "GOTerm",
    "ProteinGOTerm",
    "PDBCrossref",
    "KEGGPathway",
    "ProteinKEGGPathway",
    "BlastSearch",
    "BlastHit",
    "IngestionLog",
    # Session management
    "get_db_session",
    "get_async_db_session",
    "get_sync_engine",
    "get_async_engine",
    "init_db",
    "drop_db",
]
