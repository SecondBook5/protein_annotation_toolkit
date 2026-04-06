"""
Refresh service for updating protein data.

Handles batch updates and refreshing stale data.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from protein_annotation_toolkit.clients import UniProtClient
from protein_annotation_toolkit.db.models import Protein
from protein_annotation_toolkit.parsers import UniProtXMLParser

logger = structlog.get_logger(__name__)


class RefreshService:
    """Service for refreshing protein data from sources."""

    def __init__(self, session: AsyncSession):
        """
        Initialize refresh service.

        Args:
            session: Async database session
        """
        self.session = session
        self.parser = UniProtXMLParser()

    async def refresh_stale_proteins(
        self,
        days_old: int = 30,
        batch_size: int = 50
    ) -> Dict[str, any]:
        """
        Refresh proteins older than specified days.

        Args:
            days_old: Refresh proteins not updated in this many days
            batch_size: Number of concurrent API requests

        Returns:
            Dictionary with refresh statistics
        """
        logger.info("starting_stale_refresh", days_old=days_old)

        # Calculate cutoff date
        cutoff = datetime.utcnow() - timedelta(days=days_old)

        # Find stale proteins
        result = await self.session.execute(
            select(Protein.uniprot_accession)
            .where(
                (Protein.last_fetched_at < cutoff) |
                (Protein.last_fetched_at.is_(None))
            )
        )
        stale_accessions = [row[0] for row in result.all()]

        logger.info("found_stale_proteins", count=len(stale_accessions))

        if not stale_accessions:
            return {
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "errors": []
            }

        # Refresh proteins
        return await self.refresh_proteins(stale_accessions, batch_size=batch_size)

    async def refresh_proteins(
        self,
        accessions: List[str],
        batch_size: int = 50,
        force: bool = False
    ) -> Dict[str, any]:
        """
        Refresh specific proteins from UniProt API.

        Args:
            accessions: List of UniProt accessions to refresh
            batch_size: Number of concurrent API requests
            force: If True, refresh even if recently updated

        Returns:
            Dictionary with refresh statistics
        """
        logger.info("starting_refresh", count=len(accessions))

        stats = {
            "total": len(accessions),
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

        # Filter accessions if not forcing
        if not force:
            # Check which proteins exist and need updating
            result = await self.session.execute(
                select(Protein.uniprot_accession, Protein.last_fetched_at)
                .where(Protein.uniprot_accession.in_(accessions))
            )
            existing = {row[0]: row[1] for row in result.all()}

            # Skip recently updated (within 1 day)
            cutoff = datetime.utcnow() - timedelta(days=1)
            accessions_to_refresh = [
                acc for acc in accessions
                if acc not in existing or existing[acc] < cutoff
            ]

            stats["skipped"] = len(accessions) - len(accessions_to_refresh)
            accessions = accessions_to_refresh

        if not accessions:
            logger.info("no_proteins_need_refresh")
            return stats

        # Create batches
        batches = [
            accessions[i:i + batch_size]
            for i in range(0, len(accessions), batch_size)
        ]

        # Fetch and update
        async with UniProtClient() as client:
            for batch_num, batch in enumerate(batches, 1):
                logger.info("refreshing_batch", batch_num=batch_num, size=len(batch))

                # Fetch batch
                xml_results = await client.fetch_xml_batch(batch)

                # Process each result
                for accession, xml_content in xml_results.items():
                    if xml_content:
                        try:
                            # Parse XML
                            data = self.parser.parse_string(xml_content)

                            # Update protein
                            await self._update_protein(accession, data)
                            stats["succeeded"] += 1

                        except Exception as e:
                            logger.error("refresh_failed", accession=accession, error=str(e))
                            stats["failed"] += 1
                            stats["errors"].append(f"{accession}: {str(e)}")
                    else:
                        stats["failed"] += 1
                        stats["errors"].append(f"{accession}: Failed to fetch from API")

        # Commit all updates
        await self.session.commit()

        logger.info("refresh_complete", **stats)
        return stats

    async def _update_protein(self, accession: str, data: Dict) -> None:
        """
        Update protein with new data.

        Args:
            accession: UniProt accession
            data: Parsed protein data
        """
        # Get existing protein
        result = await self.session.execute(
            select(Protein).where(Protein.uniprot_accession == accession)
        )
        protein = result.scalar_one_or_none()

        if not protein:
            logger.warning("protein_not_found_for_update", accession=accession)
            return

        # Update fields
        protein.entry_name = data.get("entry_name")
        protein.recommended_name = data.get("recommended_name")
        protein.sequence = data.get("sequence")
        protein.sequence_length = data.get("sequence_length")
        protein.last_fetched_at = datetime.utcnow()
        protein.updated_at = datetime.utcnow()

        logger.info("protein_updated", accession=accession)
