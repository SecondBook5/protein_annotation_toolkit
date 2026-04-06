"""
API clients package.

Provides async clients for external APIs.
"""

from protein_annotation_toolkit.clients.base import BaseAPIClient
from protein_annotation_toolkit.clients.blast import BlastClient
from protein_annotation_toolkit.clients.kegg import KEGGClient
from protein_annotation_toolkit.clients.uniprot import UniProtClient

__all__ = [
    "BaseAPIClient",
    "UniProtClient",
    "KEGGClient",
    "BlastClient",
]
