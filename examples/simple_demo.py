#!/usr/bin/env python
"""
Simple demonstration of the Protein Annotation Toolkit.

This script demonstrates:
1. Parsing UniProt XML files
2. Validating biological identifiers
3. Working with the parsed data

For full database integration, see the Jupyter notebook tutorial.
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table

from protein_annotation_toolkit.parsers import UniProtXMLParser
from protein_annotation_toolkit.validators import validate_uniprot_id

# Initialize console for pretty output
console = Console()

def main():
    console.print("\n[bold blue]Protein Annotation Toolkit - Simple Demo[/bold blue]\n")

    # Step 1: Validate some UniProt IDs
    console.print("[bold]Step 1: Validate UniProt IDs[/bold]")
    test_ids = ["P13773", "INVALID", "P29274", "P1234"]  # Mix of valid and invalid

    for uid in test_ids:
        is_valid, error = validate_uniprot_id(uid)
        if is_valid:
            console.print(f"  [green]✓[/green] {uid} is valid")
        else:
            console.print(f"  [red]✗[/red] {uid} is invalid: {error}")

    # Step 2: Parse a UniProt XML file
    console.print("\n[bold]Step 2: Parse UniProt XML File[/bold]")
    xml_file = Path("examples/data/uniprot_xml/P13773.xml")

    if not xml_file.exists():
        console.print(f"[red]XML file not found: {xml_file}[/red]")
        return

    parser = UniProtXMLParser()
    data = parser.parse_file(xml_file)

    console.print(f"\n[cyan]Parsed protein: {data['accession']}[/cyan]")
    console.print(f"  Entry Name: {data['entry_name']}")
    console.print(f"  Protein: {data['recommended_name']}")
    console.print(f"  Organism: {data['organism']}")
    console.print(f"  Sequence Length: {data['sequence_length']} aa")

    # Step 3: Display GO terms
    console.print(f"\n[bold]Step 3: Gene Ontology Terms ({len(data['go_terms'])} total)[/bold]")

    if data['go_terms']:
        table = Table(title="GO Terms (first 10)")
        table.add_column("GO ID", style="cyan")
        table.add_column("Term", style="green")

        for go_term in data['go_terms'][:10]:
            table.add_row(go_term['go_id'], go_term['term'])

        console.print(table)

    # Step 4: Display PDB cross-references
    console.print(f"\n[bold]Step 4: PDB Cross-References ({len(data['pdb_crossrefs'])} total)[/bold]")

    if data['pdb_crossrefs']:
        pdb_table = Table(title="PDB Structures")
        pdb_table.add_column("PDB ID", style="cyan")
        pdb_table.add_column("Method", style="yellow")
        pdb_table.add_column("Resolution (Å)", style="green")

        for pdb in data['pdb_crossrefs']:
            resolution = f"{pdb['resolution']:.2f}" if pdb['resolution'] else "-"
            pdb_table.add_row(
                pdb['pdb_id'],
                pdb['method'] or "-",
                resolution
            )

        console.print(pdb_table)
    else:
        console.print("  [yellow]No PDB structures found[/yellow]")

    # Step 5: Show sequence snippet
    console.print(f"\n[bold]Step 5: Sequence Information[/bold]")
    sequence = data['sequence']
    if sequence:
        console.print(f"  First 60 amino acids: {sequence[:60]}...")
        console.print(f"  Total length: {len(sequence)} aa")

    console.print("\n[bold green]Demo complete![/bold green]")
    console.print("\n[dim]For database integration and more features, see the Jupyter notebook tutorial.[/dim]\n")

if __name__ == "__main__":
    main()
