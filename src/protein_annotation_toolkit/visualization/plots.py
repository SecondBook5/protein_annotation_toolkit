"""
Visualization utilities for protein data.

Provides plotting functions for data analysis and exploration.
"""

from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import matplotlib
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from protein_annotation_toolkit.db.models import (
    GOTerm,
    Organism,
    Protein,
    ProteinGOTerm,
)

# Use non-interactive backend for server environments
matplotlib.use('Agg')


async def plot_organism_distribution(
    session: AsyncSession,
    output_path: Path,
    top_n: int = 15,
    figsize: tuple = (12, 6)
) -> None:
    """
    Plot distribution of proteins across organisms.

    Args:
        session: Database session
        output_path: Output file path (PNG, PDF, etc.)
        top_n: Number of top organisms to show
        figsize: Figure size (width, height)
    """
    # Query organism counts
    result = await session.execute(
        select(
            Organism.scientific_name,
            func.count(Protein.id).label("count")
        )
        .join(Protein, Protein.organism_id == Organism.id)
        .group_by(Organism.scientific_name)
        .order_by(func.count(Protein.id).desc())
        .limit(top_n)
    )
    data = result.all()

    if not data:
        raise ValueError("No data to plot")

    # Extract data for plotting
    organisms = [row[0] for row in data]
    counts = [row[1] for row in data]

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Create bar plot
    bars = ax.barh(organisms, counts, color='steelblue', edgecolor='black', linewidth=0.5)

    # Customize plot
    ax.set_xlabel('Number of Proteins', fontsize=12, weight='bold')
    ax.set_ylabel('Organism', fontsize=12, weight='bold')
    ax.set_title(f'Top {top_n} Organisms by Protein Count', fontsize=14, weight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    # Add value labels on bars
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width,
            bar.get_y() + bar.get_height() / 2,
            f' {int(width)}',
            ha='left',
            va='center',
            fontsize=10
        )

    # Invert y-axis so highest is at top
    ax.invert_yaxis()

    # Tight layout
    plt.tight_layout()

    # Save figure
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


async def plot_sequence_lengths(
    session: AsyncSession,
    output_path: Path,
    organism: Optional[str] = None,
    bins: int = 50,
    figsize: tuple = (10, 6)
) -> None:
    """
    Plot distribution of sequence lengths.

    Args:
        session: Database session
        output_path: Output file path
        organism: Filter by organism (optional)
        bins: Number of histogram bins
        figsize: Figure size
    """
    # Query sequence lengths
    query = select(Protein.sequence_length).where(Protein.sequence_length.isnot(None))

    if organism:
        query = query.join(Organism, Protein.organism_id == Organism.id).where(
            Organism.scientific_name == organism
        )

    result = await session.execute(query)
    lengths = [row[0] for row in result.all()]

    if not lengths:
        raise ValueError("No sequence data to plot")

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Create histogram
    n, bins_edges, patches = ax.hist(
        lengths,
        bins=bins,
        color='steelblue',
        edgecolor='black',
        alpha=0.7,
        linewidth=0.5
    )

    # Customize plot
    title = 'Distribution of Protein Sequence Lengths'
    if organism:
        title += f' ({organism})'

    ax.set_xlabel('Sequence Length (amino acids)', fontsize=12, weight='bold')
    ax.set_ylabel('Number of Proteins', fontsize=12, weight='bold')
    ax.set_title(title, fontsize=14, weight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add statistics text
    mean_length = sum(lengths) / len(lengths)
    median_length = sorted(lengths)[len(lengths) // 2]

    stats_text = f'Mean: {mean_length:.0f} aa\nMedian: {median_length:.0f} aa\nTotal: {len(lengths)} proteins'
    ax.text(
        0.97,
        0.97,
        stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray')
    )

    # Tight layout
    plt.tight_layout()

    # Save figure
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


async def plot_go_enrichment(
    session: AsyncSession,
    output_path: Path,
    search_term: Optional[str] = None,
    top_n: int = 20,
    figsize: tuple = (14, 8)
) -> None:
    """
    Plot GO term enrichment.

    Shows most common GO terms, optionally filtered by protein name.

    Args:
        session: Database session
        output_path: Output file path
        search_term: Filter proteins by name (optional)
        top_n: Number of top GO terms to show
        figsize: Figure size
    """
    # Build query for GO term counts
    if search_term:
        # Filter by protein name
        query = (
            select(
                GOTerm.term_name,
                func.count(ProteinGOTerm.protein_id).label("count")
            )
            .join(ProteinGOTerm, ProteinGOTerm.go_term_id == GOTerm.id)
            .join(Protein, ProteinGOTerm.protein_id == Protein.id)
            .where(Protein.recommended_name.ilike(f"%{search_term}%"))
            .group_by(GOTerm.term_name)
            .order_by(func.count(ProteinGOTerm.protein_id).desc())
            .limit(top_n)
        )
    else:
        # All GO terms
        query = (
            select(
                GOTerm.term_name,
                func.count(ProteinGOTerm.protein_id).label("count")
            )
            .join(ProteinGOTerm, ProteinGOTerm.go_term_id == GOTerm.id)
            .group_by(GOTerm.term_name)
            .order_by(func.count(ProteinGOTerm.protein_id).desc())
            .limit(top_n)
        )

    result = await session.execute(query)
    data = result.all()

    if not data:
        raise ValueError("No GO term data to plot")

    # Extract data
    go_terms = [row[0] for row in data]
    counts = [row[1] for row in data]

    # Shorten long GO term names for display
    def shorten_term(term: str, max_length: int = 60) -> str:
        """Shorten GO term name for display."""
        if len(term) <= max_length:
            return term
        return term[:max_length - 3] + "..."

    go_terms_short = [shorten_term(term) for term in go_terms]

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Create horizontal bar plot
    y_pos = range(len(go_terms_short))
    bars = ax.barh(y_pos, counts, color='forestgreen', edgecolor='black', linewidth=0.5)

    # Customize plot
    ax.set_yticks(y_pos)
    ax.set_yticklabels(go_terms_short, fontsize=9)
    ax.set_xlabel('Number of Proteins', fontsize=12, weight='bold')
    ax.set_ylabel('GO Term', fontsize=12, weight='bold')

    title = f'Top {top_n} GO Terms'
    if search_term:
        title += f' (filtered by "{search_term}")'

    ax.set_title(title, fontsize=14, weight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    # Add value labels
    for i, (bar, count) in enumerate(zip(bars, counts)):
        width = bar.get_width()
        ax.text(
            width,
            bar.get_y() + bar.get_height() / 2,
            f' {int(count)}',
            ha='left',
            va='center',
            fontsize=9
        )

    # Invert y-axis
    ax.invert_yaxis()

    # Tight layout
    plt.tight_layout()

    # Save figure
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
