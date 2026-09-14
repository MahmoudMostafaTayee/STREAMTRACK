#!/usr/bin/env python3
"""
Comparison script for verifying parity between Python and Java MCPT implementations.
Compares intermediate dumps from both pipelines.

Usage:
    python compare_mcpt_dumps.py --output-dir ./output/scene2
"""

import os
import sys
import re
import numpy as np
from pathlib import Path

# Force UTF-8 encoding for console output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Default output directory
OUTPUT_DIR = Path(r".\output\scene2")


def load_matrix(filepath):
    """Load a matrix from a text file."""
    try:
        # Handle both formats: "0.123, 0.456" and "0.123 0.456"
        with open(filepath, 'r') as f:
            content = f.read().strip()
        
        if not content:
            return np.array([])
        
        lines = content.split('\n')
        matrix = []
        for line in lines:
            if line.strip():
                # Handle comma-separated or space-separated
                if ',' in line:
                    row = [float(x.strip()) for x in line.split(',') if x.strip()]
                else:
                    row = [float(x.strip()) for x in line.split() if x.strip()]
                matrix.append(row)
        return np.array(matrix)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def load_clusters(filepath):
    """Load cluster assignments from a text file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
        # Parse [0, 1, 2, ...] format
        if content.startswith('[') and content.endswith(']'):
            content = content[1:-1]
        clusters = [int(x.strip()) for x in content.split(',') if x.strip()]
        return clusters
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def load_text_file(filepath):
    """Load a text file as lines for comparison."""
    try:
        with open(filepath, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def compare_matrices(java_path, python_path, tolerance=1e-4):
    """Compare two matrices with tolerance."""
    java_matrix = load_matrix(java_path)
    python_matrix = load_matrix(python_path)
    
    if java_matrix is None or python_matrix is None:
        return False, "Could not load one or both files"
    
    if java_matrix.shape != python_matrix.shape:
        return False, f"Shape mismatch: Java {java_matrix.shape} vs Python {python_matrix.shape}"
    
    if java_matrix.size == 0:
        return True, "Both matrices empty"
    
    diff = np.abs(java_matrix - python_matrix)
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    
    if max_diff <= tolerance:
        return True, f"Match (max_diff={max_diff:.6f}, mean_diff={mean_diff:.6f})"
    else:
        # Find location of max difference
        max_idx = np.unravel_index(np.argmax(diff), diff.shape)
        return False, f"Mismatch: max_diff={max_diff:.6f} at {max_idx}, Java={java_matrix[max_idx]:.6f}, Python={python_matrix[max_idx]:.6f}"


def compare_clusters(java_path, python_path):
    """Compare cluster assignments."""
    java_clusters = load_clusters(java_path)
    python_clusters = load_clusters(python_path)
    
    if java_clusters is None or python_clusters is None:
        return False, "Could not load one or both files"
    
    if len(java_clusters) != len(python_clusters):
        return False, f"Length mismatch: Java {len(java_clusters)} vs Python {len(python_clusters)}"
    
    if java_clusters == python_clusters:
        return True, f"Exact match ({len(java_clusters)} clusters)"
    
    # Check if they're equivalent (same groupings, different IDs)
    java_groups = {}
    python_groups = {}
    
    for i, (j, p) in enumerate(zip(java_clusters, python_clusters)):
        if j not in java_groups:
            java_groups[j] = []
        java_groups[j].append(i)
        
        if p not in python_groups:
            python_groups[p] = []
        python_groups[p].append(i)
    
    java_sets = set(frozenset(v) for v in java_groups.values())
    python_sets = set(frozenset(v) for v in python_groups.values())
    
    if java_sets == python_sets:
        return True, f"Equivalent groupings (different IDs, {len(java_sets)} unique clusters)"
    
    # Find differences
    only_java = java_sets - python_sets
    only_python = python_sets - java_sets
    
    return False, f"Grouping mismatch: {len(only_java)} Java-only, {len(only_python)} Python-only clusters"


def compare_text_files(java_path, python_path):
    """Compare text files line by line."""
    java_text = load_text_file(java_path)
    python_text = load_text_file(python_path)
    
    if java_text is None or python_text is None:
        return False, "Could not load one or both files"
    
    if java_text == python_text:
        return True, "Exact match"
    
    # Normalize and compare
    java_lines = sorted(java_text.split('\n'))
    python_lines = sorted(python_text.split('\n'))
    
    if len(java_lines) != len(python_lines):
        return False, f"Line count mismatch: Java {len(java_lines)} vs Python {len(python_lines)}"
    
    diff_count = sum(1 for j, p in zip(java_lines, python_lines) if j.strip() != p.strip())
    if diff_count == 0:
        return True, "Match (order-independent)"
    
    return False, f"{diff_count} lines differ"


def guess_file_type(name, filepath):
    """Guess the type of file based on name and content."""
    name_lower = name.lower()
    if any(x in name_lower for x in ['matrix', 'raw', 'zeroed', 'replaced', 'similarity']):
        return 'matrix'
    if any(x in name_lower for x in ['cluster']):
        return 'clusters'
    if any(x in name_lower for x in ['camera-dict', 'global-ids', 'global_id']):
        return 'text'
    return 'text'


def main(output_dir=None):
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)

    dumps_dir = output_dir / "mcpt-dumps"

    print("=" * 70)
    print("MCPT Implementation Parity Comparison")
    print("=" * 70)
    print(f"Dumps directory: {dumps_dir}")

    if not dumps_dir.exists():
        print(f"\n[ERROR] MCPT dumps directory not found: {dumps_dir}")
        print("Please run Java and Python with --debug first.")
        return 1

    # Discover files
    java_files = {}
    python_files = {}

    for f in dumps_dir.iterdir():
        if not f.is_file() or f.suffix == '.json':
            continue
        name = f.stem
        if "-python" in name or "_python" in name:
            python_files[name] = f
        else:
            java_files[name] = f

    def normalize(name, is_java):
        """Normalize filename for cross-language matching."""
        n = name.lower()
        if is_java:
            n = re.sub(r'_(batch_)?\d+$', '', n)
            n = re.sub(r'-java$', '', n)
        else:
            n = n.replace('-python', '').replace('_python', '')
            n = re.sub(r'_(batch_)?\d+$', '', n)
        return n.strip('_-')

    matched_pairs = []
    used_python = set()
    for java_name, java_path in sorted(java_files.items()):
        java_key = normalize(java_name, True)
        best_match = None
        for python_name, python_path in sorted(python_files.items()):
            if python_name in used_python:
                continue
            python_key = normalize(python_name, False)
            if java_key == python_key:
                best_match = (python_name, python_path)
                break
        if best_match:
            matched_pairs.append((java_name, best_match[0], java_key))
            used_python.add(best_match[0])

    if not matched_pairs:
        print("[WARN] No matching Java-Python file pairs found.")
        print(f"  Java files: {sorted(java_files.keys())}")
        print(f"  Python files: {sorted(python_files.keys())}")
        for f in dumps_dir.iterdir():
            if f.is_file() and f.suffix != '.json':
                print(f"    {f.name}")
        return 1

    all_passed = True
    total = 0
    passed_count = 0

    print("\n--- Comparing matched files ---")
    for java_name, python_name, key in sorted(matched_pairs):
        java_path = java_files[java_name]
        python_path = python_files[python_name]

        file_type = guess_file_type(key, java_path)
        total += 1

        if file_type == 'matrix':
            passed, msg = compare_matrices(str(java_path), str(python_path))
        elif file_type == 'clusters':
            passed, msg = compare_clusters(str(java_path), str(python_path))
        else:
            passed, msg = compare_text_files(str(java_path), str(python_path))

        status = "[PASS]" if passed else "[FAIL]"
        print(f"\n{key} ({file_type}):")
        print(f"  Java: {java_name}{java_path.suffix}")
        print(f"  Py:   {python_name}{python_path.suffix}")
        print(f"  {status} {msg}")

        if passed:
            passed_count += 1
        else:
            all_passed = False

    # Summary
    print("\n" + "=" * 70)
    print(f"Summary: {passed_count}/{total} comparisons passed")
    if all_passed:
        print("[PASS] ALL COMPARISONS PASSED - Implementations are equivalent!")
    else:
        print("[FAIL] SOME COMPARISONS FAILED - See details above")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Compare Java vs Python MCPT implementation parity."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Base output directory containing mcpt-dumps subdirectory (default: ./output/scene2)"
    )
    args = parser.parse_args()
    sys.exit(main(output_dir=args.output_dir))
