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
from protein_annotation_toolkit.services.query import QueryService
from protein_annotation_toolkit.services.refresh import RefreshService
from protein_annotation_toolkit.utils import (
    analyze_sequence,
    calculate_similarity,
    format_sequence_analysis,
)
from protein_annotation_toolkit.visualization import (
    plot_go_enrichment,
    plot_organism_distribution,
    plot_sequence_lengths,
)

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


@cli.group()
def stats():
    """Database statistics commands."""
    pass


@stats.command("summary")
def stats_summary():
    """
    Display database statistics summary.

    Shows counts of proteins, organisms, GO terms, and PDB structures.
    """
    async def run_stats():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.get_statistics()

    try:
        stats = asyncio.run(run_stats())

        console.print("\n[bold]Database Statistics[/bold]")
        console.print(f"  Proteins: {stats['protein_count']}")
        console.print(f"  Organisms: {stats['organism_count']}")
        console.print(f"  GO Terms: {stats['go_term_count']}")
        console.print(f"  PDB Structures: {stats['pdb_structure_count']}")
        if stats['last_updated']:
            console.print(f"  Last Updated: {stats['last_updated']}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Failed to get statistics: {e}")
        raise click.Abort()


@stats.command("by-organism")
@click.option("--top", type=int, default=10, help="Number of top organisms to show")
def stats_by_organism(top: int):
    """
    Show protein counts by organism.

    Example:
        pat stats by-organism --top 20
    """
    async def run_stats():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.get_organism_statistics(limit=top)

    try:
        results = asyncio.run(run_stats())

        if not results:
            console.print("[yellow]No organisms found[/yellow]")
            return

        # Create table
        table = Table(title=f"Top {len(results)} Organisms by Protein Count")
        table.add_column("Organism", style="cyan")
        table.add_column("Protein Count", style="green", justify="right")

        for row in results:
            table.add_row(row["organism"], str(row["count"]))

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Failed to get statistics: {e}")
        raise click.Abort()


@stats.command("go-terms")
@click.option("--most-common", type=int, default=20, help="Number of GO terms to show")
def stats_go_terms(most_common: int):
    """
    Show most common GO terms.

    Example:
        pat stats go-terms --most-common 30
    """
    async def run_stats():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.get_go_term_statistics(limit=most_common)

    try:
        results = asyncio.run(run_stats())

        if not results:
            console.print("[yellow]No GO terms found[/yellow]")
            return

        # Create table
        table = Table(title=f"Top {len(results)} GO Terms")
        table.add_column("GO ID", style="cyan")
        table.add_column("Term Name", style="white")
        table.add_column("Proteins", style="green", justify="right")

        for row in results:
            table.add_row(row["go_id"], row["term"], str(row["protein_count"]))

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Failed to get statistics: {e}")
        raise click.Abort()


@cli.group()
def export():
    """Export data commands."""
    pass


@export.command("proteins")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option(
    "--format",
    type=click.Choice(["csv", "json", "tsv"]),
    default="csv",
    help="Output format"
)
def export_proteins(output_file: Path, format: str):
    """
    Export all proteins to file.

    Example:
        pat export proteins output.csv --format csv
        pat export proteins data.json --format json
    """
    async def run_export():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.export_proteins(output_file, format=format)

    try:
        count = asyncio.run(run_export())
        console.print(f"[green]✓[/green] Exported {count} proteins to {output_file}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Export failed: {e}")
        raise click.Abort()


@export.command("by-organism")
@click.argument("organism_name")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option(
    "--format",
    type=click.Choice(["csv", "json", "tsv"]),
    default="json",
    help="Output format"
)
def export_by_organism(organism_name: str, output_file: Path, format: str):
    """
    Export proteins from specific organism.

    Example:
        pat export by-organism "Homo sapiens" human.json
    """
    async def run_export():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.export_proteins(
                output_file,
                format=format,
                organism=organism_name
            )

    try:
        count = asyncio.run(run_export())
        console.print(f"[green]✓[/green] Exported {count} proteins to {output_file}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Export failed: {e}")
        raise click.Abort()


@export.command("by-go-term")
@click.argument("go_id")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option(
    "--format",
    type=click.Choice(["csv", "json", "tsv"]),
    default="tsv",
    help="Output format"
)
def export_by_go_term(go_id: str, output_file: Path, format: str):
    """
    Export proteins with specific GO term.

    Example:
        pat export by-go-term GO:0004930 proteins.tsv
    """
    async def run_export():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.export_proteins(
                output_file,
                format=format,
                go_term=go_id
            )

    try:
        count = asyncio.run(run_export())
        console.print(f"[green]✓[/green] Exported {count} proteins to {output_file}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Export failed: {e}")
        raise click.Abort()


@cli.group()
def query():
    """Advanced query commands."""
    pass


@query.command("by-organism")
@click.argument("organism_name")
@click.option("--limit", type=int, default=100, help="Maximum results")
def query_by_organism(organism_name: str, limit: int):
    """
    Query proteins by organism.

    Example:
        pat query by-organism "Homo sapiens" --limit 50
    """
    from protein_annotation_toolkit.db.models import Protein

    async def run_query():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.query_by_organism(organism_name, limit=limit)

    try:
        proteins = asyncio.run(run_query())

        if not proteins:
            console.print(f"[yellow]No proteins found for {organism_name}[/yellow]")
            return

        # Create table
        table = Table(title=f"Proteins from {organism_name} (showing {len(proteins)})")
        table.add_column("Accession", style="cyan")
        table.add_column("Entry Name", style="green")
        table.add_column("Protein Name", style="white")
        table.add_column("Length", style="yellow", justify="right")

        for p in proteins:
            table.add_row(
                p.uniprot_accession,
                p.entry_name or "-",
                p.recommended_name or "-",
                str(p.sequence_length) if p.sequence_length else "-"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Query failed: {e}")
        raise click.Abort()


@query.command("by-go")
@click.argument("go_id")
@click.option("--include-proteins", is_flag=True, help="Include protein details")
def query_by_go(go_id: str, include_proteins: bool):
    """
    Query proteins by GO term.

    Example:
        pat query by-go GO:0004930 --include-proteins
    """
    async def run_query():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.query_by_go_term(go_id, include_proteins=include_proteins)

    try:
        result = asyncio.run(run_query())

        if not result["found"]:
            console.print(f"[yellow]GO term {go_id} not found[/yellow]")
            return

        console.print(f"\n[bold]GO Term: {result['go_id']}[/bold]")
        console.print(f"Name: {result['term_name']}")
        console.print(f"Protein Count: {result['protein_count']}")

        if include_proteins and result["proteins"]:
            console.print("\n[bold]Associated Proteins:[/bold]")

            # Create table
            table = Table()
            table.add_column("Accession", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Organism", style="yellow")

            for p in result["proteins"][:50]:  # Limit display
                table.add_row(
                    p.uniprot_accession,
                    p.recommended_name or "-",
                    p.organism.scientific_name if p.organism else "-"
                )

            console.print(table)

            if result['protein_count'] > 50:
                console.print(f"\n... and {result['protein_count'] - 50} more proteins")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Query failed: {e}")
        raise click.Abort()


@query.command("with-structures")
@click.option("--min-resolution", type=float, help="Minimum resolution (Angstroms)")
@click.option("--limit", type=int, default=50, help="Maximum results")
def query_with_structures(min_resolution: float, limit: int):
    """
    Query proteins with PDB structures.

    Example:
        pat query with-structures --min-resolution 2.0 --limit 100
    """
    async def run_query():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.query_with_structures(
                min_resolution=min_resolution,
                limit=limit
            )

    try:
        proteins = asyncio.run(run_query())

        if not proteins:
            console.print("[yellow]No proteins with structures found[/yellow]")
            return

        # Create table
        title = "Proteins with PDB Structures"
        if min_resolution:
            title += f" (resolution ≤ {min_resolution} Å)"

        table = Table(title=f"{title} (showing {len(proteins)})")
        table.add_column("Accession", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Organism", style="yellow")

        for p in proteins:
            table.add_row(
                p.uniprot_accession,
                p.recommended_name or "-",
                p.organism.scientific_name if p.organism else "-"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Query failed: {e}")
        raise click.Abort()


@cli.command("search")
@click.argument("search_term")
@click.option(
    "--field",
    type=click.Choice(["name", "accession", "entry"]),
    default="name",
    help="Field to search"
)
@click.option("--limit", type=int, default=50, help="Maximum results")
def search_proteins(search_term: str, field: str, limit: int):
    """
    Search proteins by text.

    Example:
        pat search "kinase" --field name --limit 20
        pat search "P13" --field accession
    """
    async def run_search():
        async with get_async_db_session() as session:
            service = QueryService(session)
            return await service.search_proteins(search_term, field=field, limit=limit)

    try:
        proteins = asyncio.run(run_search())

        if not proteins:
            console.print(f"[yellow]No proteins found matching '{search_term}'[/yellow]")
            return

        # Create table
        table = Table(title=f"Search Results for '{search_term}' (showing {len(proteins)})")
        table.add_column("Accession", style="cyan")
        table.add_column("Entry Name", style="green")
        table.add_column("Protein Name", style="white")
        table.add_column("Organism", style="yellow")

        for p in proteins:
            table.add_row(
                p.uniprot_accession,
                p.entry_name or "-",
                p.recommended_name or "-",
                p.organism.scientific_name if p.organism else "-"
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Search failed: {e}")
        raise click.Abort()


@cli.group()
def analyze():
    """Sequence analysis commands."""
    pass


@analyze.command("sequence")
@click.argument("uniprot_id")
def analyze_sequence_cmd(uniprot_id: str):
    """
    Analyze protein sequence.

    Calculates molecular weight, isoelectric point, composition.

    Example:
        pat analyze sequence P13773
    """
    from sqlalchemy import select
    from protein_annotation_toolkit.db.models import Protein

    async def run_analysis():
        async with get_async_db_session() as session:
            result = await session.execute(
                select(Protein).where(Protein.uniprot_accession == uniprot_id)
            )
            return result.scalar_one_or_none()

    try:
        protein = asyncio.run(run_analysis())

        if not protein or not protein.sequence:
            console.print(f"[yellow]Protein {uniprot_id} not found or has no sequence[/yellow]")
            return

        # Analyze sequence
        analysis = analyze_sequence(protein.sequence)

        console.print(f"\n[bold]Sequence Analysis: {uniprot_id}[/bold]")
        console.print(f"Name: {protein.recommended_name or 'N/A'}")
        console.print()
        console.print(format_sequence_analysis(analysis))

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Analysis failed: {e}")
        raise click.Abort()


@analyze.command("compare")
@click.argument("uniprot_id1")
@click.argument("uniprot_id2")
def compare_sequences(uniprot_id1: str, uniprot_id2: str):
    """
    Compare two protein sequences.

    Calculates percent identity.

    Example:
        pat analyze compare P13773 Q02293
    """
    from sqlalchemy import select
    from protein_annotation_toolkit.db.models import Protein

    async def run_comparison():
        async with get_async_db_session() as session:
            result = await session.execute(
                select(Protein).where(
                    Protein.uniprot_accession.in_([uniprot_id1, uniprot_id2])
                )
            )
            proteins = {p.uniprot_accession: p for p in result.scalars().all()}

            if uniprot_id1 not in proteins or uniprot_id2 not in proteins:
                return None

            return proteins

    try:
        proteins = asyncio.run(run_comparison())

        if not proteins:
            console.print("[yellow]One or both proteins not found[/yellow]")
            return

        p1 = proteins[uniprot_id1]
        p2 = proteins[uniprot_id2]

        if not p1.sequence or not p2.sequence:
            console.print("[yellow]One or both proteins have no sequence[/yellow]")
            return

        # Calculate similarity
        similarity = calculate_similarity(p1.sequence, p2.sequence)

        console.print(f"\n[bold]Sequence Comparison[/bold]")
        console.print(f"\nProtein 1: {uniprot_id1}")
        console.print(f"  Name: {p1.recommended_name or 'N/A'}")
        console.print(f"  Length: {len(p1.sequence)} aa")

        console.print(f"\nProtein 2: {uniprot_id2}")
        console.print(f"  Name: {p2.recommended_name or 'N/A'}")
        console.print(f"  Length: {len(p2.sequence)} aa")

        console.print(f"\n[bold]Similarity: {similarity:.2f}%[/bold]")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Comparison failed: {e}")
        raise click.Abort()


@cli.group()
def refresh():
    """Refresh/update protein data."""
    pass


@refresh.command("stale")
@click.option(
    "--older-than",
    type=int,
    default=30,
    help="Refresh proteins older than N days"
)
@click.option("--batch-size", type=int, default=50, help="Batch size for API requests")
def refresh_stale(older_than: int, batch_size: int):
    """
    Refresh proteins not updated recently.

    Example:
        pat refresh stale --older-than 60 --batch-size 25
    """
    async def run_refresh():
        async with get_async_db_session() as session:
            service = RefreshService(session)
            return await service.refresh_stale_proteins(
                days_old=older_than,
                batch_size=batch_size
            )

    try:
        console.print(f"[bold blue]Refreshing proteins older than {older_than} days...[/bold blue]")
        stats = asyncio.run(run_refresh())

        console.print("\n[bold]Refresh Results:[/bold]")
        console.print(f"  Total: {stats['total']}")
        console.print(f"  [green]✓ Succeeded: {stats['succeeded']}[/green]")
        console.print(f"  [red]✗ Failed: {stats['failed']}[/red]")

        if stats['errors']:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in stats['errors'][:10]:
                console.print(f"  • {error}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Refresh failed: {e}")
        raise click.Abort()


@refresh.command("protein")
@click.argument("uniprot_id")
@click.option("--force", is_flag=True, help="Force refresh even if recently updated")
def refresh_protein(uniprot_id: str, force: bool):
    """
    Refresh specific protein.

    Example:
        pat refresh protein P13773 --force
    """
    async def run_refresh():
        async with get_async_db_session() as session:
            service = RefreshService(session)
            return await service.refresh_proteins([uniprot_id], force=force)

    try:
        console.print(f"[bold blue]Refreshing {uniprot_id}...[/bold blue]")
        stats = asyncio.run(run_refresh())

        if stats['succeeded']:
            console.print(f"[green]✓[/green] Successfully refreshed {uniprot_id}")
        elif stats['skipped']:
            console.print(f"[yellow]Skipped (recently updated)[/yellow]")
        else:
            console.print(f"[red]✗[/red] Failed to refresh {uniprot_id}")
            if stats['errors']:
                console.print(f"  Error: {stats['errors'][0]}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Refresh failed: {e}")
        raise click.Abort()


@cli.group()
def visualize():
    """Data visualization commands."""
    pass


@visualize.command("organism-distribution")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option("--top", type=int, default=15, help="Number of top organisms to show")
def viz_organism_distribution(output_file: Path, top: int):
    """
    Plot organism distribution.

    Creates horizontal bar chart of protein counts by organism.

    Example:
        pat visualize organism-distribution chart.png --top 20
    """
    async def run_plot():
        async with get_async_db_session() as session:
            await plot_organism_distribution(
                session,
                output_file,
                top_n=top
            )

    try:
        console.print("[bold blue]Generating organism distribution plot...[/bold blue]")
        asyncio.run(run_plot())
        console.print(f"[green]✓[/green] Plot saved to {output_file}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Visualization failed: {e}")
        raise click.Abort()


@visualize.command("sequence-lengths")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option("--organism", type=str, help="Filter by organism")
@click.option("--bins", type=int, default=50, help="Number of histogram bins")
def viz_sequence_lengths(output_file: Path, organism: str, bins: int):
    """
    Plot sequence length distribution.

    Creates histogram of protein sequence lengths.

    Example:
        pat visualize sequence-lengths lengths.png
        pat visualize sequence-lengths human.png --organism "Homo sapiens"
    """
    async def run_plot():
        async with get_async_db_session() as session:
            await plot_sequence_lengths(
                session,
                output_file,
                organism=organism,
                bins=bins
            )

    try:
        console.print("[bold blue]Generating sequence length distribution...[/bold blue]")
        asyncio.run(run_plot())
        console.print(f"[green]✓[/green] Plot saved to {output_file}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Visualization failed: {e}")
        raise click.Abort()


@visualize.command("go-enrichment")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option("--query", type=str, help="Filter proteins by name")
@click.option("--top", type=int, default=20, help="Number of GO terms to show")
def viz_go_enrichment(output_file: Path, query: str, top: int):
    """
    Plot GO term enrichment.

    Shows most common GO terms, optionally filtered by protein name.

    Example:
        pat visualize go-enrichment enrichment.pdf
        pat visualize go-enrichment kinase_go.png --query "kinase" --top 30
    """
    async def run_plot():
        async with get_async_db_session() as session:
            await plot_go_enrichment(
                session,
                output_file,
                search_term=query,
                top_n=top
            )

    try:
        console.print("[bold blue]Generating GO enrichment plot...[/bold blue]")
        asyncio.run(run_plot())
        console.print(f"[green]✓[/green] Plot saved to {output_file}")

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Visualization failed: {e}")
        raise click.Abort()


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
