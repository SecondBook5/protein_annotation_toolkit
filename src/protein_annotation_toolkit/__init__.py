"""
Protein Annotation Toolkit

A bioinformatics toolkit for protein annotation and database management.
Supports UniProt, KEGG, BLAST, and PDB data sources.
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from protein_annotation_toolkit.config import get_settings

# Export commonly used components
__all__ = ["__version__", "get_settings"]
