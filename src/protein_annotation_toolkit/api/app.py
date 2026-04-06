"""
FastAPI web application for Protein Annotation Toolkit.

Provides RESTful API endpoints for querying and exporting protein data.
"""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from protein_annotation_toolkit.db import get_async_db_session
from protein_annotation_toolkit.services.query import QueryService


# Pydantic models for API responses
class ProteinBase(BaseModel):
    """Base protein model."""
    accession: str = Field(..., description="UniProt accession")
    entry_name: Optional[str] = Field(None, description="Entry name")
    name: Optional[str] = Field(None, description="Recommended protein name")
    organism: Optional[str] = Field(None, description="Organism scientific name")
    taxonomy_id: Optional[int] = Field(None, description="NCBI taxonomy ID")
    sequence_length: Optional[int] = Field(None, description="Sequence length in amino acids")


class ProteinDetail(ProteinBase):
    """Detailed protein model with sequence."""
    sequence: Optional[str] = Field(None, description="Amino acid sequence")
    last_fetched: Optional[str] = Field(None, description="Last update timestamp")


class GOTermInfo(BaseModel):
    """GO term information."""
    go_id: str = Field(..., description="GO term ID (e.g., GO:0004930)")
    term_name: Optional[str] = Field(None, description="GO term name")
    protein_count: int = Field(..., description="Number of associated proteins")


class StatsSummary(BaseModel):
    """Database statistics summary."""
    protein_count: int
    organism_count: int
    go_term_count: int
    pdb_structure_count: int
    last_updated: Optional[str] = None


class OrganismStats(BaseModel):
    """Organism statistics."""
    organism: str
    count: int


class SearchRequest(BaseModel):
    """Search request model."""
    search_term: str = Field(..., description="Text to search for")
    field: str = Field("name", description="Field to search (name, accession, entry)")
    limit: int = Field(50, description="Maximum results", ge=1, le=1000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    yield
    # Shutdown
    pass


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="Protein Annotation Toolkit API",
        description="RESTful API for protein database queries and exports",
        version="0.1.0",
        lifespan=lifespan
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", tags=["System"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    # Statistics endpoints
    @app.get("/api/stats/summary", response_model=StatsSummary, tags=["Statistics"])
    async def get_stats_summary():
        """
        Get database statistics summary.

        Returns counts of proteins, organisms, GO terms, and PDB structures.
        """
        async with get_async_db_session() as session:
            service = QueryService(session)
            stats = await service.get_statistics()
            return stats

    @app.get("/api/stats/organisms", response_model=List[OrganismStats], tags=["Statistics"])
    async def get_organism_stats(
        limit: int = Query(10, ge=1, le=100, description="Number of top organisms")
    ):
        """
        Get top organisms by protein count.
        """
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.get_organism_statistics(limit=limit)

    @app.get("/api/stats/go-terms", response_model=List[GOTermInfo], tags=["Statistics"])
    async def get_go_term_stats(
        limit: int = Query(20, ge=1, le=100, description="Number of GO terms")
    ):
        """
        Get most common GO terms.
        """
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.get_go_term_statistics(limit=limit)

    # Protein query endpoints
    @app.get("/api/proteins/{accession}", response_model=ProteinDetail, tags=["Proteins"])
    async def get_protein(accession: str):
        """
        Get protein by UniProt accession.

        Args:
            accession: UniProt accession (e.g., P13773)

        Returns:
            Protein details including sequence
        """
        from sqlalchemy import select
        from protein_annotation_toolkit.db.models import Protein

        async with get_async_db_session() as session:
            result = await session.execute(
                select(Protein).where(Protein.uniprot_accession == accession)
            )
            protein = result.scalar_one_or_none()

            if not protein:
                raise HTTPException(status_code=404, detail="Protein not found")

            return {
                "accession": protein.uniprot_accession,
                "entry_name": protein.entry_name,
                "name": protein.recommended_name,
                "organism": protein.organism.scientific_name if protein.organism else None,
                "taxonomy_id": protein.organism.taxonomy_id if protein.organism else None,
                "sequence_length": protein.sequence_length,
                "sequence": protein.sequence,
                "last_fetched": protein.last_fetched_at.isoformat() if protein.last_fetched_at else None
            }

    @app.get("/api/proteins", response_model=List[ProteinBase], tags=["Proteins"])
    async def list_proteins(
        limit: int = Query(50, ge=1, le=1000, description="Maximum results"),
        organism: Optional[str] = Query(None, description="Filter by organism")
    ):
        """
        List proteins with optional filters.

        Args:
            limit: Maximum number of results
            organism: Filter by organism scientific name

        Returns:
            List of proteins
        """
        async with get_async_db_session() as session:
            service = QueryService(session)

            if organism:
                proteins = await service.query_by_organism(organism, limit=limit)
            else:
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload
                from protein_annotation_toolkit.db.models import Protein

                result = await session.execute(
                    select(Protein)
                    .options(selectinload(Protein.organism))
                    .limit(limit)
                )
                proteins = list(result.scalars().all())

            return [
                {
                    "accession": p.uniprot_accession,
                    "entry_name": p.entry_name,
                    "name": p.recommended_name,
                    "organism": p.organism.scientific_name if p.organism else None,
                    "taxonomy_id": p.organism.taxonomy_id if p.organism else None,
                    "sequence_length": p.sequence_length
                }
                for p in proteins
            ]

    @app.post("/api/search", response_model=List[ProteinBase], tags=["Search"])
    async def search_proteins(request: SearchRequest):
        """
        Search proteins by text.

        Search in protein name, accession, or entry name fields.

        Args:
            request: Search parameters

        Returns:
            List of matching proteins
        """
        async with get_async_db_session() as session:
            service = QueryService(session)
            proteins = await service.search_proteins(
                request.search_term,
                field=request.field,
                limit=request.limit
            )

            return [
                {
                    "accession": p.uniprot_accession,
                    "entry_name": p.entry_name,
                    "name": p.recommended_name,
                    "organism": p.organism.scientific_name if p.organism else None,
                    "taxonomy_id": p.organism.taxonomy_id if p.organism else None,
                    "sequence_length": p.sequence_length
                }
                for p in proteins
            ]

    @app.get("/api/go-terms/{go_id}", response_model=GOTermInfo, tags=["GO Terms"])
    async def get_go_term(
        go_id: str,
        include_proteins: bool = Query(False, description="Include protein list")
    ):
        """
        Get GO term information.

        Args:
            go_id: GO term ID (e.g., GO:0004930)
            include_proteins: Include list of associated proteins

        Returns:
            GO term information and protein count
        """
        async with get_async_db_session() as session:
            service = QueryService(session)
            result = await service.query_by_go_term(go_id, include_proteins=include_proteins)

            if not result["found"]:
                raise HTTPException(status_code=404, detail="GO term not found")

            response = {
                "go_id": result["go_id"],
                "term_name": result["term_name"],
                "protein_count": result["protein_count"]
            }

            if include_proteins and result["proteins"]:
                # Could add proteins list to response model if needed
                pass

            return response

    return app


# For running with uvicorn directly
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
