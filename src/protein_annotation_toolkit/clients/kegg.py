"""
KEGG REST API client.

Fetches pathway and gene information from KEGG REST API.
"""

import re
from typing import Dict, List, Optional

import structlog

from protein_annotation_toolkit.clients.base import BaseAPIClient
from protein_annotation_toolkit.config import get_settings
from protein_annotation_toolkit.exceptions import APIError

# Set up logger
logger = structlog.get_logger(__name__)


class KEGGClient(BaseAPIClient):
    """
    Client for KEGG REST API.

    Provides methods to:
    - Convert UniProt IDs to KEGG gene IDs
    - Fetch pathway information
    - Link genes to pathways
    """

    def __init__(self):
        """
        Initialize KEGG client.

        Uses base URL from application settings.
        """
        settings = get_settings()
        super().__init__(base_url=settings.kegg_api_base)

    async def convert_uniprot_to_kegg(self, uniprot_ids: List[str]) -> Dict[str, List[str]]:
        """
        Convert UniProt IDs to KEGG gene IDs.

        Uses KEGG's conv operation to map UniProt accessions to KEGG gene IDs.

        Args:
            uniprot_ids: List of UniProt accessions

        Returns:
            Dictionary mapping UniProt ID to list of KEGG gene IDs
            Example: {"P13773": ["ddi:DDB_G0267178"]}

        Raises:
            APIError: If conversion fails

        Example:
            >>> async with KEGGClient() as client:
            ...     mapping = await client.convert_uniprot_to_kegg(["P13773", "P29274"])
        """
        # Build batch request
        # Format: /conv/genes/uniprot:P13773+uniprot:P29274
        uniprot_list = "+".join([f"uniprot:{uid}" for uid in uniprot_ids])
        url = f"conv/genes/{uniprot_list}"

        logger.info("converting_uniprot_to_kegg", count=len(uniprot_ids))

        try:
            # Fetch from API
            response = await self.get(url)

            # Parse response
            # Format: "uniprot:P13773\tddi:DDB_G0267178\n"
            mapping: Dict[str, List[str]] = {}

            for line in response.strip().split("\n"):
                if not line:
                    continue

                # Split by tab
                parts = line.split("\t")
                if len(parts) != 2:
                    logger.warning("invalid_conv_line", line=line)
                    continue

                # Extract UniProt ID and KEGG gene ID
                uniprot_part, kegg_gene_id = parts
                # Remove "uniprot:" prefix
                uniprot_id = uniprot_part.split(":")[-1]

                # Add to mapping
                if uniprot_id not in mapping:
                    mapping[uniprot_id] = []
                mapping[uniprot_id].append(kegg_gene_id)

            logger.info(
                "conversion_complete",
                input_count=len(uniprot_ids),
                mapped_count=len(mapping)
            )

            return mapping

        except Exception as e:
            logger.error("conversion_failed", error=str(e))
            # Return empty mapping on error (graceful degradation)
            return {}

    async def get_gene_pathways(self, kegg_gene_id: str) -> List[str]:
        """
        Get pathways associated with a KEGG gene.

        Args:
            kegg_gene_id: KEGG gene identifier (e.g., "ddi:DDB_G0267178")

        Returns:
            List of KEGG pathway IDs (e.g., ["path:ddi00340"])

        Raises:
            APIError: If fetch fails

        Example:
            >>> async with KEGGClient() as client:
            ...     pathways = await client.get_gene_pathways("ddi:DDB_G0267178")
        """
        # Use KEGG link operation
        # Format: /link/pathway/ddi:DDB_G0267178
        url = f"link/pathway/{kegg_gene_id}"

        logger.debug("fetching_gene_pathways", gene_id=kegg_gene_id)

        try:
            # Fetch from API
            response = await self.get(url)

            # Parse response
            # Format: "ddi:DDB_G0267178\tpath:ddi00340\n"
            pathways = []

            for line in response.strip().split("\n"):
                if not line:
                    continue

                # Split by tab
                parts = line.split("\t")
                if len(parts) != 2:
                    continue

                # Extract pathway ID
                _, pathway_id = parts
                pathways.append(pathway_id)

            logger.debug(
                "pathways_found",
                gene_id=kegg_gene_id,
                pathway_count=len(pathways)
            )

            return pathways

        except Exception as e:
            logger.warning("pathway_fetch_failed", gene_id=kegg_gene_id, error=str(e))
            # Return empty list on error
            return []

    async def get_pathway_info(self, pathway_id: str) -> Optional[Dict[str, str]]:
        """
        Get detailed information about a KEGG pathway.

        Args:
            pathway_id: KEGG pathway identifier (e.g., "path:ddi00340" or "ddi00340")

        Returns:
            Dictionary with pathway information:
            {
                "pathway_id": "path:ddi00340",
                "name": "Lysine degradation",
                "class": "Metabolism; Amino acid metabolism"
            }
            Returns None if pathway not found

        Example:
            >>> async with KEGGClient() as client:
            ...     info = await client.get_pathway_info("path:ddi00340")
            ...     print(info["name"])
        """
        # Remove "path:" prefix if present
        pathway_id_clean = pathway_id.replace("path:", "")

        # Use KEGG get operation
        # Format: /get/ddi00340
        url = f"get/{pathway_id_clean}"

        logger.debug("fetching_pathway_info", pathway_id=pathway_id)

        try:
            # Fetch from API
            response = await self.get(url)

            # Parse response (text format)
            info = {
                "pathway_id": pathway_id,
                "name": None,
                "class": None
            }

            # Extract name
            # Format: "NAME        Lysine degradation"
            name_match = re.search(r"NAME\s+(.+)", response)
            if name_match:
                info["name"] = name_match.group(1).strip()

            # Extract class
            # Format: "CLASS       Metabolism; Amino acid metabolism"
            class_match = re.search(r"CLASS\s+(.+)", response)
            if class_match:
                info["class"] = class_match.group(1).strip()

            # Validate that we got at least the name
            if not info["name"]:
                logger.warning("no_pathway_name", pathway_id=pathway_id)
                return None

            logger.debug("pathway_info_fetched", pathway_id=pathway_id, name=info["name"])

            return info

        except Exception as e:
            logger.warning("pathway_info_failed", pathway_id=pathway_id, error=str(e))
            return None

    async def get_pathways_for_protein(self, uniprot_id: str) -> List[Dict[str, str]]:
        """
        Get all KEGG pathways for a protein (convenience method).

        Combines: UniProt→KEGG conversion, gene→pathway lookup, and pathway info fetch.

        Args:
            uniprot_id: UniProt accession

        Returns:
            List of dictionaries with pathway information

        Example:
            >>> async with KEGGClient() as client:
            ...     pathways = await client.get_pathways_for_protein("P13773")
            ...     for pathway in pathways:
            ...         print(f"{pathway['pathway_id']}: {pathway['name']}")
        """
        logger.info("fetching_pathways_for_protein", uniprot_id=uniprot_id)

        # Step 1: Convert UniProt to KEGG gene IDs
        mapping = await self.convert_uniprot_to_kegg([uniprot_id])
        kegg_gene_ids = mapping.get(uniprot_id, [])

        if not kegg_gene_ids:
            logger.info("no_kegg_mapping", uniprot_id=uniprot_id)
            return []

        # Step 2: Get pathways for each gene ID
        all_pathway_ids = set()
        for gene_id in kegg_gene_ids:
            pathway_ids = await self.get_gene_pathways(gene_id)
            all_pathway_ids.update(pathway_ids)

        if not all_pathway_ids:
            logger.info("no_pathways_found", uniprot_id=uniprot_id)
            return []

        # Step 3: Get detailed info for each pathway
        pathways = []
        for pathway_id in all_pathway_ids:
            info = await self.get_pathway_info(pathway_id)
            if info:
                pathways.append(info)

        logger.info(
            "pathways_fetched",
            uniprot_id=uniprot_id,
            pathway_count=len(pathways)
        )

        return pathways
