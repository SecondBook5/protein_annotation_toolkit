"""
Integration tests for database workflow.

These tests verify that the full ingestion pipeline works:
1. Parse XML files
2. Store in database
3. Query database
"""

import pytest
import asyncio
from pathlib import Path
from sqlalchemy import select
from protein_annotation_toolkit.parsers import UniProtXMLParser
from protein_annotation_toolkit.services.ingest import IngestService
from protein_annotation_toolkit.db.models import Protein, GOTerm, Organism, PDBCrossref
from protein_annotation_toolkit.db.session import get_async_session_local


@pytest.fixture
def example_xml_dir():
    """Get path to example XML files."""
    return Path(__file__).parent.parent.parent / "examples" / "data" / "uniprot_xml"


@pytest.fixture
async def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from protein_annotation_toolkit.db.base import Base

    # Create in-memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.mark.asyncio
async def test_ingest_single_protein(db_session, example_xml_dir):
    """Test ingesting a single protein from XML file."""
    from sqlalchemy.orm import selectinload

    service = IngestService(db_session)
    xml_file = example_xml_dir / "P13773.xml"

    # Parse and ingest
    parser = UniProtXMLParser()
    data = parser.parse_file(xml_file)
    await service._store_protein_data(data)

    # Query back with eager loading of organism
    result = await db_session.execute(
        select(Protein)
        .where(Protein.uniprot_accession == "P13773")
        .options(selectinload(Protein.organism))
    )
    protein = result.scalar_one()

    # Verify protein data
    assert protein.uniprot_accession == "P13773"
    assert protein.entry_name == "CAR1_DICDI"
    assert protein.recommended_name is not None
    assert protein.sequence_length == 392
    assert protein.sequence is not None

    # Verify organism relationship
    assert protein.organism is not None
    assert protein.organism.scientific_name == "Dictyostelium discoideum"
    assert protein.organism.taxonomy_id == 44689


@pytest.mark.asyncio
async def test_ingest_go_terms(db_session, example_xml_dir):
    """Test that GO terms are stored correctly."""
    from protein_annotation_toolkit.db.models import ProteinGOTerm

    service = IngestService(db_session)
    xml_file = example_xml_dir / "P13773.xml"

    # Parse and ingest
    parser = UniProtXMLParser()
    data = parser.parse_file(xml_file)
    await service._store_protein_data(data)

    # Query protein
    result = await db_session.execute(
        select(Protein).where(Protein.uniprot_accession == "P13773")
    )
    protein = result.scalar_one()

    # Check GO term count (should match parsed data)
    assert len(data["go_terms"]) > 0

    # Query GO terms through association table
    result = await db_session.execute(
        select(GOTerm)
        .join(ProteinGOTerm, ProteinGOTerm.go_term_id == GOTerm.id)
        .where(ProteinGOTerm.protein_id == protein.id)
    )
    go_terms = result.scalars().all()

    assert len(go_terms) > 0
    assert len(go_terms) == len(data["go_terms"])

    # Verify structure
    for go_term in go_terms:
        assert go_term.go_id.startswith("GO:")
        assert go_term.term_name is not None


@pytest.mark.asyncio
async def test_ingest_multiple_proteins(db_session, example_xml_dir):
    """Test ingesting multiple proteins."""
    service = IngestService(db_session)
    parser = UniProtXMLParser()

    # Ingest multiple proteins
    protein_ids = ["P13773", "P29274", "P41595"]
    for uid in protein_ids:
        xml_file = example_xml_dir / f"{uid}.xml"
        if xml_file.exists():
            data = parser.parse_file(xml_file)
            await service._store_protein_data(data)

    # Query all proteins
    result = await db_session.execute(select(Protein))
    proteins = result.scalars().all()

    assert len(proteins) >= len(protein_ids)

    # Check accessions
    accessions = [p.uniprot_accession for p in proteins]
    for uid in protein_ids:
        assert uid in accessions


@pytest.mark.asyncio
async def test_organism_deduplication(db_session, example_xml_dir):
    """Test that organisms are not duplicated."""
    service = IngestService(db_session)
    parser = UniProtXMLParser()

    # Ingest two proteins from same organism (Homo sapiens)
    human_proteins = ["P29274", "P41595"]
    for uid in human_proteins:
        xml_file = example_xml_dir / f"{uid}.xml"
        if xml_file.exists():
            data = parser.parse_file(xml_file)
            await service._store_protein_data(data)

    # Query organisms
    result = await db_session.execute(select(Organism))
    organisms = result.scalars().all()

    # Should only have one Homo sapiens organism
    human_orgs = [o for o in organisms if o.scientific_name == "Homo sapiens"]
    assert len(human_orgs) == 1


@pytest.mark.asyncio
async def test_go_term_deduplication(db_session, example_xml_dir):
    """Test that GO terms are not duplicated across proteins."""
    service = IngestService(db_session)
    parser = UniProtXMLParser()

    # Ingest multiple proteins (likely share some GO terms)
    protein_ids = ["P13773", "P29274"]
    for uid in protein_ids:
        xml_file = example_xml_dir / f"{uid}.xml"
        if xml_file.exists():
            data = parser.parse_file(xml_file)
            await service._store_protein_data(data)

    # Query all GO terms
    result = await db_session.execute(select(GOTerm))
    go_terms = result.scalars().all()

    # Check no duplicate GO IDs
    go_ids = [g.go_id for g in go_terms]
    assert len(go_ids) == len(set(go_ids)), "GO terms should be deduplicated"


@pytest.mark.asyncio
async def test_upsert_protein(db_session, example_xml_dir):
    """Test that re-ingesting a protein updates rather than duplicates."""
    service = IngestService(db_session)
    parser = UniProtXMLParser()
    xml_file = example_xml_dir / "P13773.xml"

    # Ingest once
    data = parser.parse_file(xml_file)
    await service._store_protein_data(data)

    # Count proteins
    result = await db_session.execute(select(Protein))
    proteins_first = result.scalars().all()
    count_first = len(proteins_first)

    # Ingest again
    await service._store_protein_data(data)

    # Count proteins again
    result = await db_session.execute(select(Protein))
    proteins_second = result.scalars().all()
    count_second = len(proteins_second)

    # Should still be same count (upsert, not insert)
    assert count_first == count_second
    assert count_first == 1


@pytest.mark.asyncio
async def test_ingest_from_xml_directory(db_session, example_xml_dir):
    """Test the full directory ingestion workflow."""
    service = IngestService(db_session)

    # Get list of XML files
    xml_files = list(example_xml_dir.glob("*.xml"))
    uniprot_ids = [f.stem for f in xml_files]

    # Ingest from directory
    stats = await service.ingest_from_xml_directory(example_xml_dir, uniprot_ids)

    # Check stats
    assert stats["total"] == len(uniprot_ids)
    assert stats["succeeded"] > 0
    assert stats["failed"] == 0

    # Verify proteins in database
    result = await db_session.execute(select(Protein))
    proteins = result.scalars().all()

    assert len(proteins) == stats["succeeded"]
