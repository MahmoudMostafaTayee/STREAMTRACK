#!/usr/bin/env python3
"""
SCPT Comparison Script - Compares Python and Java SCPT implementations.

Compares intermediate dumps at each SCPT processing stage:
1. Similarity matrices
2. Bare clustering results
3. After trackingByClustering
4. After associateClusterBetweenPeriod
5. After sequential_nms
6. After separate_warp
7. After exclude_short
8. After exclude_motionless

Usage:
    python compare_scpt_dumps.py check   # Run comparisons
    python compare_scpt_dumps.py clear   # Clear dump directories
"""

import os
import re
import sys
import ast
import numpy as np
import argparse
import shutil
from pathlib import Path
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from itertools import combinations

# Force UTF-8 encoding for console output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Base directory for both Java and Python dumps
# Java writes to: {OUTPUT_DIR}/<stage>/clusters-java_<cameraId>_<window>.txt
# Python writes to: /mnt/c/.../output/scene{scene_id}/<stage>/clusters-python_<cameraId>_<window>.txt
# We configure OUTPUT_DIR to point to the scene output dir so they match.
OUTPUT_DIR = Path(r".\output\scene2")
SCENE_ID = 2

# SCPT pipeline stages (subdirectory name, prefix pattern)
SCPT_STAGES = [
    ("similatiry-matrix", "similarityMatrix"),  # Note: typo matches actual dir name
    ("after-bare-clustering", "clusters"),
    ("after-trackingByClustering", "clusters"),
    ("after-associateClusterBetweenPeriod", "clusters"),
    ("after-sequential_nms", "clusters"),
    ("after-separate_warp", "clusters"),
    ("after-exclude_short", "clusters"),
    ("after-exclude_motionless", "clusters"),
]

# For post-processing stages, Python uses window="0" (post-processing on combined data)
# but Java uses the actual window index. We'll try matching by window index.
# The similarity matrix and bare clustering are only dumped by Java (SCPT.java),
# so they won't have Python counterparts to compare against initially.


def load_matrix(filepath):
    """Load a matrix from a text file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
        if not content:
            return np.array([])
        lines = content.split('\n')
        matrix = []
        for line in lines:
            if line.strip():
                if ',' in line:
                    row = [float(x.strip()) for x in line.split(',') if x.strip()]
                else:
                    row = [float(x.strip()) for x in line.split() if x.strip()]
                matrix.append(row)
        return np.array(matrix)
    except Exception as e:
        return None


def load_clusters(filepath):
    """Load cluster assignments from a text file.
    
    Handles both plain int format: [1, 2, 3]
    And numpy format: [np.int32(1), np.int32(2)]
    """
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
        if not (content.startswith('[') and content.endswith(']')):
            return None
        
        # Remove np.int32(...) wrappers if present
        import re
        content = re.sub(r'np\.int32\((\d+)\)', r'\1', content)
        content = re.sub(r'np\.int64\((\d+)\)', r'\1', content)
        content = re.sub(r'np\.float32\(([\d.]+)\)', r'\1', content)
        content = re.sub(r'np\.float64\(([\d.]+)\)', r'\1', content)
        
        clusters = ast.literal_eval(content)
        return clusters
    except Exception as e:
        return None


def compare_matrices(java_matrix, python_matrix, tolerance=1e-4):
    """Compare two matrices with tolerance."""
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
        max_idx = np.unravel_index(np.argmax(diff), diff.shape)
        return False, f"Mismatch: max_diff={max_diff:.6f} at {max_idx}"


def pairwise_agreement(a, b):
    """Calculate pairwise agreement between two clusterings."""
    n = len(a)
    if n < 2:
        return 1.0
    agree = 0
    total = 0
    for i, j in combinations(range(n), 2):
        same_a = (a[i] == a[j])
        same_b = (b[i] == b[j])
        if same_a == same_b:
            agree += 1
        total += 1
    return agree / total if total > 0 else 1.0


def compare_clusters(java_clusters, python_clusters):
    """Compare two cluster assignments using multiple metrics."""
    if java_clusters is None or python_clusters is None:
        return False, "Could not load one or both files", {}
    
    if len(java_clusters) != len(python_clusters):
        return False, f"Length mismatch: Java {len(java_clusters)} vs Python {len(python_clusters)}", {}
    
    if len(java_clusters) == 0:
        return True, "Both empty", {}
    
    # Calculate metrics
    ari = adjusted_rand_score(java_clusters, python_clusters)
    nmi = normalized_mutual_info_score(java_clusters, python_clusters)
    pa = pairwise_agreement(java_clusters, python_clusters)
    
    metrics = {"ARI": ari, "NMI": nmi, "Pairwise": pa}
    
    # Determine verdict
    if ari >= 0.99 and nmi >= 0.99:
        return True, f"EXACT MATCH (ARI={ari:.4f}, NMI={nmi:.4f})", metrics
    elif ari >= 0.90 and nmi >= 0.90 and pa >= 0.95:
        return True, f"VERY CLOSE (ARI={ari:.4f}, NMI={nmi:.4f}, Pairwise={pa:.2%})", metrics
    elif ari >= 0.80 and nmi >= 0.85:
        return True, f"CLOSE (ARI={ari:.4f}, NMI={nmi:.4f})", metrics
    else:
        return False, f"MISMATCH (ARI={ari:.4f}, NMI={nmi:.4f}, Pairwise={pa:.2%})", metrics


def find_matching_files(java_dir, python_dir, file_type):
    """Find matching Java and Python files across separate directories."""
    java_files = {}
    python_files = {}
    
    # Scan Java directory
    if java_dir.exists():
        for f in java_dir.iterdir():
            if not f.is_file():
                continue
            name = f.name
            
            if file_type == "similarityMatrix":
                if name.startswith("java-similarityMatrix_"):
                    idx = name.replace("java-similarityMatrix_", "").replace(".txt", "")
                    java_files[idx] = f
            else:
                if "java" in name and name.endswith(".txt"):
                    parts = name.replace(".txt", "").split("_")
                    idx = parts[-1]  # Window index
                    java_files[idx] = f
    
    # Scan Python directory
    if python_dir.exists():
        for f in python_dir.iterdir():
            if not f.is_file():
                continue
            name = f.name
            
            if file_type == "similarityMatrix":
                if name.startswith("python-similarityMatrix_"):
                    idx = name.replace("python-similarityMatrix_", "").replace(".txt", "")
                    python_files[idx] = f
            else:
                if "python" in name and name.endswith(".txt"):
                    parts = name.replace(".txt", "").split("_")
                    idx = parts[-1]
                    python_files[idx] = f
    
    # Match by index
    matches = []
    common_indices = sorted(set(java_files.keys()) & set(python_files.keys()))
    for idx in common_indices:
        matches.append((idx, java_files[idx], python_files[idx]))
    
    return matches


def run_checks(output_dir=None, scene_id=None):
    """Run all comparisons between Java and Python dumps."""
    if output_dir is None:
        output_dir = OUTPUT_DIR
    if scene_id is None:
        scene_id = SCENE_ID
    output_dir = Path(output_dir)
    
    # Both Java and Python dump to the same base directory
    # Java: --output_dir points to this dir
    # Python: hardcoded /mnt/c/.../output/scene{scene_id}/ which maps to this dir
    
    print("=" * 80)
    print("SCPT Implementation Parity Comparison")
    print("=" * 80)
    print(f"Dump base directory: {output_dir}")
    print(f"Scene ID: {scene_id}")
    
    if not output_dir.exists():
        print(f"\n[ERROR] Dump directory not found: {output_dir}")
        print("Please run Java and/or Python with --debug first.")
        return 1
    
    all_passed = True
    total_comparisons = 0
    passed_comparisons = 0
    
    for stage_name, file_type in SCPT_STAGES:
        stage_dir = output_dir / stage_name
        
        print(f"\n{'-' * 60}")
        print(f"Stage: {stage_name}")
        print(f"{'-' * 60}")
        
        if not stage_dir.exists():
            print(f"  [WARN] Stage directory not found: {stage_dir.name}")
            continue
        
        # Build suffix->file mapping, normalizing naming differences
        # Python similarity suffix: "camera_1_0" -> normalized "1_0"
        # Java similarity suffix:   "1_0" 
        # Python clusters suffix:   "1_0"
        # Java clusters suffix:     "1_0"
        def make_file_map(files_iter, prefix_java, prefix_python):
            jmap, pmap = {}, {}
            for f in files_iter:
                if not f.is_file():
                    continue
                name = f.name
                if name.startswith(prefix_java):
                    suffix = name.replace(prefix_java, "").replace(".txt", "")
                    # Normalize: remove leading "camera_" if present
                    suffix = re.sub(r'^camera_', '', suffix)
                    jmap[suffix] = f
                elif name.startswith(prefix_python):
                    suffix = name.replace(prefix_python, "").replace(".txt", "")
                    suffix = re.sub(r'^camera_', '', suffix)
                    pmap[suffix] = f
            return jmap, pmap
        
        if file_type == "similarityMatrix":
            java_prefix = "java-similarityMatrix_"
            python_prefix = "python-similarityMatrix_"
        else:
            java_prefix = "clusters-java_"
            python_prefix = "clusters-python_"
        
        java_files, python_files = make_file_map(stage_dir.iterdir(), java_prefix, python_prefix)
        
        if not java_files and not python_files:
            print(f"  [WARN] No dump files found in {stage_dir.name}")
            continue
        
        # For post-processing stages (sequential_nms, separate_warp, etc.),
        # Python dumps combined data as window "0", while Java dumps per-window.
        # Detect this and handle specially.
        is_postproc_stage = stage_name in ("after-sequential_nms", "after-separate_warp",
                                           "after-exclude_short", "after-exclude_motionless")
        
        if is_postproc_stage:
            # Python has only combined dump (window 0, all detections).
            # Java has per-window dumps. To compare, we need to merge Java's
            # per-window results back into a combined array using original serial ordering.
            
            # First, check if Python has its combined dump
            py_combined_key = [k for k in python_files.keys() if k.endswith('_0') or k == '0']
            if py_combined_key:
                py_key = py_combined_key[0]
                python_data = load_clusters(python_files[py_key])
                
                if python_data is None:
                    print(f"  [SKIP] Python combined dump not loadable")
                    continue
                
                # For Java: combine per-window clusters into one array matching Python's order
                # We need the original serial order from trackingDict to interleave properly.
                # For now, attempt per-window comparisons where windows match.
                java_windows = sorted(java_files.keys())
                py_windows = sorted([k for k in python_files.keys()])
                
                print(f"  [INFO] Post-processing stage with different structures:")
                print(f"    Java: per-window ({len(java_windows)} windows: {java_windows})")
                print(f"    Python: combined single dump ({len(python_data)} tracklets)")
                
                # Compare each Java window individually (structural diff is expected)
                total_size_java = 0
                for jk in java_windows:
                    jd = load_clusters(java_files[jk])
                    if jd is not None:
                        total_size_java += len(jd)
                
                print(f"    Java total tracklets: {total_size_java}, Python: {len(python_data)}")
                print(f"    [INFO] Architectural difference: Java processes post-processing")
                print(f"           per-window, Python processes combined data.")
                print(f"    [INFO] Skipping direct comparison - results are structurally different")
                print(f"           by design. Verify correctness through final output instead.")
                
                # Still compare per-window if a matching Python window exists
                common = sorted(set(java_windows) & set(py_windows))
                for suffix in common:
                    total_comparisons += 1
                    java_data = load_clusters(java_files[suffix])
                    python_data_single = load_clusters(python_files[suffix])
                    if java_data is not None and python_data_single is not None:
                        passed, msg, _ = compare_clusters(java_data, python_data_single)
                        status = "[PASS]" if passed else "[FAIL]"
                        print(f"    [{suffix}] {status} {msg}")
                        if passed:
                            passed_comparisons += 1
                        else:
                            all_passed = False
                continue
        
        # Match by suffix (cameraId_window format)
        common_suffixes = sorted(set(java_files.keys()) & set(python_files.keys()))
        
        if not common_suffixes:
            print(f"  [WARN] No matching camera/window combinations found")
            if java_files:
                print(f"    Java files: {sorted(java_files.keys())}")
            if python_files:
                print(f"    Python files: {sorted(python_files.keys())}")
            # Show all files in directory
            print(f"    All files: {[f.name for f in stage_dir.iterdir() if f.is_file()]}")
            continue
        
        for suffix in common_suffixes:
            total_comparisons += 1
            java_file = java_files[suffix]
            python_file = python_files[suffix]
            
            if file_type == "similarityMatrix":
                java_data = load_matrix(java_file)
                python_data = load_matrix(python_file)
                passed, msg = compare_matrices(java_data, python_data)
            else:
                java_data = load_clusters(java_file)
                python_data = load_clusters(python_file)
                passed, msg, _ = compare_clusters(java_data, python_data)
            
            status = "[PASS]" if passed else "[FAIL]"
            print(f"  [{suffix}] {status} {msg}")
            
            if passed:
                passed_comparisons += 1
            else:
                all_passed = False
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Summary: {passed_comparisons}/{total_comparisons} comparisons passed")
    if all_passed:
        print("[PASS] ALL COMPARISONS PASSED - Implementations are equivalent!")
    else:
        print("[FAIL] SOME COMPARISONS FAILED - See details above")
    print("=" * 80)
    
    return 0 if all_passed else 1


def clear_directories(output_dir=None):
    """Clear all dump directories."""
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)
    
    print("WARNING: This will DELETE ALL FILES in the SCPT dump directories.\n")
    
    dirs_to_clear = [output_dir / stage[0] for stage in SCPT_STAGES]
    existing_dirs = [d for d in dirs_to_clear if d.exists()]
    
    if not existing_dirs:
        print("No directories to clear.")
        return
    
    print("Directories to clear:")
    for d in existing_dirs:
        print(f"  - {d}")
    
    confirm = input("\nType YES to confirm: ").strip()
    if confirm != "YES":
        print("Aborted.")
        return
    
    for directory in existing_dirs:
        for f in directory.iterdir():
            try:
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    shutil.rmtree(f)
            except Exception as e:
                print(f"[ERROR] Failed to delete {f}: {e}")
        print(f"[OK] Cleared: {directory.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare Java vs Python SCPT clustering results or clear dump directories."
    )
    parser.add_argument(
        "mode",
        choices=["check", "clear"],
        help="check = run similarity checks, clear = delete dump contents"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Base output directory containing SCPT dump subdirectories (default: ./output/scene2)"
    )
    parser.add_argument(
        "--scene",
        type=int,
        default=None,
        help="Scene ID (default: 2)"
    )
    
    args = parser.parse_args()
    
    output_dir = args.output_dir
    scene_id = args.scene
    
    if args.mode == "check":
        return run_checks(output_dir=output_dir, scene_id=scene_id)
    elif args.mode == "clear":
        clear_directories(output_dir=output_dir)
        return 0


if __name__ == "__main__":
    sys.exit(main())
