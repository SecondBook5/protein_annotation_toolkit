"""
BLAST XML parser.

Parses BLAST XML output format to extract search results and hits.
Uses lxml for efficient XML parsing.
"""

from pathlib import Path
from typing import Dict, List, Optional

import structlog
from lxml import etree as ET

from protein_annotation_toolkit.exceptions import ParsingError

# Set up logger
logger = structlog.get_logger(__name__)


class BlastXMLParser:
    """
    Parser for BLAST XML output format.

    Extracts search metadata and hit information from BLAST results.
    """

    def parse_file(self, file_path: Path, top_n: Optional[int] = None) -> Dict:
        """
        Parse BLAST XML from file.

        Args:
            file_path: Path to BLAST XML file
            top_n: If specified, only return top N hits (by e-value)

        Returns:
            Dictionary containing parsed BLAST data

        Raises:
            FileNotFoundError: If file doesn't exist
            ParsingError: If XML is malformed
        """
        # Check if file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Parse XML file
            tree = ET.parse(str(file_path))
            root = tree.getroot()

            # Parse the XML content
            return self._parse_xml_root(root, top_n)

        except ET.XMLSyntaxError as e:
            raise ParsingError(f"XML syntax error in {file_path}: {e}")
        except Exception as e:
            raise ParsingError(f"Error parsing {file_path}: {e}")

    def parse_string(self, xml_string: str, top_n: Optional[int] = None) -> Dict:
        """
        Parse BLAST XML from string.

        Args:
            xml_string: XML content as string
            top_n: If specified, only return top N hits (by e-value)

        Returns:
            Dictionary containing parsed BLAST data

        Raises:
            ParsingError: If XML is malformed
        """
        try:
            # Parse XML string
            root = ET.fromstring(xml_string.encode('utf-8'))

            # Parse the XML content
            return self._parse_xml_root(root, top_n)

        except ET.XMLSyntaxError as e:
            raise ParsingError(f"XML syntax error: {e}")
        except Exception as e:
            raise ParsingError(f"Error parsing XML: {e}")

    def _parse_xml_root(self, root: ET._Element, top_n: Optional[int]) -> Dict:
        """
        Parse BLAST XML root element.

        Args:
            root: XML root element
            top_n: If specified, only return top N hits

        Returns:
            Dictionary with BLAST data:
            {
                "program": "blastp",
                "database": "nr",
                "query_id": "Query_147503",
                "query_def": "CAR1_DICDI|Cyclic AMP receptor 1",
                "query_length": 392,
                "hits": [
                    {
                        "hit_num": 1,
                        "hit_accession": "XP_644603",
                        "hit_def": "G-protein-coupled receptor...",
                        "hit_length": 392,
                        "hsps": [
                            {
                                "e_value": 0.0,
                                "bit_score": 810.446,
                                "identity": 392,
                                "positive": 392,
                                "gaps": 0,
                                "alignment_length": 392,
                                "query_start": 1,
                                "query_end": 392,
                                "hit_start": 1,
                                "hit_end": 392,
                                "query_seq": "MGLLDGNPA...",
                                "hit_seq": "MGLLDGNPA...",
                                "midline": "MGLLDGNPA..."
                            }
                        ]
                    },
                    ...
                ]
            }
        """
        # Initialize data structure
        data = {
            "program": None,
            "database": None,
            "query_id": None,
            "query_def": None,
            "query_length": None,
            "hits": []
        }

        # Extract program (e.g., "blastp")
        program = root.findtext("BlastOutput_program")
        if program:
            data["program"] = program

        # Extract database (e.g., "nr")
        database = root.findtext("BlastOutput_db")
        if database:
            data["database"] = database

        # Extract query information
        query_id = root.findtext("BlastOutput_query-ID")
        if query_id:
            data["query_id"] = query_id

        query_def = root.findtext("BlastOutput_query-def")
        if query_def:
            data["query_def"] = query_def

        query_len = root.findtext("BlastOutput_query-len")
        if query_len:
            try:
                data["query_length"] = int(query_len)
            except ValueError:
                logger.warning("invalid_query_length", value=query_len)

        # Extract iterations (usually one iteration per query)
        iterations = root.find("BlastOutput_iterations")
        if iterations is None:
            logger.warning("no_iterations_found")
            return data

        # Process first iteration
        iteration = iterations.find("Iteration")
        if iteration is None:
            logger.warning("no_iteration_found")
            return data

        # Extract hits from iteration
        hits = iteration.find("Iteration_hits")
        if hits is None:
            logger.warning("no_hits_found")
            return data

        # Parse each hit
        for hit_elem in hits.findall("Hit"):
            hit_data = self._parse_hit(hit_elem)
            if hit_data:
                data["hits"].append(hit_data)

            # Stop if we've reached the requested number of hits
            if top_n and len(data["hits"]) >= top_n:
                break

        # Log parsing result
        logger.info(
            "parsed_blast_xml",
            program=data["program"],
            database=data["database"],
            query_id=data["query_id"],
            hits_count=len(data["hits"])
        )

        return data

    def _parse_hit(self, hit_elem: ET._Element) -> Optional[Dict]:
        """
        Parse a single Hit element.

        Args:
            hit_elem: Hit XML element

        Returns:
            Dictionary with hit data, or None if parsing fails
        """
        try:
            # Extract hit metadata
            hit_num = hit_elem.findtext("Hit_num")
            hit_id = hit_elem.findtext("Hit_id")
            hit_def = hit_elem.findtext("Hit_def")
            hit_accession = hit_elem.findtext("Hit_accession")
            hit_len = hit_elem.findtext("Hit_len")

            # Parse hit length
            hit_length = None
            if hit_len:
                try:
                    hit_length = int(hit_len)
                except ValueError:
                    pass

            # Initialize hit data
            hit_data = {
                "hit_num": int(hit_num) if hit_num else None,
                "hit_id": hit_id,
                "hit_def": hit_def,
                "hit_accession": hit_accession,
                "hit_length": hit_length,
                "hsps": []
            }

            # Extract HSPs (High-scoring Segment Pairs)
            hsps = hit_elem.find("Hit_hsps")
            if hsps is not None:
                # Usually we want the best HSP (first one)
                # But we'll parse all of them
                for hsp_elem in hsps.findall("Hsp"):
                    hsp_data = self._parse_hsp(hsp_elem)
                    if hsp_data:
                        hit_data["hsps"].append(hsp_data)

            return hit_data

        except Exception as e:
            logger.error("error_parsing_hit", error=str(e))
            return None

    def _parse_hsp(self, hsp_elem: ET._Element) -> Optional[Dict]:
        """
        Parse a single HSP (High-scoring Segment Pair) element.

        Args:
            hsp_elem: Hsp XML element

        Returns:
            Dictionary with HSP data, or None if parsing fails
        """
        try:
            # Extract HSP data
            hsp_data = {
                "hsp_num": self._get_int(hsp_elem, "Hsp_num"),
                "bit_score": self._get_float(hsp_elem, "Hsp_bit-score"),
                "score": self._get_int(hsp_elem, "Hsp_score"),
                "e_value": self._get_float(hsp_elem, "Hsp_evalue"),
                "query_start": self._get_int(hsp_elem, "Hsp_query-from"),
                "query_end": self._get_int(hsp_elem, "Hsp_query-to"),
                "hit_start": self._get_int(hsp_elem, "Hsp_hit-from"),
                "hit_end": self._get_int(hsp_elem, "Hsp_hit-to"),
                "identity": self._get_int(hsp_elem, "Hsp_identity"),
                "positive": self._get_int(hsp_elem, "Hsp_positive"),
                "gaps": self._get_int(hsp_elem, "Hsp_gaps"),
                "alignment_length": self._get_int(hsp_elem, "Hsp_align-len"),
                "query_seq": hsp_elem.findtext("Hsp_qseq"),
                "hit_seq": hsp_elem.findtext("Hsp_hseq"),
                "midline": hsp_elem.findtext("Hsp_midline"),
            }

            return hsp_data

        except Exception as e:
            logger.error("error_parsing_hsp", error=str(e))
            return None

    @staticmethod
    def _get_int(elem: ET._Element, tag: str) -> Optional[int]:
        """
        Extract integer value from XML element.

        Args:
            elem: XML element
            tag: Tag name

        Returns:
            Integer value or None
        """
        text = elem.findtext(tag)
        if text:
            try:
                return int(text)
            except ValueError:
                pass
        return None

    @staticmethod
    def _get_float(elem: ET._Element, tag: str) -> Optional[float]:
        """
        Extract float value from XML element.

        Args:
            elem: XML element
            tag: Tag name

        Returns:
            Float value or None
        """
        text = elem.findtext(tag)
        if text:
            try:
                return float(text)
            except ValueError:
                pass
        return None

    def get_best_hits(
        self,
        blast_data: Dict,
        max_hits: int = 10,
        max_e_value: float = 1e-5
    ) -> List[Dict]:
        """
        Filter BLAST hits to get best matches.

        Args:
            blast_data: Parsed BLAST data from parse_file or parse_string
            max_hits: Maximum number of hits to return
            max_e_value: Maximum e-value threshold

        Returns:
            List of filtered hits, sorted by e-value

        Example:
            >>> parser = BlastXMLParser()
            >>> data = parser.parse_file("blast_results.xml")
            >>> best_hits = parser.get_best_hits(data, max_hits=5, max_e_value=1e-10)
        """
        # Extract hits with their best HSP e-values
        hits_with_evalue = []
        for hit in blast_data.get("hits", []):
            # Get best (lowest) e-value from HSPs
            if hit["hsps"]:
                best_evalue = min(hsp["e_value"] for hsp in hit["hsps"] if hsp["e_value"] is not None)
                # Filter by e-value threshold
                if best_evalue <= max_e_value:
                    hits_with_evalue.append((hit, best_evalue))

        # Sort by e-value (ascending)
        hits_with_evalue.sort(key=lambda x: x[1])

        # Return top N hits
        return [hit for hit, _ in hits_with_evalue[:max_hits]]
