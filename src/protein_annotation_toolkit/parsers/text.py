"""
Text file parsers.

Parses UniProt IDs and other identifiers from text files.
"""

import re
from pathlib import Path
from typing import List, Optional

import structlog

from protein_annotation_toolkit.exceptions import ParsingError
from protein_annotation_toolkit.validators import validate_uniprot_id

# Set up logger
logger = structlog.get_logger(__name__)


def parse_uniprot_ids_from_file(
    file_path: Path,
    prefix: Optional[str] = "UniProt:",
    ignore_invalid: bool = False
) -> List[str]:
    """
    Parse UniProt IDs from a text file.

    Supports files with one ID per line, optionally prefixed with "UniProt:"
    Flexible whitespace handling and case-insensitive prefix matching.

    File format examples:
        UniProt: P13773
        UniProt:P29274
        P41595
        Q02293

    Args:
        file_path: Path to text file containing UniProt IDs
        prefix: Optional prefix before IDs (e.g., "UniProt:"). Set to None to disable.
        ignore_invalid: If True, skip invalid IDs with warning. If False, raise error.

    Returns:
        List of valid UniProt IDs

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file cannot be read
        ParsingError: If no valid IDs found or invalid IDs encountered (when ignore_invalid=False)

    Examples:
        >>> ids = parse_uniprot_ids_from_file(Path("proteins.txt"))
        >>> print(ids)
        ['P13773', 'P29274', 'P41595']
    """
    # Check if file exists
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check if file is readable
    if not file_path.is_file():
        raise ParsingError(f"Not a file: {file_path}")

    # Read file and parse IDs
    valid_ids = []
    invalid_ids = []

    try:
        # Open file for reading
        with open(file_path, 'r', encoding='utf-8') as file:
            # Process each line
            for line_num, line in enumerate(file, start=1):
                # Skip empty lines
                line = line.strip()
                if not line:
                    continue

                # Extract ID from line
                uniprot_id = _extract_id_from_line(line, prefix)

                # Validate extracted ID
                is_valid, error_msg = validate_uniprot_id(uniprot_id)

                if is_valid:
                    # Add to valid IDs list
                    valid_ids.append(uniprot_id)
                    logger.debug(
                        "parsed_id",
                        line_num=line_num,
                        uniprot_id=uniprot_id
                    )
                else:
                    # Handle invalid ID
                    invalid_ids.append((line_num, uniprot_id, error_msg))
                    logger.warning(
                        "invalid_id",
                        line_num=line_num,
                        uniprot_id=uniprot_id,
                        error=error_msg
                    )

                    if not ignore_invalid:
                        raise ParsingError(
                            f"Invalid UniProt ID at line {line_num}: '{uniprot_id}'. {error_msg}"
                        )

    except UnicodeDecodeError as e:
        raise ParsingError(f"Error decoding file {file_path}: {e}")
    except IOError as e:
        raise ParsingError(f"Error reading file {file_path}: {e}")

    # Check if any valid IDs were found
    if not valid_ids:
        if invalid_ids:
            raise ParsingError(
                f"No valid UniProt IDs found in {file_path}. "
                f"Found {len(invalid_ids)} invalid IDs."
            )
        else:
            raise ParsingError(f"No UniProt IDs found in {file_path}")

    # Log summary
    logger.info(
        "parse_complete",
        file=str(file_path),
        valid_count=len(valid_ids),
        invalid_count=len(invalid_ids)
    )

    return valid_ids


def _extract_id_from_line(line: str, prefix: Optional[str]) -> str:
    """
    Extract UniProt ID from a line of text.

    Handles optional prefix and flexible whitespace.

    Args:
        line: Line of text potentially containing a UniProt ID
        prefix: Optional prefix (e.g., "UniProt:")

    Returns:
        Extracted ID string (may not be valid)
    """
    # If prefix is specified, try to extract ID after prefix
    if prefix:
        # Create case-insensitive pattern for prefix
        # Match prefix followed by optional whitespace and the ID
        pattern = re.compile(
            rf"{re.escape(prefix)}\s*(.*)",
            re.IGNORECASE
        )
        match = pattern.search(line)

        if match:
            # Extract the part after the prefix
            uniprot_id_line = match.group(1)
        else:
            # No prefix found, use entire line
            uniprot_id_line = line
    else:
        # No prefix expected, use entire line
        uniprot_id_line = line

    # Remove leading and trailing whitespace
    uniprot_id_line = uniprot_id_line.strip()

    return uniprot_id_line


def parse_ids_from_string(
    text: str,
    prefix: Optional[str] = None,
    ignore_invalid: bool = True
) -> List[str]:
    """
    Parse UniProt IDs from a string.

    Useful for parsing IDs from command-line arguments or other text sources.

    Args:
        text: Text containing UniProt IDs (one per line or comma-separated)
        prefix: Optional prefix before IDs
        ignore_invalid: If True, skip invalid IDs. If False, raise error.

    Returns:
        List of valid UniProt IDs

    Examples:
        >>> ids = parse_ids_from_string("P13773, P29274, P41595")
        >>> print(ids)
        ['P13773', 'P29274', 'P41595']
    """
    # Split by commas or newlines
    lines = re.split(r'[,\n]', text)

    valid_ids = []

    # Process each potential ID
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Extract ID
        uniprot_id = _extract_id_from_line(line, prefix)

        # Validate
        is_valid, error_msg = validate_uniprot_id(uniprot_id)

        if is_valid:
            valid_ids.append(uniprot_id)
        elif not ignore_invalid:
            raise ParsingError(f"Invalid UniProt ID: '{uniprot_id}'. {error_msg}")

    return valid_ids
