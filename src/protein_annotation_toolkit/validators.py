"""
Input validation functions.

Validates biological identifiers and input data formats.
"""

import re
from typing import Dict, List, Tuple

from protein_annotation_toolkit.exceptions import ValidationError

# UniProt ID format: one letter followed by exactly 5 digits
# Examples: P13773, Q02293, A12345
UNIPROT_ID_PATTERN = re.compile(r"^[A-Za-z]\d{5}$")

# GO term ID format: GO: followed by 7 digits
# Example: GO:0004930
GO_ID_PATTERN = re.compile(r"^GO:\d{7}$")

# PDB ID format: 4 alphanumeric characters
# Example: 1FQG, 4HHB
PDB_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{4}$")

# KEGG pathway ID format: path: followed by organism code and pathway number
# Example: path:ddi00340
KEGG_PATHWAY_PATTERN = re.compile(r"^path:[a-z]{2,4}\d{5}$")


def validate_uniprot_id(uniprot_id: str) -> Tuple[bool, str]:
    """
    Validate UniProt accession ID format.

    UniProt IDs consist of one letter followed by exactly 5 digits.
    Examples of valid IDs: P13773, Q02293, A12345

    Args:
        uniprot_id: The UniProt ID string to validate

    Returns:
        Tuple of (is_valid, error_message)
        - If valid: (True, "")
        - If invalid: (False, descriptive error message)

    Examples:
        >>> validate_uniprot_id("P13773")
        (True, "")
        >>> validate_uniprot_id("P1377")
        (False, "Expected 5 digits, found 4")
        >>> validate_uniprot_id("123456")
        (False, "First character must be a letter")
    """
    # Strip whitespace
    uniprot_id = uniprot_id.strip()

    # Check if empty
    if not uniprot_id:
        return False, "UniProt ID cannot be empty"

    # Check if matches the pattern
    if UNIPROT_ID_PATTERN.match(uniprot_id):
        return True, ""

    # Provide specific error messages based on the issue
    if len(uniprot_id) == 0:
        return False, "UniProt ID cannot be empty"

    # Extract first character and remaining characters
    first_char = uniprot_id[0]
    remaining = uniprot_id[1:]

    # Check if first character is a letter
    if not first_char.isalpha():
        return False, "First character must be a letter"

    # Check if remaining characters are all digits
    if not remaining.isdigit():
        # Find the first non-digit character
        for i, char in enumerate(remaining, start=1):
            if not char.isdigit():
                return False, f"Invalid character '{char}' at position {i + 1}"

    # Check digit count
    if len(remaining) != 5:
        return False, f"Expected 5 digits, found {len(remaining)}"

    # Catch-all for any other format issues
    return False, f"Invalid UniProt ID format: {uniprot_id}"


def validate_uniprot_ids(uniprot_ids: List[str]) -> Dict[str, List[Tuple[str, str]]]:
    """
    Validate a list of UniProt IDs.

    Args:
        uniprot_ids: List of UniProt ID strings to validate

    Returns:
        Dictionary with two keys:
        - "valid": List of valid UniProt IDs
        - "invalid": List of tuples (invalid_id, error_message)

    Example:
        >>> result = validate_uniprot_ids(["P13773", "INVALID", "Q02293"])
        >>> result["valid"]
        ['P13773', 'Q02293']
        >>> result["invalid"]
        [('INVALID', 'Expected 5 digits, found 2')]
    """
    # Initialize result dictionary
    result = {
        "valid": [],
        "invalid": []
    }

    # Validate each ID
    for uniprot_id in uniprot_ids:
        is_valid, error_msg = validate_uniprot_id(uniprot_id)
        if is_valid:
            result["valid"].append(uniprot_id)
        else:
            result["invalid"].append((uniprot_id, error_msg))

    return result


def validate_go_id(go_id: str) -> bool:
    """
    Validate GO term ID format.

    GO IDs consist of "GO:" followed by exactly 7 digits.
    Example: GO:0004930

    Args:
        go_id: The GO term ID to validate

    Returns:
        True if valid, False otherwise

    Raises:
        ValidationError: If the GO ID format is invalid
    """
    # Strip whitespace
    go_id = go_id.strip()

    # Check if matches pattern
    if GO_ID_PATTERN.match(go_id):
        return True

    raise ValidationError(f"Invalid GO term ID format: {go_id}. Expected format: GO:NNNNNNN")


def validate_pdb_id(pdb_id: str) -> bool:
    """
    Validate PDB ID format.

    PDB IDs consist of exactly 4 alphanumeric characters.
    Examples: 1FQG, 4HHB

    Args:
        pdb_id: The PDB ID to validate

    Returns:
        True if valid, False otherwise

    Raises:
        ValidationError: If the PDB ID format is invalid
    """
    # Strip whitespace and convert to uppercase
    pdb_id = pdb_id.strip().upper()

    # Check if matches pattern
    if PDB_ID_PATTERN.match(pdb_id):
        return True

    raise ValidationError(f"Invalid PDB ID format: {pdb_id}. Expected 4 alphanumeric characters")


def validate_kegg_pathway_id(pathway_id: str) -> bool:
    """
    Validate KEGG pathway ID format.

    KEGG pathway IDs consist of "path:" followed by organism code
    (2-4 lowercase letters) and 5 digits.
    Example: path:ddi00340

    Args:
        pathway_id: The KEGG pathway ID to validate

    Returns:
        True if valid, False otherwise

    Raises:
        ValidationError: If the KEGG pathway ID format is invalid
    """
    # Strip whitespace
    pathway_id = pathway_id.strip()

    # Check if matches pattern
    if KEGG_PATHWAY_PATTERN.match(pathway_id):
        return True

    raise ValidationError(
        f"Invalid KEGG pathway ID format: {pathway_id}. "
        "Expected format: path:XXNNNNN (e.g., path:ddi00340)"
    )
