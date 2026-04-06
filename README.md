# Protein Annotation Toolkit

A professional bioinformatics toolkit for protein data management and analysis. Integrates UniProt, KEGG, and BLAST databases with a modern async Python architecture.

**Built to showcase**: Computational biology domain knowledge, async Python development, database design, API integration, and software engineering best practices.

## Features

- **Biological Identifier Validation**: Rigorous validation with detailed error messages for UniProt IDs
- **XML Parsing**: Parse UniProt and BLAST XML formats with robust error handling
- **REST API Integration**: Async clients for UniProt and KEGG with retry logic and rate limiting
- **Database Storage**: Normalized SQLAlchemy 2.0 schema supporting PostgreSQL and SQLite
- **Concurrent Operations**: Batch API requests with aiohttp for high throughput
- **Rich CLI Interface**: Beautiful terminal output with progress bars and formatted tables
- **Interactive Tutorial**: Comprehensive Jupyter notebook demonstrating all features

## Quick Start

```bash
# Install from source
pip install -e .

# Run the simple demonstration
python examples/simple_demo.py

# Or explore the interactive tutorial
jupyter notebook examples/Tutorial.ipynb
```

**Output Preview:**
```
Step 1: Validate UniProt IDs
  ✓ P13773 is valid
  ✗ INVALID is invalid: ID must be exactly 6 characters (1 letter + 5 digits)
  ✓ P29274 is valid

Step 2: Parse UniProt XML File
Parsed protein: P13773
  Entry Name: CY5_DICDI
  Protein: Adenylate cyclase B
  Organism: Dictyostelium discoideum
  Sequence Length: 392 aa

GO Terms (29 total)  |  PDB Structures (0 entries)  |  Sequence Preview
```

## Installation

### Prerequisites

- **Python 3.11+**
- **For production**: PostgreSQL 13+ (optional, SQLite works for development)

### Install from Source

```bash
# Clone repository
git clone <repository-url>
cd protein_annotation_toolkit

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package with dependencies
pip install -e .

# Install Jupyter for the tutorial notebook
pip install jupyter
```

### Configuration

Create a `.env` file in the project root:

```bash
# For development/demo (SQLite - no setup required)
DATABASE_URL=sqlite+aiosqlite:///./protein_annotation.db

# For production (PostgreSQL)
# DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/protein_annotation_db

# Optional: Add your email for NCBI BLAST submission
# NCBI_EMAIL=your.email@example.com
```

**Note**: The examples work out-of-the-box with SQLite. For PostgreSQL, ensure the database exists and is accessible.

## Usage

### Interactive Tutorial (Recommended)

The **Tutorial.ipynb** notebook provides a comprehensive walkthrough:

```bash
jupyter notebook examples/Tutorial.ipynb
```

**Tutorial Contents:**
1. **Biological Identifier Validation** - Validate UniProt IDs with detailed error messages
2. **XML Parsing** - Parse UniProt XML to extract protein metadata, sequences, GO terms
3. **API Integration** - Fetch data from UniProt REST API (single and batch operations)
4. **KEGG Pathways** - Retrieve pathway annotations for proteins
5. **BLAST Analysis** - Parse BLAST XML output and extract top hits
6. **Complete Workflow** - End-to-end protein analysis combining all features

### Simple Demo Script

For a quick demonstration without Jupyter:

```bash
python examples/simple_demo.py
```

This script demonstrates:
- UniProt ID validation
- XML file parsing
- GO term extraction
- PDB cross-reference display
- Sequence analysis

### Command-Line Interface

Initialize the database:
```bash
pat db init
```

Ingest protein data:
```bash
# From a text file containing UniProt IDs
pat ingest-text proteins.txt

# From a directory of UniProt XML files
pat ingest-xml examples/data/uniprot_xml/
```

Query the database:
```bash
# Get details for a specific protein
pat query-protein P13773

# List all proteins in the database
pat list-proteins
```

## Code Examples

### Validate Biological Identifiers

```python
from protein_annotation_toolkit.validators import validate_uniprot_id

is_valid, error = validate_uniprot_id("P13773")
if is_valid:
    print("✓ Valid UniProt ID")
else:
    print(f"✗ Invalid: {error}")
```

### Parse UniProt XML

```python
from protein_annotation_toolkit.parsers import UniProtXMLParser

parser = UniProtXMLParser()
data = parser.parse_file("P13773.xml")

print(f"Protein: {data['recommended_name']}")
print(f"Organism: {data['organism']}")
print(f"Sequence Length: {data['sequence_length']} aa")
print(f"GO Terms: {len(data['go_terms'])}")
```

### Fetch from UniProt API

```python
from protein_annotation_toolkit.clients import UniProtClient

async with UniProtClient() as client:
    # Single protein
    xml_content = await client.fetch_xml("P13773")
    
    # Batch fetch (concurrent)
    results = await client.fetch_xml_batch(["P13773", "P29274", "Q02293"])
```

### Get KEGG Pathways

```python
from protein_annotation_toolkit.clients import KEGGClient

async with KEGGClient() as client:
    pathways = await client.get_pathways_for_protein("P13773")
    for pathway in pathways:
        print(f"{pathway['pathway_id']}: {pathway['name']}")
```

## Architecture

```
src/protein_annotation_toolkit/
├── cli.py                    # Click-based command-line interface
├── config.py                 # Pydantic settings management
├── validators.py             # Biological identifier validation
├── exceptions.py             # Custom exception hierarchy
├── db/
│   ├── models.py            # SQLAlchemy 2.0 ORM models
│   └── session.py           # Async session management
├── clients/
│   ├── base.py              # Base async HTTP client with retry logic
│   ├── uniprot.py           # UniProt REST API client
│   ├── kegg.py              # KEGG REST API client
│   └── blast.py             # NCBI BLAST API client
├── parsers/
│   ├── uniprot_xml.py       # UniProt XML parser (lxml)
│   ├── blast_xml.py         # BLAST XML parser
│   └── text.py              # Text file parsers
└── services/
    └── ingest.py            # Orchestration service for data ingestion
```

## Database Schema

Normalized relational schema designed for PostgreSQL, with SQLite compatibility:

**Core Entities:**
- **`organisms`** - Taxonomic information with NCBI taxonomy IDs
- **`proteins`** - UniProt protein records with sequences
- **`go_terms`** - Gene Ontology functional annotations
- **`pdb_crossrefs`** - 3D structure references with method and resolution
- **`kegg_pathways`** - Metabolic and signaling pathway definitions
- **`blast_searches`** - BLAST search metadata and parameters
- **`blast_hits`** - Individual sequence alignment results

**Relationships:**
- **`protein_go_terms`** - Many-to-many: proteins ↔ GO terms
- **`protein_kegg_pathways`** - Many-to-many: proteins ↔ pathways
- **`ingestion_logs`** - Audit trail for data provenance

**Features:**
- Foreign key constraints with cascading deletes
- Indexed columns for query performance
- Timestamps for created/updated tracking
- Text search optimization for protein names

## Skills Demonstrated

This toolkit showcases professional software engineering and computational biology expertise:

### Bioinformatics & Computational Biology
- **Domain Knowledge**: UniProt, Gene Ontology, KEGG pathways, PDB structures, BLAST sequence alignment
- **Data Formats**: UniProt XML, BLAST XML, FASTA sequences, biological identifiers
- **Data Integration**: Combining heterogeneous biological databases into unified view

### Software Engineering
- **Async Python**: `asyncio`, `aiohttp`, concurrent API requests with proper resource management
- **Database Design**: Normalized SQLAlchemy 2.0 ORM models with relationship mapping
- **API Integration**: REST clients with tenacity retry logic, rate limiting, and exponential backoff
- **XML Processing**: Efficient `lxml` parsing with XPath queries and namespace handling
- **Error Handling**: Custom exception hierarchy with detailed validation messages
- **Configuration**: Pydantic v2 settings with environment variable management

### Software Quality
- **Type Safety**: Comprehensive type hints throughout codebase
- **Documentation**: Docstrings, inline comments, and tutorial notebook
- **Logging**: Structured logging with `structlog` for observability
- **Package Management**: Modern `pyproject.toml` with proper dependencies

### Developer Experience
- **CLI Design**: Click framework with Rich formatting for beautiful terminal output
- **Interactive Tutorial**: Jupyter notebook with real API calls and data visualization
- **Real Data**: Working examples with actual UniProt, KEGG, and BLAST data

## What's Included

```
protein_annotation_toolkit/
├── src/protein_annotation_toolkit/   # Main package
│   ├── cli.py                        # Command-line interface
│   ├── config.py                     # Settings management
│   ├── validators.py                 # ID validation logic
│   ├── db/                           # Database models and sessions
│   ├── clients/                      # Async API clients
│   ├── parsers/                      # XML and text parsers
│   └── services/                     # Business logic layer
├── examples/
│   ├── Tutorial.ipynb                # Comprehensive Jupyter tutorial
│   ├── simple_demo.py                # Quick demonstration script
│   ├── data/
│   │   ├── uniprot_xml/              # Sample UniProt XML files
│   │   └── blast/                    # Sample BLAST XML output
│   └── fetch_uniprot_samples.py      # Script to download sample data
├── pyproject.toml                     # Package configuration
├── requirements.txt                   # Dependencies
└── README.md                          # This file
```

## About This Project

This is a **portfolio project** demonstrating computational biology and software engineering skills. It was extracted and refined from graduate-level bioinformatics coursework into a professional, production-ready toolkit.

**Use Cases:**
- Protein annotation and functional characterization
- Integration of heterogeneous biological databases
- Batch processing of UniProt protein records
- Educational tool for learning bioinformatics APIs

**Future Enhancements:**
- Comprehensive test suite with pytest
- GitHub Actions CI/CD pipeline
- Additional export formats (CSV, JSON)
- Web API with FastAPI
- Docker containerization

## License

MIT License - See LICENSE file for details.

## Questions or Feedback?

Open an issue or reach out with suggestions. This project is actively maintained as part of a professional portfolio.
