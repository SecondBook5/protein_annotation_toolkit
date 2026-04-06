"""
UniProt REST API client.

Fetches protein data from UniProt REST API.
"""

from typing import List, Optional

import structlog

from protein_annotation_toolkit.clients.base import BaseAPIClient
from protein_annotation_toolkit.config import get_settings
from protein_annotation_toolkit.exceptions import APIError

# Set up logger
logger = structlog.get_logger(__name__)


class UniProtClient(BaseAPIClient):
    """
    Client for UniProt REST API.

    Provides methods to fetch protein records in XML format.
    """

    def __init__(self):
        """
        Initialize UniProt client.

        Uses base URL from application settings.
        """
        settings = get_settings()
        super().__init__(base_url=settings.uniprot_api_base)

    async def fetch_xml(self, uniprot_id: str) -> str:
        """
        Fetch UniProt record in XML format.

        Args:
            uniprot_id: UniProt accession (e.g., "P13773")

        Returns:
            XML content as string

        Raises:
            APIError: If fetch fails or protein not found

        Example:
            >>> async with UniProtClient() as client:
            ...     xml = await client.fetch_xml("P13773")
        """
        # Construct URL for XML endpoint
        # Format: https://rest.uniprot.org/uniprotkb/P13773.xml
        url = f"uniprotkb/{uniprot_id}.xml"

        logger.info("fetching_uniprot", uniprot_id=uniprot_id)

        try:
            # Fetch from API
            xml_content = await self.get(url)

            # Validate that we got XML (basic check)
            if not xml_content.strip().startswith("<?xml"):
                raise APIError(f"Invalid XML response for {uniprot_id}")

            logger.info(
                "fetched_uniprot",
                uniprot_id=uniprot_id,
                size=len(xml_content)
            )

            return xml_content

        except APIError as e:
            # Check if it's a 404 (protein not found)
            if "404" in str(e):
                raise APIError(f"UniProt ID not found: {uniprot_id}")
            raise

    async def fetch_xml_batch(self, uniprot_ids: List[str]) -> dict[str, Optional[str]]:
        """
        Fetch multiple UniProt records concurrently.

        Args:
            uniprot_ids: List of UniProt accessions

        Returns:
            Dictionary mapping UniProt ID to XML content
            Failed fetches will have None as value

        Example:
            >>> async with UniProtClient() as client:
            ...     results = await client.fetch_xml_batch(["P13773", "P29274"])
            ...     for uid, xml in results.items():
            ...         if xml:
            ...             print(f"Got {len(xml)} bytes for {uid}")
        """
        import asyncio

        # Create tasks for concurrent fetching
        async def fetch_one(uid: str) -> tuple[str, Optional[str]]:
            """Fetch single record, return (id, xml or None)."""
            try:
                xml = await self.fetch_xml(uid)
                return uid, xml
            except Exception as e:
                logger.warning("fetch_failed", uniprot_id=uid, error=str(e))
                return uid, None

        # Launch all fetch tasks concurrently
        tasks = [fetch_one(uid) for uid in uniprot_ids]
        results = await asyncio.gather(*tasks)

        # Convert to dictionary
        return dict(results)

    async def search(
        self,
        query: str,
        fields: Optional[List[str]] = None,
        size: int = 25
    ) -> str:
        """
        Search UniProt database.

        Args:
            query: Search query (UniProt query syntax)
            fields: Fields to return (e.g., ["accession", "id", "organism_name"])
            size: Maximum number of results

        Returns:
            JSON response as string

        Example:
            >>> async with UniProtClient() as client:
            ...     results = await client.search(
            ...         query="organism_id:44689 AND reviewed:true",
            ...         size=10
            ...     )

        Note:
            This method returns JSON, not XML.
            See UniProt API documentation for query syntax:
            https://www.uniprot.org/help/query-fields
        """
        # Build query parameters
        params = {
            "query": query,
            "size": str(size),
            "format": "json"
        }

        # Add fields if specified
        if fields:
            params["fields"] = ",".join(fields)

        logger.info("searching_uniprot", query=query, size=size)

        # Fetch from search endpoint
        url = "uniprotkb/search"
        result = await self.get(url, params=params)

        logger.info("search_complete", query=query)

        return result
