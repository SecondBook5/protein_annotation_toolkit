"""
Query and statistics service.

Provides advanced querying and statistics functionality.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from protein_annotation_toolkit.db.models import (
    GOTerm,
    Organism,
    PDBCrossref,
    Protein,
    ProteinGOTerm,
)

logger = structlog.get_logger(__name__)


class QueryService:
    """Service for advanced protein queries and statistics."""

    def __init__(self, session: AsyncSession):
        """
        Initialize query service.

        Args:
            session: Async database session
        """
        self.session = session

    async def get_statistics(self) -> Dict[str, any]:
        """
        Get database statistics.

        Returns:
            Dictionary with counts and metadata
        """
        stats = {}

        # Protein count
        result = await self.session.execute(select(func.count(Protein.id)))
        stats["protein_count"] = result.scalar_one()

        # Organism count
        result = await self.session.execute(select(func.count(Organism.id)))
        stats["organism_count"] = result.scalar_one()

        # GO term count
        result = await self.session.execute(select(func.count(GOTerm.id)))
        stats["go_term_count"] = result.scalar_one()

        # PDB structure count
        result = await self.session.execute(select(func.count(PDBCrossref.id)))
        stats["pdb_structure_count"] = result.scalar_one()

        # Last updated
        result = await self.session.execute(
            select(func.max(Protein.last_fetched_at))
        )
        last_updated = result.scalar_one()
        stats["last_updated"] = last_updated.isoformat() if last_updated else None

        return stats

    async def get_organism_statistics(self, limit: int = 10) -> List[Dict]:
        """
        Get top organisms by protein count.

        Args:
            limit: Number of top organisms to return

        Returns:
            List of dicts with organism name and count
        """
        result = await self.session.execute(
            select(
                Organism.scientific_name,
                func.count(Protein.id).label("count")
            )
            .join(Protein, Protein.organism_id == Organism.id)
            .group_by(Organism.scientific_name)
            .order_by(desc("count"))
            .limit(limit)
        )

        return [
            {"organism": row[0], "count": row[1]}
            for row in result.all()
        ]

    async def get_go_term_statistics(self, limit: int = 20) -> List[Dict]:
        """
        Get most common GO terms.

        Args:
            limit: Number of GO terms to return

        Returns:
            List of dicts with GO ID, term name, and protein count
        """
        result = await self.session.execute(
            select(
                GOTerm.go_id,
                GOTerm.term_name,
                func.count(ProteinGOTerm.protein_id).label("count")
            )
            .join(ProteinGOTerm, ProteinGOTerm.go_term_id == GOTerm.id)
            .group_by(GOTerm.go_id, GOTerm.term_name)
            .order_by(desc("count"))
            .limit(limit)
        )

        return [
            {"go_id": row[0], "term": row[1], "protein_count": row[2]}
            for row in result.all()
        ]

    async def query_by_organism(
        self,
        organism_name: str,
        limit: Optional[int] = None
    ) -> List[Protein]:
        """
        Query proteins by organism.

        Args:
            organism_name: Scientific name of organism
            limit: Maximum number of results

        Returns:
            List of Protein objects
        """
        query = (
            select(Protein)
            .join(Organism, Protein.organism_id == Organism.id)
            .where(Organism.scientific_name == organism_name)
            .options(selectinload(Protein.organism))
        )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def query_by_go_term(
        self,
        go_id: str,
        include_proteins: bool = False
    ) -> Dict:
        """
        Query proteins by GO term.

        Args:
            go_id: GO term ID (e.g., "GO:0004930")
            include_proteins: If True, include full protein objects

        Returns:
            Dictionary with GO term info and protein list
        """
        # Get GO term
        result = await self.session.execute(
            select(GOTerm).where(GOTerm.go_id == go_id)
        )
        go_term = result.scalar_one_or_none()

        if not go_term:
            return {"go_id": go_id, "found": False}

        # Get associated proteins
        if include_proteins:
            result = await self.session.execute(
                select(Protein)
                .join(ProteinGOTerm, ProteinGOTerm.protein_id == Protein.id)
                .where(ProteinGOTerm.go_term_id == go_term.id)
                .options(selectinload(Protein.organism))
            )
            proteins = list(result.scalars().all())
        else:
            # Just get count
            result = await self.session.execute(
                select(func.count(ProteinGOTerm.protein_id))
                .where(ProteinGOTerm.go_term_id == go_term.id)
            )
            protein_count = result.scalar_one()
            proteins = None

        return {
            "go_id": go_term.go_id,
            "term_name": go_term.term_name,
            "found": True,
            "protein_count": len(proteins) if proteins else protein_count,
            "proteins": proteins if include_proteins else None
        }

    async def query_with_structures(
        self,
        min_resolution: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Protein]:
        """
        Query proteins with PDB structures.

        Args:
            min_resolution: Minimum resolution threshold (in Angstroms)
            limit: Maximum number of results

        Returns:
            List of Protein objects with structures
        """
        query = (
            select(Protein)
            .join(PDBCrossref, PDBCrossref.protein_id == Protein.id)
            .options(selectinload(Protein.organism))
            .distinct()
        )

        if min_resolution is not None:
            query = query.where(
                (PDBCrossref.resolution <= min_resolution) |
                (PDBCrossref.resolution.is_(None))
            )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search_proteins(
        self,
        search_term: str,
        field: str = "name",
        limit: int = 50
    ) -> List[Protein]:
        """
        Search proteins by text.

        Args:
            search_term: Text to search for
            field: Field to search in ("name", "accession", "entry")
            limit: Maximum number of results

        Returns:
            List of matching Protein objects
        """
        search_pattern = f"%{search_term}%"

        if field == "name":
            query = select(Protein).where(
                Protein.recommended_name.ilike(search_pattern)
            )
        elif field == "accession":
            query = select(Protein).where(
                Protein.uniprot_accession.ilike(search_pattern)
            )
        elif field == "entry":
            query = select(Protein).where(
                Protein.entry_name.ilike(search_pattern)
            )
        else:
            raise ValueError(f"Invalid field: {field}")

        query = query.options(selectinload(Protein.organism)).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def export_proteins(
        self,
        output_path: Path,
        format: str = "csv",
        organism: Optional[str] = None,
        go_term: Optional[str] = None
    ) -> int:
        """
        Export proteins to file.

        Args:
            output_path: Output file path
            format: Export format ("csv", "json", "tsv")
            organism: Filter by organism name
            go_term: Filter by GO term ID

        Returns:
            Number of proteins exported
        """
        # Build query
        query = select(Protein).options(selectinload(Protein.organism))

        # Apply filters
        if organism:
            query = query.join(Organism, Protein.organism_id == Organism.id).where(
                Organism.scientific_name == organism
            )

        if go_term:
            query = (
                query
                .join(ProteinGOTerm, ProteinGOTerm.protein_id == Protein.id)
                .join(GOTerm, ProteinGOTerm.go_term_id == GOTerm.id)
                .where(GOTerm.go_id == go_term)
            )

        # Execute query
        result = await self.session.execute(query)
        proteins = list(result.scalars().all())

        # Export based on format
        if format == "csv":
            self._export_csv(proteins, output_path)
        elif format == "tsv":
            self._export_csv(proteins, output_path, delimiter="\t")
        elif format == "json":
            self._export_json(proteins, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info("exported_proteins", count=len(proteins), format=format, path=str(output_path))
        return len(proteins)

    def _export_csv(self, proteins: List[Protein], path: Path, delimiter: str = ",") -> None:
        """Export proteins to CSV/TSV."""
        with open(path, "w", newline="") as f:
            writer = csv.writer(f, delimiter=delimiter)

            # Header
            writer.writerow([
                "accession",
                "entry_name",
                "name",
                "organism",
                "taxonomy_id",
                "sequence_length",
                "sequence",
                "last_fetched"
            ])

            # Data
            for p in proteins:
                writer.writerow([
                    p.uniprot_accession,
                    p.entry_name or "",
                    p.recommended_name or "",
                    p.organism.scientific_name if p.organism else "",
                    p.organism.taxonomy_id if p.organism else "",
                    p.sequence_length or "",
                    p.sequence or "",
                    p.last_fetched_at.isoformat() if p.last_fetched_at else ""
                ])

    def _export_json(self, proteins: List[Protein], path: Path) -> None:
        """Export proteins to JSON."""
        data = []
        for p in proteins:
            data.append({
                "accession": p.uniprot_accession,
                "entry_name": p.entry_name,
                "name": p.recommended_name,
                "organism": p.organism.scientific_name if p.organism else None,
                "taxonomy_id": p.organism.taxonomy_id if p.organism else None,
                "sequence_length": p.sequence_length,
                "sequence": p.sequence,
                "last_fetched": p.last_fetched_at.isoformat() if p.last_fetched_at else None
            })

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
