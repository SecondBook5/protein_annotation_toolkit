"""
Unit tests for XML parsers.
"""

import pytest
from pathlib import Path
from protein_annotation_toolkit.parsers import UniProtXMLParser


class TestUniProtXMLParser:
    """Test UniProt XML parsing."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return UniProtXMLParser()

    @pytest.fixture
    def example_xml_dir(self):
        """Get path to example XML files."""
        return Path(__file__).parent.parent.parent / "examples" / "data" / "uniprot_xml"

    def test_parse_p13773(self, parser, example_xml_dir):
        """Test parsing P13773 (Cyclic AMP receptor 1)."""
        xml_file = example_xml_dir / "P13773.xml"
        assert xml_file.exists(), f"Example file not found: {xml_file}"

        data = parser.parse_file(xml_file)

        # Check basic fields
        assert data["accession"] == "P13773"
        assert data["entry_name"] == "CAR1_DICDI"
        assert "receptor" in data["recommended_name"].lower()
        assert data["organism"] == "Dictyostelium discoideum"
        assert data["taxonomy_id"] == 44689

        # Check sequence
        assert data["sequence"] is not None
        assert len(data["sequence"]) > 0
        assert data["sequence_length"] == len(data["sequence"])
        assert data["sequence_length"] == 392

        # Check GO terms
        assert len(data["go_terms"]) > 0
        # Verify structure of GO terms
        for go_term in data["go_terms"]:
            assert "go_id" in go_term
            assert "term" in go_term
            assert go_term["go_id"].startswith("GO:")

    def test_parse_p29274(self, parser, example_xml_dir):
        """Test parsing P29274 (Adenosine receptor A2a)."""
        xml_file = example_xml_dir / "P29274.xml"
        assert xml_file.exists(), f"Example file not found: {xml_file}"

        data = parser.parse_file(xml_file)

        # Check basic fields
        assert data["accession"] == "P29274"
        assert data["entry_name"] == "AA2AR_HUMAN"
        assert "adenosine" in data["recommended_name"].lower()
        assert data["organism"] == "Homo sapiens"
        assert data["taxonomy_id"] == 9606

        # Human protein should have sequence
        assert data["sequence"] is not None
        assert data["sequence_length"] > 0

        # Should have GO terms and PDB structures
        assert len(data["go_terms"]) > 0

    def test_parse_p41595(self, parser, example_xml_dir):
        """Test parsing P41595 (5-hydroxytryptamine receptor 2B)."""
        xml_file = example_xml_dir / "P41595.xml"
        assert xml_file.exists(), f"Example file not found: {xml_file}"

        data = parser.parse_file(xml_file)

        # Check basic fields
        assert data["accession"] == "P41595"
        assert data["organism"] == "Homo sapiens"
        assert data["sequence"] is not None

    def test_parse_all_examples(self, parser, example_xml_dir):
        """Test that all example XML files can be parsed without errors."""
        xml_files = list(example_xml_dir.glob("*.xml"))
        assert len(xml_files) >= 3, "Should have at least 3 example XML files"

        for xml_file in xml_files:
            data = parser.parse_file(xml_file)

            # Every parsed file should have these required fields
            assert "accession" in data
            assert "entry_name" in data
            assert "organism" in data
            assert "sequence" in data
            assert "go_terms" in data
            assert "pdb_crossrefs" in data

            # Accession should be valid format
            assert len(data["accession"]) == 6
            assert data["accession"][0].isalpha()
            assert data["accession"][1:].isdigit()

    def test_parse_missing_file(self, parser):
        """Test that parsing non-existent file raises appropriate error."""
        from protein_annotation_toolkit.exceptions import ParsingError

        with pytest.raises((ParsingError, FileNotFoundError)):
            parser.parse_file(Path("/nonexistent/file.xml"))

    def test_sequence_format(self, parser, example_xml_dir):
        """Test that sequences are properly formatted."""
        xml_file = example_xml_dir / "P13773.xml"
        data = parser.parse_file(xml_file)

        sequence = data["sequence"]

        # Sequence should be uppercase amino acids
        assert sequence.isupper()
        # Should only contain valid amino acid characters
        valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
        assert all(aa in valid_aa for aa in sequence)
        # Should not contain whitespace or newlines
        assert " " not in sequence
        assert "\n" not in sequence

    def test_go_terms_structure(self, parser, example_xml_dir):
        """Test that GO terms have correct structure."""
        xml_file = example_xml_dir / "P13773.xml"
        data = parser.parse_file(xml_file)

        assert len(data["go_terms"]) > 0

        for go_term in data["go_terms"]:
            # Each GO term should be a dict with go_id and term
            assert isinstance(go_term, dict)
            assert "go_id" in go_term
            assert "term" in go_term

            # GO ID should match pattern GO:NNNNNNN
            go_id = go_term["go_id"]
            assert go_id.startswith("GO:")
            assert go_id[3:].isdigit()
            assert len(go_id) >= 10  # GO: + at least 7 digits

            # Term should be non-empty string with category prefix
            term = go_term["term"]
            assert isinstance(term, str)
            assert len(term) > 0
            # Should start with category (P:, F:, or C:)
            assert term[0] in ["P", "F", "C"]
            assert term[1] == ":"

    def test_pdb_crossrefs_structure(self, parser, example_xml_dir):
        """Test that PDB cross-references have correct structure."""
        # Use P29274 which should have PDB structures
        xml_file = example_xml_dir / "P29274.xml"
        data = parser.parse_file(xml_file)

        pdb_refs = data["pdb_crossrefs"]

        # Should be a list (might be empty)
        assert isinstance(pdb_refs, list)

        if len(pdb_refs) > 0:
            for pdb_ref in pdb_refs:
                # Each PDB ref should be a dict
                assert isinstance(pdb_ref, dict)
                assert "pdb_id" in pdb_ref
                assert "method" in pdb_ref
                assert "resolution" in pdb_ref
                assert "chains" in pdb_ref

                # PDB ID should be 4 characters
                assert len(pdb_ref["pdb_id"]) == 4

                # Resolution should be None or a float
                if pdb_ref["resolution"] is not None:
                    assert isinstance(pdb_ref["resolution"], float)

                # Chains should be a list
                assert isinstance(pdb_ref["chains"], list)
