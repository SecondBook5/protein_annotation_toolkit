"""
Unit tests for biological identifier validators.
"""

import pytest
from protein_annotation_toolkit.validators import validate_uniprot_id, validate_uniprot_ids


class TestValidateUniProtID:
    """Test UniProt ID validation."""

    def test_valid_uniprot_ids(self):
        """Test that valid UniProt IDs are accepted."""
        valid_ids = [
            "P13773",  # Standard format
            "Q02293",
            "P29274",
            "A12345",  # Letter + 5 digits
            "Z99999",
        ]

        for uid in valid_ids:
            is_valid, error = validate_uniprot_id(uid)
            assert is_valid, f"{uid} should be valid but got error: {error}"
            assert error == ""  # Valid IDs return empty string

    def test_invalid_too_short(self):
        """Test that IDs with too few digits are rejected."""
        is_valid, error = validate_uniprot_id("P1234")
        assert not is_valid
        assert "4" in error  # Should mention found 4 digits
        assert "5" in error  # Should mention expected 5 digits

    def test_invalid_too_long(self):
        """Test that IDs with too many digits are rejected."""
        is_valid, error = validate_uniprot_id("P123456")
        assert not is_valid
        assert "6" in error.lower() or "character" in error.lower()

    def test_invalid_starts_with_digit(self):
        """Test that IDs starting with a digit are rejected."""
        is_valid, error = validate_uniprot_id("1P2345")
        assert not is_valid
        assert "letter" in error.lower() or "start" in error.lower()

    def test_invalid_special_characters(self):
        """Test that IDs with special characters are rejected."""
        invalid_ids = [
            "P1234!",
            "P-2345",
            "P@2345",
            "P 2345",
        ]

        for uid in invalid_ids:
            is_valid, error = validate_uniprot_id(uid)
            assert not is_valid, f"{uid} should be invalid"
            assert error is not None

    def test_invalid_empty_string(self):
        """Test that empty string is rejected."""
        is_valid, error = validate_uniprot_id("")
        assert not is_valid
        assert "empty" in error.lower() or "6" in error

    def test_invalid_only_letters(self):
        """Test that IDs with only letters are rejected."""
        is_valid, error = validate_uniprot_id("ABCDEF")
        assert not is_valid
        assert "invalid character" in error.lower() or "digit" in error.lower()

    def test_case_insensitive(self):
        """Test that validation accepts both upper and lowercase."""
        # Our validator should accept both cases
        is_valid_upper, _ = validate_uniprot_id("P13773")
        is_valid_lower, _ = validate_uniprot_id("p13773")

        # Both should have same validity
        assert is_valid_upper == is_valid_lower


class TestValidateUniProtIDs:
    """Test batch UniProt ID validation."""

    def test_all_valid(self):
        """Test batch validation with all valid IDs."""
        ids = ["P13773", "Q02293", "P29274"]
        result = validate_uniprot_ids(ids)

        assert len(result["valid"]) == 3
        assert len(result["invalid"]) == 0
        assert result["valid"] == ids

    def test_mixed_valid_invalid(self):
        """Test that invalid IDs are separated from valid ones."""
        ids = ["P13773", "INVALID", "Q02293", "P1234"]
        result = validate_uniprot_ids(ids)

        assert len(result["valid"]) == 2
        assert "P13773" in result["valid"]
        assert "Q02293" in result["valid"]

        assert len(result["invalid"]) == 2
        # Invalid entries are tuples of (id, error_message)
        invalid_ids = [item[0] for item in result["invalid"]]
        assert "INVALID" in invalid_ids
        assert "P1234" in invalid_ids

    def test_empty_list(self):
        """Test that empty list returns empty results."""
        result = validate_uniprot_ids([])
        assert result["valid"] == []
        assert result["invalid"] == []

    def test_all_invalid(self):
        """Test that all invalid IDs results in empty valid list."""
        ids = ["INVALID1", "INVALID2", "123456"]
        result = validate_uniprot_ids(ids)

        assert len(result["valid"]) == 0
        assert len(result["invalid"]) == 3

    def test_duplicates_preserved(self):
        """Test that duplicate valid IDs are preserved."""
        ids = ["P13773", "P13773", "Q02293"]
        result = validate_uniprot_ids(ids)

        assert len(result["valid"]) == 3
        assert result["valid"].count("P13773") == 2

    def test_invalid_entries_have_error_messages(self):
        """Test that invalid entries include error messages."""
        ids = ["P13773", "INVALID"]
        result = validate_uniprot_ids(ids)

        assert len(result["invalid"]) == 1
        invalid_id, error_msg = result["invalid"][0]
        assert invalid_id == "INVALID"
        assert len(error_msg) > 0
        assert isinstance(error_msg, str)
