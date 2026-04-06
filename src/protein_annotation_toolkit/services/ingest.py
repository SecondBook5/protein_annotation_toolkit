"""
Ingestion service.

Orchestrates data ingestion from various sources into the database.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from protein_annotation_toolkit.clients import UniProtClient
from protein_annotation_toolkit.db.models import GOTerm, Organism, PDBCrossref, Protein, ProteinGOTerm
from protein_annotation_toolkit.exceptions import ParsingError, ValidationError
from protein_annotation_toolkit.parsers import UniProtXMLParser, parse_uniprot_ids_from_file

# Set up logger
logger = structlog.get_logger(__name__)


class IngestService:
    """
    Service for ingesting protein data from various sources.

    Handles:
    - Parsing input files
    - Fetching from APIs
    - Parsing XML
    - Storing in database with proper relationships
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize ingest service.

        Args:
            session: Async database session
        """
        self.session = session
        self.parser = UniProtXMLParser()

    async def ingest_from_text_file(
        self,
        file_path: Path,
        fetch_from_api: bool = True,
        batch_size: int = 50
    ) -> Dict[str, any]:
        """
        Ingest proteins from text file containing UniProt IDs.

        Args:
            file_path: Path to text file with UniProt IDs
            fetch_from_api: If True, fetch from UniProt API. If False, expect local XML files.
            batch_size: Number of concurrent API requests

        Returns:
            Dictionary with ingestion statistics

        Example:
            >>> service = IngestService(session)
            >>> stats = await service.ingest_from_text_file(Path("proteins.txt"))
            >>> print(f"Ingested {stats['succeeded']} proteins")
        """
        logger.info("starting_text_file_ingest", file=str(file_path))

        # Parse UniProt IDs from file
        try:
            uniprot_ids = parse_uniprot_ids_from_file(file_path, ignore_invalid=False)
        except (FileNotFoundError, PermissionError, ParsingError) as e:
            logger.error("file_parsing_failed", file=str(file_path), error=str(e))
            return {
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "cached": 0,
                "errors": [str(e)]
            }

        logger.info("parsed_ids", count=len(uniprot_ids))

        # Ingest the IDs
        if fetch_from_api:
            return await self.ingest_from_api(uniprot_ids, batch_size=batch_size)
        else:
            # For local XML files, look in same directory as input file
            xml_dir = file_path.parent
            return await self.ingest_from_xml_directory(xml_dir, uniprot_ids)

    async def ingest_from_api(
        self,
        uniprot_ids: List[str],
        batch_size: int = 50
    ) -> Dict[str, any]:
        """
        Fetch proteins from UniProt API and ingest into database.

        Args:
            uniprot_ids: List of UniProt accessions
            batch_size: Number of concurrent API requests

        Returns:
            Dictionary with ingestion statistics
        """
        logger.info("starting_api_ingest", count=len(uniprot_ids))

        stats = {
            "total": len(uniprot_ids),
            "succeeded": 0,
            "failed": 0,
            "cached": 0,
            "errors": []
        }

        # Create batches
        batches = [
            uniprot_ids[i:i + batch_size]
            for i in range(0, len(uniprot_ids), batch_size)
        ]

        # Process each batch
        async with UniProtClient() as client:
            for batch_num, batch in enumerate(batches, 1):
                logger.info("processing_batch", batch_num=batch_num, size=len(batch))

                # Fetch batch concurrently
                xml_results = await client.fetch_xml_batch(batch)

                # Process each result
                for uniprot_id, xml_content in xml_results.items():
                    if xml_content:
                        try:
                            # Parse and store
                            await self._parse_and_store(uniprot_id, xml_content)
                            stats["succeeded"] += 1
                        except Exception as e:
                            logger.error("ingest_failed", uniprot_id=uniprot_id, error=str(e))
                            stats["failed"] += 1
                            stats["errors"].append(f"{uniprot_id}: {str(e)}")
                    else:
                        stats["failed"] += 1
                        stats["errors"].append(f"{uniprot_id}: Failed to fetch from API")

        logger.info("api_ingest_complete", **stats)
        return stats

    async def ingest_from_xml_directory(
        self,
        xml_dir: Path,
        uniprot_ids: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Ingest proteins from local XML files.

        Args:
            xml_dir: Directory containing UniProt XML files
            uniprot_ids: If provided, only process these IDs. Otherwise process all XML files.

        Returns:
            Dictionary with ingestion statistics
        """
        logger.info("starting_xml_directory_ingest", directory=str(xml_dir))

        # Find XML files
        if uniprot_ids:
            # Look for specific files
            xml_files = [xml_dir / f"{uid}.xml" for uid in uniprot_ids]
            # Filter to files that actually exist
            xml_files = [f for f in xml_files if f.exists()]
        else:
            # Process all XML files in directory
            xml_files = list(xml_dir.glob("*.xml"))

        stats = {
            "total": len(xml_files),
            "succeeded": 0,
            "failed": 0,
            "cached": 0,
            "errors": []
        }

        # Process each file
        for xml_file in xml_files:
            try:
                # Parse XML file
                data = self.parser.parse_file(xml_file)
                uniprot_id = data["accession"]

                # Store in database
                await self._store_protein_data(data)
                stats["succeeded"] += 1

                logger.info("xml_file_ingested", file=xml_file.name, uniprot_id=uniprot_id)

            except Exception as e:
                logger.error("xml_file_failed", file=xml_file.name, error=str(e))
                stats["failed"] += 1
                stats["errors"].append(f"{xml_file.name}: {str(e)}")

        logger.info("xml_directory_ingest_complete", **stats)
        return stats

    async def _parse_and_store(self, uniprot_id: str, xml_content: str) -> None:
        """
        Parse XML content and store in database.

        Args:
            uniprot_id: UniProt accession
            xml_content: XML content as string
        """
        # Parse XML
        data = self.parser.parse_string(xml_content)

        # Store in database
        await self._store_protein_data(data)

    async def _store_protein_data(self, data: Dict) -> None:
        """
        Store parsed protein data in database with all relationships.

        Implements upsert logic - updates if exists, inserts if new.

        Args:
            data: Parsed protein data from UniProtXMLParser
        """
        # Get or create organism
        organism = None
        if data.get("organism"):
            organism = await self._get_or_create_organism(
                scientific_name=data["organism"],
                taxonomy_id=data.get("taxonomy_id")
            )

        # Get or create protein
        protein = await self._get_or_create_protein(
            accession=data["accession"],
            entry_name=data.get("entry_name"),
            recommended_name=data.get("recommended_name"),
            organism=organism,
            sequence=data.get("sequence"),
            sequence_length=data.get("sequence_length")
        )

        # Add GO terms
        if data.get("go_terms"):
            await self._add_go_terms(protein, data["go_terms"])

        # Add PDB cross-references
        if data.get("pdb_crossrefs"):
            await self._add_pdb_crossrefs(protein, data["pdb_crossrefs"])

        # Commit transaction
        await self.session.commit()

        logger.info(
            "protein_stored",
            accession=data["accession"],
            go_terms=len(data.get("go_terms", [])),
            pdb_refs=len(data.get("pdb_crossrefs", []))
        )

    async def _get_or_create_organism(
        self,
        scientific_name: str,
        taxonomy_id: Optional[int] = None
    ) -> Organism:
        """Get existing organism or create new one."""
        # Try to find existing
        result = await self.session.execute(
            select(Organism).where(Organism.scientific_name == scientific_name)
        )
        organism = result.scalar_one_or_none()

        if organism:
            return organism

        # Create new
        organism = Organism(
            scientific_name=scientific_name,
            taxonomy_id=taxonomy_id
        )
        self.session.add(organism)
        await self.session.flush()  # Get ID without committing

        return organism

    async def _get_or_create_protein(
        self,
        accession: str,
        entry_name: Optional[str],
        recommended_name: Optional[str],
        organism: Optional[Organism],
        sequence: Optional[str],
        sequence_length: Optional[int]
    ) -> Protein:
        """Get existing protein or create new one (upsert)."""
        # Try to find existing
        result = await self.session.execute(
            select(Protein).where(Protein.uniprot_accession == accession)
        )
        protein = result.scalar_one_or_none()

        if protein:
            # Update existing
            protein.entry_name = entry_name
            protein.recommended_name = recommended_name
            if organism:
                protein.organism_id = organism.id
            protein.sequence = sequence
            protein.sequence_length = sequence_length
            protein.last_fetched_at = datetime.utcnow()
            protein.updated_at = datetime.utcnow()
        else:
            # Create new
            protein = Protein(
                uniprot_accession=accession,
                entry_name=entry_name,
                recommended_name=recommended_name,
                organism_id=organism.id if organism else None,
                sequence=sequence,
                sequence_length=sequence_length,
                last_fetched_at=datetime.utcnow()
            )
            self.session.add(protein)

        await self.session.flush()  # Get ID
        return protein

    async def _add_go_terms(self, protein: Protein, go_terms_data: List[Dict]) -> None:
        """Add GO term associations to protein."""
        for go_data in go_terms_data:
            # Get or create GO term
            go_term = await self._get_or_create_go_term(
                go_id=go_data["go_id"],
                term_name=go_data["term"]
            )

            # Check if association already exists
            result = await self.session.execute(
                select(ProteinGOTerm).where(
                    ProteinGOTerm.protein_id == protein.id,
                    ProteinGOTerm.go_term_id == go_term.id
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                # Create association
                assoc = ProteinGOTerm(
                    protein_id=protein.id,
                    go_term_id=go_term.id
                )
                self.session.add(assoc)

    async def _get_or_create_go_term(self, go_id: str, term_name: str) -> GOTerm:
        """Get existing GO term or create new one."""
        result = await self.session.execute(
            select(GOTerm).where(GOTerm.go_id == go_id)
        )
        go_term = result.scalar_one_or_none()

        if not go_term:
            go_term = GOTerm(go_id=go_id, term_name=term_name)
            self.session.add(go_term)
            await self.session.flush()

        return go_term

    async def _add_pdb_crossrefs(self, protein: Protein, pdb_data: List[Dict]) -> None:
        """Add PDB cross-references to protein."""
        for pdb_info in pdb_data:
            # Check if already exists
            result = await self.session.execute(
                select(PDBCrossref).where(
                    PDBCrossref.protein_id == protein.id,
                    PDBCrossref.pdb_id == pdb_info["pdb_id"]
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                # Create cross-reference
                # Convert chain list to comma-separated string
                chains = pdb_info.get("chains")
                chain_str = ",".join(chains) if chains else None

                pdb_ref = PDBCrossref(
                    protein_id=protein.id,
                    pdb_id=pdb_info["pdb_id"],
                    method=pdb_info.get("method"),
                    resolution=pdb_info.get("resolution"),
                    chain_ids=chain_str
                )
                self.session.add(pdb_ref)
