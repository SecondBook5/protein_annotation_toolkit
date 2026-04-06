"""
Parsers package.

Provides parsers for various biological data formats.
"""

from protein_annotation_toolkit.parsers.blast_xml import BlastXMLParser
from protein_annotation_toolkit.parsers.text import (
    parse_ids_from_string,
    parse_uniprot_ids_from_file,
)
from protein_annotation_toolkit.parsers.uniprot_xml import UniProtXMLParser

__all__ = [
    "UniProtXMLParser",
    "BlastXMLParser",
    "parse_uniprot_ids_from_file",
    "parse_ids_from_string",
]
