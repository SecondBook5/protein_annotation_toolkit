"""
Custom exception classes for the Protein Annotation Toolkit.

Provides specific exception types for different error scenarios.
"""


class ProteinAnnotationToolkitError(Exception):
    """Base exception class for all toolkit errors."""
    pass


class ValidationError(ProteinAnnotationToolkitError):
    """
    Raised when input validation fails.

    Examples:
    - Invalid UniProt ID format
    - Malformed file input
    - Invalid parameter values
    """
    pass


class APIError(ProteinAnnotationToolkitError):
    """
    Raised when external API calls fail.

    Examples:
    - UniProt API unreachable
    - KEGG API rate limit exceeded
    - BLAST submission failed
    """
    pass


class ParsingError(ProteinAnnotationToolkitError):
    """
    Raised when parsing data fails.

    Examples:
    - Malformed XML
    - Unexpected data structure
    - Missing required fields
    """
    pass


class DatabaseError(ProteinAnnotationToolkitError):
    """
    Raised when database operations fail.

    Examples:
    - Connection failure
    - Query execution error
    - Transaction rollback
    """
    pass


class CacheError(ProteinAnnotationToolkitError):
    """
    Raised when cache operations fail.

    Examples:
    - Redis connection lost
    - Cache serialization error
    """
    pass


class ConfigurationError(ProteinAnnotationToolkitError):
    """
    Raised when configuration is invalid or missing.

    Examples:
    - Missing required environment variable
    - Invalid database URL
    - Malformed config file
    """
    pass
