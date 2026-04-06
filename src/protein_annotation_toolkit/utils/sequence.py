"""
Sequence analysis utilities.

Provides functions for analyzing protein sequences.
"""

from typing import Dict, Tuple

# Amino acid properties
AA_MOLECULAR_WEIGHTS = {
    'A': 89.09, 'R': 174.20, 'N': 132.12, 'D': 133.10, 'C': 121.15,
    'Q': 146.15, 'E': 147.13, 'G': 75.07, 'H': 155.16, 'I': 131.17,
    'L': 131.17, 'K': 146.19, 'M': 149.21, 'F': 165.19, 'P': 115.13,
    'S': 105.09, 'T': 119.12, 'W': 204.23, 'Y': 181.19, 'V': 117.15
}

# pKa values for charged amino acids
PKA_VALUES = {
    'C-term': 3.65,
    'N-term': 8.2,
    'D': 3.9,
    'E': 4.3,
    'H': 6.0,
    'C': 8.3,
    'Y': 10.1,
    'K': 10.5,
    'R': 12.5
}


def calculate_molecular_weight(sequence: str) -> float:
    """
    Calculate molecular weight of protein sequence.

    Args:
        sequence: Protein sequence (one-letter amino acid codes)

    Returns:
        Molecular weight in Daltons
    """
    if not sequence:
        return 0.0

    # Sum amino acid weights
    weight = sum(AA_MOLECULAR_WEIGHTS.get(aa, 0.0) for aa in sequence.upper())

    # Subtract water molecules for peptide bonds
    water_weight = 18.015 * (len(sequence) - 1)

    return weight - water_weight


def calculate_gc_content(sequence: str) -> float:
    """
    Calculate GC content (percentage of G and C residues).

    Note: GC content is typically for nucleotide sequences, but can be
    calculated for protein sequences as the percentage of glycine and cysteine.

    Args:
        sequence: Protein sequence

    Returns:
        GC content as percentage (0-100)
    """
    if not sequence:
        return 0.0

    sequence = sequence.upper()
    gc_count = sequence.count('G') + sequence.count('C')

    return (gc_count / len(sequence)) * 100


def calculate_isoelectric_point(sequence: str) -> float:
    """
    Calculate theoretical isoelectric point (pI) of protein.

    Uses iterative approach to find pH where net charge is zero.

    Args:
        sequence: Protein sequence

    Returns:
        Theoretical pI value
    """
    if not sequence:
        return 0.0

    sequence = sequence.upper()

    # Count charged residues
    counts = {
        'D': sequence.count('D'),
        'E': sequence.count('E'),
        'H': sequence.count('H'),
        'C': sequence.count('C'),
        'Y': sequence.count('Y'),
        'K': sequence.count('K'),
        'R': sequence.count('R'),
        'N-term': 1,
        'C-term': 1
    }

    def calculate_charge(ph: float) -> float:
        """Calculate net charge at given pH."""
        charge = 0.0

        # Positive charges (protonated)
        for residue in ['N-term', 'K', 'R', 'H']:
            pka = PKA_VALUES[residue]
            count = counts[residue]
            charge += count / (1 + 10 ** (ph - pka))

        # Negative charges (deprotonated)
        for residue in ['C-term', 'D', 'E', 'C', 'Y']:
            pka = PKA_VALUES[residue]
            count = counts[residue]
            charge -= count / (1 + 10 ** (pka - ph))

        return charge

    # Binary search for pI
    ph_min, ph_max = 0.0, 14.0
    tolerance = 0.01

    while ph_max - ph_min > tolerance:
        ph_mid = (ph_min + ph_max) / 2
        charge = calculate_charge(ph_mid)

        if charge > 0:
            ph_min = ph_mid
        else:
            ph_max = ph_mid

    return (ph_min + ph_max) / 2


def calculate_sequence_composition(sequence: str) -> Dict[str, any]:
    """
    Calculate amino acid composition.

    Args:
        sequence: Protein sequence

    Returns:
        Dictionary with counts and percentages for each amino acid
    """
    if not sequence:
        return {}

    sequence = sequence.upper()
    length = len(sequence)

    composition = {}
    for aa in set(sequence):
        count = sequence.count(aa)
        composition[aa] = {
            'count': count,
            'percentage': (count / length) * 100
        }

    return composition


def calculate_similarity(seq1: str, seq2: str) -> float:
    """
    Calculate simple sequence similarity (percent identity).

    Uses pairwise comparison without gaps.

    Args:
        seq1: First protein sequence
        seq2: Second protein sequence

    Returns:
        Similarity score (0-100)
    """
    if not seq1 or not seq2:
        return 0.0

    seq1 = seq1.upper()
    seq2 = seq2.upper()

    # Align to shorter sequence
    min_len = min(len(seq1), len(seq2))

    matches = sum(1 for i in range(min_len) if seq1[i] == seq2[i])

    return (matches / min_len) * 100


def analyze_sequence(sequence: str) -> Dict[str, any]:
    """
    Comprehensive sequence analysis.

    Args:
        sequence: Protein sequence

    Returns:
        Dictionary with all analysis results
    """
    return {
        'length': len(sequence),
        'molecular_weight': calculate_molecular_weight(sequence),
        'isoelectric_point': calculate_isoelectric_point(sequence),
        'gc_content': calculate_gc_content(sequence),
        'composition': calculate_sequence_composition(sequence)
    }


def format_sequence_analysis(analysis: Dict[str, any]) -> str:
    """
    Format sequence analysis results for display.

    Args:
        analysis: Analysis results from analyze_sequence()

    Returns:
        Formatted string
    """
    lines = [
        f"Length: {analysis['length']} aa",
        f"Molecular Weight: {analysis['molecular_weight']:.2f} Da",
        f"Isoelectric Point (pI): {analysis['isoelectric_point']:.2f}",
        f"GC Content: {analysis['gc_content']:.2f}%",
        "\nAmino Acid Composition:",
    ]

    # Sort by count (descending)
    composition = analysis['composition']
    sorted_aa = sorted(
        composition.items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )

    for aa, data in sorted_aa[:10]:  # Top 10
        lines.append(
            f"  {aa}: {data['count']} ({data['percentage']:.1f}%)"
        )

    return "\n".join(lines)
