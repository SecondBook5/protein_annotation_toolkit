"""
SQLAlchemy ORM models for the protein annotation database.

Defines normalized schema with proper relationships.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    ARRAY,
    REAL,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from protein_annotation_toolkit.db.base import Base


class Organism(Base):
    """
    Organism table storing taxonomic information.

    Each protein belongs to one organism.
    """
    __tablename__ = "organisms"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Scientific name (e.g., "Dictyostelium discoideum")
    # This is the unique identifier for organisms
    scientific_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Optional common name (e.g., "slime mold")
    common_name: Mapped[Optional[str]] = mapped_column(String(255))

    # NCBI Taxonomy ID (optional)
    taxonomy_id: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    # One organism has many proteins
    proteins: Mapped[List["Protein"]] = relationship(
        "Protein",
        back_populates="organism",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_organisms_scientific_name", "scientific_name"),
        Index("ix_organisms_taxonomy_id", "taxonomy_id"),
        # GIN index for trigram similarity search (added in migration)
    )

    def __repr__(self) -> str:
        return f"<Organism(id={self.id}, name='{self.scientific_name}')>"


class Protein(Base):
    """
    Protein table storing core protein information.

    Central table - all annotations link to proteins.
    """
    __tablename__ = "proteins"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # UniProt accession (e.g., "P13773")
    # This is the unique biological identifier
    uniprot_accession: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # UniProt entry name (e.g., "CAR1_DICDI")
    entry_name: Mapped[Optional[str]] = mapped_column(String(50))

    # Protein recommended name (e.g., "Cyclic AMP receptor 1")
    recommended_name: Mapped[Optional[str]] = mapped_column(Text)

    # Foreign key to organism
    organism_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("organisms.id", ondelete="SET NULL")
    )

    # Amino acid sequence
    sequence: Mapped[Optional[str]] = mapped_column(Text)

    # Sequence length
    sequence_length: Mapped[Optional[int]] = mapped_column(Integer)

    # SHA256 hash of sequence for deduplication
    sequence_hash: Mapped[Optional[str]] = mapped_column(String(64))

    # Computed properties (can be calculated from sequence)
    molecular_weight: Mapped[Optional[float]] = mapped_column(REAL)
    isoelectric_point: Mapped[Optional[float]] = mapped_column(REAL)

    # Track when data was last fetched from UniProt
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    # Many-to-one with organism
    organism: Mapped[Optional["Organism"]] = relationship(
        "Organism",
        back_populates="proteins"
    )

    # Many-to-many with GO terms
    protein_go_terms: Mapped[List["ProteinGOTerm"]] = relationship(
        "ProteinGOTerm",
        back_populates="protein",
        cascade="all, delete-orphan"
    )

    # One-to-many with PDB cross-references
    pdb_crossrefs: Mapped[List["PDBCrossref"]] = relationship(
        "PDBCrossref",
        back_populates="protein",
        cascade="all, delete-orphan"
    )

    # Many-to-many with KEGG pathways
    protein_kegg_pathways: Mapped[List["ProteinKEGGPathway"]] = relationship(
        "ProteinKEGGPathway",
        back_populates="protein",
        cascade="all, delete-orphan"
    )

    # One-to-many with BLAST searches (as query)
    blast_searches: Mapped[List["BlastSearch"]] = relationship(
        "BlastSearch",
        back_populates="query_protein",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_proteins_accession", "uniprot_accession"),
        Index("ix_proteins_organism_id", "organism_id"),
        Index("ix_proteins_sequence_hash", "sequence_hash"),
        # GIN index for trigram similarity search on name
    )

    def __repr__(self) -> str:
        return f"<Protein(id={self.id}, accession='{self.uniprot_accession}')>"


class GOTerm(Base):
    """
    Gene Ontology (GO) terms table.

    Stores GO term definitions. Links to proteins via protein_go_terms.
    """
    __tablename__ = "go_terms"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # GO identifier (e.g., "GO:0004930")
    go_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # GO term name (e.g., "G protein-coupled receptor activity")
    term_name: Mapped[str] = mapped_column(Text, nullable=False)

    # GO ontology type
    # "biological_process", "molecular_function", "cellular_component"
    ontology: Mapped[Optional[str]] = mapped_column(String(30))

    # Term definition
    definition: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Relationships
    # Many-to-many with proteins
    protein_go_terms: Mapped[List["ProteinGOTerm"]] = relationship(
        "ProteinGOTerm",
        back_populates="go_term",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_go_terms_go_id", "go_id"),
        Index("ix_go_terms_ontology", "ontology"),
    )

    def __repr__(self) -> str:
        return f"<GOTerm(id={self.id}, go_id='{self.go_id}')>"


class ProteinGOTerm(Base):
    """
    Join table for protein-GO term many-to-many relationship.

    Includes evidence information for the annotation.
    """
    __tablename__ = "protein_go_terms"

    # Composite primary key
    protein_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("proteins.id", ondelete="CASCADE"),
        primary_key=True
    )
    go_term_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("go_terms.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Evidence code (e.g., "IEA", "IDA", "IPI")
    # See: http://geneontology.org/docs/guide-go-evidence-codes/
    evidence_code: Mapped[Optional[str]] = mapped_column(String(10))

    # Reference (publication or database)
    reference: Mapped[Optional[str]] = mapped_column(Text)

    # Who assigned this annotation
    assigned_by: Mapped[Optional[str]] = mapped_column(String(50))

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Relationships
    protein: Mapped["Protein"] = relationship("Protein", back_populates="protein_go_terms")
    go_term: Mapped["GOTerm"] = relationship("GOTerm", back_populates="protein_go_terms")

    # Indexes
    __table_args__ = (
        Index("ix_protein_go_terms_protein_id", "protein_id"),
        Index("ix_protein_go_terms_go_term_id", "go_term_id"),
    )

    def __repr__(self) -> str:
        return f"<ProteinGOTerm(protein_id={self.protein_id}, go_term_id={self.go_term_id})>"


class PDBCrossref(Base):
    """
    PDB cross-references table.

    Links proteins to PDB structure database entries.
    """
    __tablename__ = "pdb_crossrefs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # PDB identifier (e.g., "1FQG")
    pdb_id: Mapped[str] = mapped_column(String(10), nullable=False)

    # Foreign key to protein
    protein_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("proteins.id", ondelete="CASCADE"),
        nullable=False
    )

    # Experimental method (e.g., "X-ray", "NMR", "Cryo-EM")
    method: Mapped[Optional[str]] = mapped_column(String(50))

    # Resolution in Angstroms (for X-ray and cryo-EM)
    resolution: Mapped[Optional[float]] = mapped_column(REAL)

    # Chain identifiers in the PDB file (stored as comma-separated string for SQLite compatibility)
    # e.g., "A,B,C"
    chain_ids: Mapped[Optional[str]] = mapped_column(Text)

    # Sequence positions covered by structure
    start_position: Mapped[Optional[int]] = mapped_column(Integer)
    end_position: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Relationships
    protein: Mapped["Protein"] = relationship("Protein", back_populates="pdb_crossrefs")

    # Indexes and constraints
    __table_args__ = (
        Index("ix_pdb_crossrefs_pdb_id", "pdb_id"),
        Index("ix_pdb_crossrefs_protein_id", "protein_id"),
    )

    def __repr__(self) -> str:
        return f"<PDBCrossref(id={self.id}, pdb_id='{self.pdb_id}')>"


class KEGGPathway(Base):
    """
    KEGG pathway definitions table.

    Stores KEGG pathway information. Links to proteins via protein_kegg_pathways.
    """
    __tablename__ = "kegg_pathways"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # KEGG pathway identifier (e.g., "path:ddi00340")
    pathway_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Pathway name (e.g., "Lysine degradation")
    pathway_name: Mapped[str] = mapped_column(Text, nullable=False)

    # Pathway category (e.g., "Metabolism", "Genetic Information Processing")
    category: Mapped[Optional[str]] = mapped_column(String(100))

    # Subcategory (e.g., "Amino acid metabolism")
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))

    # Pathway class (e.g., "Metabolism; Amino acid metabolism")
    pathway_class: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Relationships
    # Many-to-many with proteins
    protein_kegg_pathways: Mapped[List["ProteinKEGGPathway"]] = relationship(
        "ProteinKEGGPathway",
        back_populates="kegg_pathway",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_kegg_pathways_pathway_id", "pathway_id"),
        Index("ix_kegg_pathways_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<KEGGPathway(id={self.id}, pathway_id='{self.pathway_id}')>"


class ProteinKEGGPathway(Base):
    """
    Join table for protein-KEGG pathway many-to-many relationship.
    """
    __tablename__ = "protein_kegg_pathways"

    # Composite primary key
    protein_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("proteins.id", ondelete="CASCADE"),
        primary_key=True
    )
    pathway_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("kegg_pathways.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Relationships
    protein: Mapped["Protein"] = relationship("Protein", back_populates="protein_kegg_pathways")
    kegg_pathway: Mapped["KEGGPathway"] = relationship(
        "KEGGPathway",
        back_populates="protein_kegg_pathways"
    )

    # Indexes
    __table_args__ = (
        Index("ix_protein_kegg_pathways_protein_id", "protein_id"),
        Index("ix_protein_kegg_pathways_pathway_id", "pathway_id"),
    )

    def __repr__(self) -> str:
        return f"<ProteinKEGGPathway(protein_id={self.protein_id}, pathway_id={self.pathway_id})>"


class BlastSearch(Base):
    """
    BLAST search metadata table.

    Stores information about BLAST searches performed.
    """
    __tablename__ = "blast_searches"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign key to query protein
    query_protein_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("proteins.id", ondelete="CASCADE"),
        nullable=False
    )

    # BLAST program (e.g., "blastp", "blastn")
    program: Mapped[str] = mapped_column(String(20), nullable=False)

    # BLAST database (e.g., "nr", "swissprot")
    database: Mapped[str] = mapped_column(String(50), nullable=False)

    # Search status ("pending", "running", "completed", "failed")
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)

    # External job ID (e.g., NCBI RID)
    job_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Relationships
    query_protein: Mapped["Protein"] = relationship("Protein", back_populates="blast_searches")
    blast_hits: Mapped[List["BlastHit"]] = relationship(
        "BlastHit",
        back_populates="search",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_blast_searches_query_protein_id", "query_protein_id"),
        Index("ix_blast_searches_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<BlastSearch(id={self.id}, program='{self.program}', database='{self.database}')>"


class BlastHit(Base):
    """
    BLAST hit results table.

    Stores individual hits from BLAST searches.
    """
    __tablename__ = "blast_hits"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign key to BLAST search
    search_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("blast_searches.id", ondelete="CASCADE"),
        nullable=False
    )

    # Hit accession from BLAST result
    hit_accession: Mapped[str] = mapped_column(Text, nullable=False)

    # Foreign key to protein (if we have this protein in our database)
    hit_protein_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("proteins.id", ondelete="SET NULL")
    )

    # BLAST scores and statistics
    e_value: Mapped[float] = mapped_column(Float, nullable=False)
    bit_score: Mapped[Optional[float]] = mapped_column(REAL)
    identity: Mapped[Optional[int]] = mapped_column(Integer)
    positive: Mapped[Optional[int]] = mapped_column(Integer)
    gaps: Mapped[Optional[int]] = mapped_column(Integer)
    alignment_length: Mapped[Optional[int]] = mapped_column(Integer)

    # Alignment positions
    query_start: Mapped[Optional[int]] = mapped_column(Integer)
    query_end: Mapped[Optional[int]] = mapped_column(Integer)
    hit_start: Mapped[Optional[int]] = mapped_column(Integer)
    hit_end: Mapped[Optional[int]] = mapped_column(Integer)

    # Rank within search (1 = best hit)
    hit_rank: Mapped[Optional[int]] = mapped_column(Integer)

    # Aligned sequences (optional - can be large)
    query_sequence: Mapped[Optional[str]] = mapped_column(Text)
    hit_sequence: Mapped[Optional[str]] = mapped_column(Text)
    midline_sequence: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Relationships
    search: Mapped["BlastSearch"] = relationship("BlastSearch", back_populates="blast_hits")

    # Indexes
    __table_args__ = (
        Index("ix_blast_hits_search_id", "search_id"),
        Index("ix_blast_hits_accession", "hit_accession"),
        Index("ix_blast_hits_e_value", "e_value"),
        Index("ix_blast_hits_search_rank", "search_id", "hit_rank"),
    )

    def __repr__(self) -> str:
        return f"<BlastHit(id={self.id}, accession='{self.hit_accession}', e_value={self.e_value})>"


class IngestionLog(Base):
    """
    Ingestion log table for audit trail.

    Tracks data ingestion operations and their outcomes.
    """
    __tablename__ = "ingestion_logs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Source type ("uniprot_xml", "uniprot_api", "blast_xml", "kegg_api")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Source identifier (file path, UniProt ID, etc.)
    source_identifier: Mapped[Optional[str]] = mapped_column(Text)

    # Status ("success", "failed", "partial")
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # Record counts
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Error message if failed
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Execution time in milliseconds
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_ingestion_logs_created_at", "created_at"),
        Index("ix_ingestion_logs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<IngestionLog(id={self.id}, type='{self.source_type}', status='{self.status}')>"
