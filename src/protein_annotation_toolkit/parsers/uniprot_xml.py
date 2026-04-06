"""
UniProt XML parser.

Parses UniProt XML format to extract protein information.
Uses lxml for efficient XML parsing.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog
from lxml import etree as ET

from protein_annotation_toolkit.exceptions import ParsingError

# Set up logger
logger = structlog.get_logger(__name__)

# UniProt XML namespace
UNIPROT_NS = "http://uniprot.org/uniprot"
NAMESPACES = {"ns": UNIPROT_NS}


class UniProtXMLParser:
    """
    Parser for UniProt XML format.

    Extracts protein metadata including:
    - Accession and entry name
    - Recommended protein name
    - Organism information
    - Amino acid sequence
    - GO terms
    - PDB cross-references
    """

    def parse_file(self, file_path: Path) -> Dict:
        """
        Parse UniProt XML from file.

        Args:
            file_path: Path to XML file

        Returns:
            Dictionary containing parsed protein data

        Raises:
            FileNotFoundError: If file doesn't exist
            ParsingError: If XML is malformed or required fields missing
        """
        # Check if file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Parse XML file
            tree = ET.parse(str(file_path))
            root = tree.getroot()

            # Parse the XML content
            return self._parse_xml_root(root)

        except ET.XMLSyntaxError as e:
            raise ParsingError(f"XML syntax error in {file_path}: {e}")
        except Exception as e:
            raise ParsingError(f"Error parsing {file_path}: {e}")

    def parse_string(self, xml_string: str) -> Dict:
        """
        Parse UniProt XML from string.

        Args:
            xml_string: XML content as string

        Returns:
            Dictionary containing parsed protein data

        Raises:
            ParsingError: If XML is malformed or required fields missing
        """
        try:
            # Parse XML string
            root = ET.fromstring(xml_string.encode('utf-8'))

            # Parse the XML content
            return self._parse_xml_root(root)

        except ET.XMLSyntaxError as e:
            raise ParsingError(f"XML syntax error: {e}")
        except Exception as e:
            raise ParsingError(f"Error parsing XML: {e}")

    def _parse_xml_root(self, root: ET._Element) -> Dict:
        """
        Parse UniProt XML root element.

        Uses a single-pass traversal to extract all data efficiently.

        Args:
            root: XML root element

        Returns:
            Dictionary with protein data:
            {
                "accession": "P13773",
                "entry_name": "CAR1_DICDI",
                "recommended_name": "Cyclic AMP receptor 1",
                "organism": "Dictyostelium discoideum",
                "taxonomy_id": 44689,
                "sequence": "MGLLDGNPA...",
                "sequence_length": 392,
                "go_terms": [
                    {"go_id": "GO:0004930", "term": "G protein-coupled receptor activity"},
                    ...
                ],
                "pdb_crossrefs": [
                    {"pdb_id": "1FQG", "method": "X-ray", "resolution": 2.8, "chains": ["A"]},
                    ...
                ]
            }
        """
        # Initialize data structure
        data = {
            "accession": None,
            "entry_name": None,
            "recommended_name": None,
            "organism": None,
            "taxonomy_id": None,
            "sequence": None,
            "sequence_length": None,
            "go_terms": [],
            "pdb_crossrefs": [],
        }

        # Find the entry element (first child of root)
        entry = root.find("ns:entry", NAMESPACES)
        if entry is None:
            raise ParsingError("No entry element found in XML")

        # Extract accession (primary UniProt ID)
        # There can be multiple accessions; we want the first one (primary)
        accession_elem = entry.find("ns:accession", NAMESPACES)
        if accession_elem is not None:
            data["accession"] = accession_elem.text

        # Extract entry name (e.g., "CAR1_DICDI")
        name_elem = entry.find("ns:name", NAMESPACES)
        if name_elem is not None:
            data["entry_name"] = name_elem.text

        # Extract recommended protein name
        # Path: entry/protein/recommendedName/fullName
        recommended_name = entry.findtext(
            "ns:protein/ns:recommendedName/ns:fullName",
            namespaces=NAMESPACES
        )
        if recommended_name:
            data["recommended_name"] = recommended_name

        # Extract organism information
        # Path: entry/organism/name[@type="scientific"]
        organism = entry.find(
            'ns:organism/ns:name[@type="scientific"]',
            NAMESPACES
        )
        if organism is not None:
            data["organism"] = organism.text

        # Extract taxonomy ID
        # Path: entry/organism/dbReference[@type="NCBI Taxonomy"]
        taxonomy_ref = entry.find(
            'ns:organism/ns:dbReference[@type="NCBI Taxonomy"]',
            NAMESPACES
        )
        if taxonomy_ref is not None:
            tax_id = taxonomy_ref.get("id")
            if tax_id:
                try:
                    data["taxonomy_id"] = int(tax_id)
                except ValueError:
                    logger.warning("invalid_taxonomy_id", value=tax_id)

        # Extract sequence
        sequence_elem = entry.find("ns:sequence", NAMESPACES)
        if sequence_elem is not None:
            # Remove whitespace from sequence
            sequence = "".join(sequence_elem.text.split())
            data["sequence"] = sequence
            data["sequence_length"] = len(sequence)

            # Also get length attribute if available
            length_attr = sequence_elem.get("length")
            if length_attr:
                try:
                    data["sequence_length"] = int(length_attr)
                except ValueError:
                    pass

        # Extract GO terms and PDB cross-references
        # Iterate through all dbReference elements
        for dbref in entry.findall("ns:dbReference", NAMESPACES):
            db_type = dbref.get("type")

            # Parse GO terms
            if db_type == "GO":
                go_id = dbref.get("id")
                # Find the property element with term name
                term_prop = dbref.find('ns:property[@type="term"]', NAMESPACES)
                if go_id and term_prop is not None:
                    term_name = term_prop.get("value")
                    data["go_terms"].append({
                        "go_id": go_id,
                        "term": term_name
                    })

            # Parse PDB cross-references
            elif db_type == "PDB":
                pdb_id = dbref.get("id")
                if pdb_id:
                    # Extract method and resolution from properties
                    method_prop = dbref.find('ns:property[@type="method"]', NAMESPACES)
                    resolution_prop = dbref.find('ns:property[@type="resolution"]', NAMESPACES)
                    chains_prop = dbref.find('ns:property[@type="chains"]', NAMESPACES)

                    method = method_prop.get("value") if method_prop is not None else None
                    resolution = None
                    chains = []

                    # Parse resolution (only for X-ray)
                    if resolution_prop is not None:
                        try:
                            resolution = float(resolution_prop.get("value"))
                        except (ValueError, TypeError):
                            pass

                    # Parse chain identifiers
                    if chains_prop is not None:
                        chains_str = chains_prop.get("value")
                        if chains_str:
                            # Chains are like "A=1-392, B=1-392"
                            # Extract just the chain letters
                            chains = [c.split("=")[0].strip() for c in chains_str.split(",")]

                    data["pdb_crossrefs"].append({
                        "pdb_id": pdb_id,
                        "method": method,
                        "resolution": resolution,
                        "chains": chains if chains else None
                    })

        # Validate that we got essential data
        if not data["accession"]:
            raise ParsingError("No UniProt accession found in XML")

        # Log parsing result
        logger.info(
            "parsed_uniprot_xml",
            accession=data["accession"],
            go_terms=len(data["go_terms"]),
            pdb_refs=len(data["pdb_crossrefs"])
        )

        return data
