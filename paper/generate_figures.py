"""
Generate publication-quality figures for the STREAMTRACK paper.
Outputs:
  - Evidence/speedup_bars.png   (log-scale bar chart for Table 2)
  - Evidence/scalability_curve.png (projected latency vs camera count)
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), 'Evidence')
os.makedirs(OUT_DIR, exist_ok=True)

# Use a clean, publication-friendly style
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

# =============================================================================
# FIGURE 1: Speedup Bar Chart (Table 2 data)
# =============================================================================
def generate_speedup_bars():
    stages = [
        'Similarity Matrix\nGeneration',
        'Similarity Matrix\nZeroing',
        'Representative\nSelection',
        'Hierarchical\nClustering (HC)',
        'Global ID\nAssignment',
    ]
    theirs_ms = [1260.00, 253.00, 230.70, 415.00, 52.00]
    ours_ms   = [49.27,   0.98,   221.15, 241.17, 2.46]

    x = np.arange(len(stages))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 4.5))

    bars_theirs = ax.bar(x - width/2, theirs_ms, width, label='Theirs (Batch)',
                         color='#E74C3C', edgecolor='#C0392B', linewidth=0.8, alpha=0.9)
    bars_ours   = ax.bar(x + width/2, ours_ms,   width, label='Ours-Base (Streaming)',
                         color='#2E86C1', edgecolor='#1B4F72', linewidth=0.8, alpha=0.9)

    ax.set_yscale('log')
    ax.set_ylabel('Processing Time (ms, log scale)')
    ax.set_xticks(x)
    ax.set_xticklabels(stages)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.set_ylim(0.5, 3000)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Add speedup annotations above each pair
    speedups = [t/o for t, o in zip(theirs_ms, ours_ms)]
    for i, sp in enumerate(speedups):
        y_pos = max(theirs_ms[i], ours_ms[i]) * 1.4
        ax.annotate(f'{sp:.1f}×', xy=(x[i], y_pos),
                    ha='center', va='bottom', fontsize=9, fontweight='bold',
                    color='#1A5276',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#D4E6F1', edgecolor='#1A5276', alpha=0.8))

    plt.tight_layout()
    path = os.path.join(OUT_DIR, 'speedup_bars.png')
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")


# =============================================================================
# FIGURE 2: Scalability Projection Curve
# =============================================================================
def generate_scalability_curve():
    cameras = np.array([2, 4, 8, 16, 32, 64])

    # Theirs: O(N^2) — batch processes ALL tracklets globally
    # Base measurement: 4 cameras → 2210.70 ms, assume ~48 tracklets per camera
    # Cost ~ (cameras * tracklets_per_cam)^2
    tracklets_per_cam = 48
    theirs_base = 2210.70  # at 4 cameras
    N_base = 4 * tracklets_per_cam
    theirs_latency = theirs_base * (cameras * tracklets_per_cam / N_base) ** 2

    # Ours-Base: Same O(N^2) but with 4.28× constant factor improvement
    ours_base_latency = theirs_latency / 4.28

    # Ours-Opt: O(M * n^2) — partitioned into clusters of ~2 cameras each
    # Base measurement: 2-camera group → 4.25 ms
    cluster_size = 2
    num_clusters = cameras / cluster_size
    ours_opt_latency = num_clusters * 4.25  # linear in number of clusters

    fig, ax = plt.subplots(figsize=(7, 4.5))

    ax.plot(cameras, theirs_latency, 'o-', color='#E74C3C', linewidth=2,
            markersize=7, label='Theirs — $O(N^2)$ batch', zorder=3)
    ax.plot(cameras, ours_base_latency, 's--', color='#F39C12', linewidth=2,
            markersize=7, label='Ours-Base — $O(N^2)$ streaming', zorder=3)
    ax.plot(cameras, ours_opt_latency, 'D-', color='#2E86C1', linewidth=2.5,
            markersize=7, label='Ours-Opt — $O(M)$ topology-aware', zorder=3)

    # Real-time threshold line
    ax.axhline(y=1000, color='#27AE60', linestyle=':', linewidth=1.5, alpha=0.7)
    ax.text(50, 1150, 'Real-time threshold (1s)', color='#27AE60',
            fontsize=9, ha='center', style='italic')

    ax.set_xlabel('Number of Cameras')
    ax.set_ylabel('Projected MCPT Latency (ms)')
    ax.set_yscale('log')
    ax.set_xscale('log', base=2)
    ax.set_xticks(cameras)
    ax.set_xticklabels([str(c) for c in cameras])
    ax.legend(loc='upper left', framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, 'scalability_curve.png')
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")


if __name__ == '__main__':
    generate_speedup_bars()
    generate_scalability_curve()
    print("Done!")
