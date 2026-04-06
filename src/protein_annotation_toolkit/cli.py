"""
Command-line interface for Protein Annotation Toolkit.

Provides commands for database management, data ingestion, querying, and export.
"""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

# Import core components
from protein_annotation_toolkit.core.logging import configure_logging
from protein_annotation_toolkit.db import get_async_db_session, init_db
from protein_annotation_toolkit.services.ingest import IngestService

# Initialize Rich console
console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Protein Annotation Toolkit - A bioinformatics tool for protein data management.

    Supports UniProt, KEGG, BLAST, and PDB data sources.
    """
    # Configure logging when CLI starts
    configure_logging()


@cli.group()
def db():
    """Database management commands."""
    pass


@db.command("init")
def db_init():
    """
    Initialize database schema.

    Creates all tables defined in the models.
    """
    console.print("[bold blue]Initializing database...[/bold blue]")

    try:
        # Run async init_db
        asyncio.run(init_db())
        console.print("[bold green]✓[/bold green] Database initialized successfully")
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Failed to initialize database: {e}")
        raise click.Abort()


@cli.command("ingest-text")
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--source",
    type=click.Choice(["api", "local"]),
    default="api",
    help="Data source: 'api' to fetch from UniProt, 'local' for local XML files"
)
@click.option(
    "--batch-size",
    type=int,
    default=50,
    help="Number of concurrent API requests"
)
def ingest_text(input_file: Path, source: str, batch_size: int):
    """
    Ingest proteins from text file containing UniProt IDs.

    INPUT_FILE should contain one UniProt ID per line, optionally prefixed with "UniProt:".

    Example:
        pat ingest-text proteins.txt --source api --batch-size 50
    """
    console.print(f"[bold blue]Ingesting from {input_file}...[/bold blue]")
    console.print(f"Source: {source}, Batch size: {batch_size}")

    async def run_ingest():
        async with get_async_db_session() as session:
            service = IngestService(session)
            stats = await service.ingest_from_text_file(
                file_path=input_file,
                fetch_from_api=(source == "api"),
                batch_size=batch_size
            )
            return stats

    try:
        stats = asyncio.run(run_ingest())

        # Display results
        console.print("\n[bold]Ingestion Results:[/bold]")
        console.print(f"  Total: {stats['total']}")
        console.print(f"  [green]✓ Succeeded: {stats['succeeded']}[/green]")
        console.print(f"  [red]✗ Failed: {stats['failed']}[/red]")

        if stats['errors']:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in stats['errors'][:10]:  # Show first 10 errors
                console.print(f"  • {error}")
            if len(stats['errors']) > 10:
                console.print(f"  ... and {len(stats['errors']) - 10} more")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Ingestion failed: {e}")
        raise click.Abort()


@cli.command("ingest-xml")
@click.argument("xml_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--recursive",
    is_flag=True,
    help="Process directory recursively"
)
def ingest_xml(xml_path: Path, recursive: bool):
    """
    Ingest proteins from local UniProt XML files.

    XML_PATH can be a single file or directory.

    Example:
        pat ingest-xml data/xml/ --recursive
    """
    console.print(f"[bold blue]Ingesting from {xml_path}...[/bold blue]")

    async def run_ingest():
        async with get_async_db_session() as session:
            service = IngestService(session)

            if xml_path.is_dir():
                stats = await service.ingest_from_xml_directory(xml_path)
            else:
                # Single file - wrap in list
                stats = await service.ingest_from_xml_directory(
                    xml_path.parent,
                    [xml_path.stem]
                )
            return stats

    try:
        stats = asyncio.run(run_ingest())

        console.print("\n[bold]Ingestion Results:[/bold]")
        console.print(f"  Total: {stats['total']}")
        console.print(f"  [green]✓ Succeeded: {stats['succeeded']}[/green]")
        console.print(f"  [red]✗ Failed: {stats['failed']}[/red]")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Ingestion failed: {e}")
        raise click.Abort()


@cli.command("query-protein")
@click.argument("uniprot_id")
def query_protein(uniprot_id: str):
    """
    Query protein by UniProt ID.

    Example:
        pat query-protein P13773
    """
    from sqlalchemy import select
    from protein_annotation_toolkit.db.models import Protein, Organism

    async def run_query():
        async with get_async_db_session() as session:
            # Fetch protein with organism
            result = await session.execute(
                select(Protein, Organism)
                .join(Organism, Protein.organism_id == Organism.id, isouter=True)
                .where(Protein.uniprot_accession == uniprot_id)
            )
            data = result.first()
            return data

    try:
        data = asyncio.run(run_query())

        if not data:
            console.print(f"[red]Protein {uniprot_id} not found in database[/red]")
            return

        protein, organism = data

        # Display protein information
        console.print(f"\n[bold]Protein: {uniprot_id}[/bold]")
        console.print(f"Entry Name: {protein.entry_name or 'N/A'}")
        console.print(f"Name: {protein.recommended_name or 'N/A'}")
        console.print(f"Organism: {organism.scientific_name if organism else 'N/A'}")
        console.print(f"Sequence Length: {protein.sequence_length or 'N/A'} aa")

        if protein.last_fetched_at:
            console.print(f"Last Fetched: {protein.last_fetched_at.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Query failed: {e}")
        raise click.Abort()


@cli.command("list-proteins")
@click.option("--limit", type=int, default=20, help="Number of proteins to display")
def list_proteins(limit: int):
    """
    List proteins in database.

    Example:
        pat list-proteins --limit 10
    """
    from sqlalchemy import select
    from protein_annotation_toolkit.db.models import Protein, Organism

    async def run_query():
        async with get_async_db_session() as session:
            result = await session.execute(
                select(Protein, Organism)
                .join(Organism, Protein.organism_id == Organism.id, isouter=True)
                .limit(limit)
            )
            return result.all()

    try:
        proteins = asyncio.run(run_query())

        if not proteins:
            console.print("[yellow]No proteins found in database[/yellow]")
            return

        # Create table
        table = Table(title=f"Proteins (showing {len(proteins)})")
        table.add_column("Accession", style="cyan")
        table.add_column("Entry Name", style="green")
        table.add_column("Protein Name", style="white")
        table.add_column("Organism", style="yellow")

        for protein, organism in proteins:
            table.add_row(
                protein.uniprot_accession,
                protein.entry_name or "-",
                protein.recommended_name or "-",
                organism.scientific_name if organism else "-"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Query failed: {e}")
        raise click.Abort()


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
