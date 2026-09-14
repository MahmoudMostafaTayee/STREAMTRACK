"""
Generate two data-driven benchmark figures for the STREAMTRACK paper.

Data sources:
  - output/streaming_25w.txt           (per-window streaming stage timings, UTF-16-LE)
  - output/batch_incremental_25w.log   (incremental per-window batch MCPT timings, UTF-16-LE)
  - output/batch_25w.txt               (cumulative batch stage timings, UTF-16-LE)

Outputs (in paper/Evidence/):
  - fig_cumulative_mcpt.png   — Figure 1: Cumulative MCPT latency (streaming vs batch)
  - fig_stage_speedup.png     — Figure 2: Per-stage speedup bar chart
"""

import re
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── Output directory ──────────────────────────────────────────────────────
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT_DIR, exist_ok=True)

# ── Publication styling ───────────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

COLOR_STREAM   = '#2E86C1'
COLOR_BATCH    = '#E74C3C'
COLOR_SPEEDUP  = '#27AE60'
COLOR_REF      = '#7F8C8D'

# ── Parse streaming log ──────────────────────────────────────────────────
def parse_streaming_log(path):
    """Return list of dicts: {window, stages:{name:ms}, total, scpt_per_cam:{cam:ms}, scpt_total:ms}"""
    with open(path, 'r', encoding='utf-16-le', errors='replace') as f:
        content = f.read()

    lines = content.split('\n')

    # First pass: SCPT per-camera per-window
    scpt_windows = {}
    for line in lines:
        ls = line.strip()
        m = re.search(r'\[camera_(\d+)\] Window (\d+) Finished\. Time: (\d+) ms', ls)
        if m:
            cam = m.group(1)
            win = int(m.group(2))
            t = float(m.group(3))
            if win not in scpt_windows:
                scpt_windows[win] = {}
            scpt_windows[win][cam] = t

    # Second pass: MCPT PERFORMANCE REPORT per window
    windows = []
    current = None
    for line in lines:
        ls = line.strip()

        m = re.search(r'PERFORMANCE REPORT.*Window:\s*(\d+)', ls)
        if m:
            if current:
                windows.append(current)
            widx = int(m.group(1))
            cams = scpt_windows.get(widx, {})
            scpt_sum = sum(cams.values())
            current = {
                'window': widx,
                'stages': {},
                'scpt_per_cam': dict(cams),
                'scpt_total': scpt_sum,
            }
            continue

        if current is None:
            continue

        m = re.search(r'(Stage \d+: .*?):\s+(\d+\.?\d*)\s*ms', ls)
        if m:
            current['stages'][m.group(1).strip()] = float(m.group(2))

        m = re.search(r'Total MCPT Time:\s+(\d+\.?\d*)\s*ms', ls)
        if m:
            current['total'] = float(m.group(1))

    if current:
        windows.append(current)

    return windows


# ── Parse batch log (cumulative stages) ──────────────────────────────────
def parse_batch_log(path):
    """Return dict of {stage_name: ms}"""
    with open(path, 'r', encoding='utf-16-le', errors='replace') as f:
        content = f.read()

    stages = {}
    for line in content.split('\n'):
        m = re.search(r'(Stage \d+: .*?):\s+(\d+\.?\d*)\s*ms', line)
        if m:
            stages[m.group(1).strip()] = float(m.group(2))

    m = re.search(r'Total Core Processing Time:\s+(\d+\.?\d*)\s*ms', content)
    if m:
        stages['Total Core'] = float(m.group(1))

    return stages


# ── Parse incremental benchmark log (per-window batch MCPT) ────────────
def parse_incremental_benchmark(path):
    """
    Return list of (n, tracklets, cumulative_ms) from MCPT_BENCHMARK lines.
    File is UTF-16-LE encoded.
    """
    with open(path, 'r', encoding='utf-16-le', errors='replace') as f:
        content = f.read()

    results = []
    for line in content.split('\n'):
        m = re.match(r'MCPT_BENCHMARK\s+(\d+)\s+(\d+)\s+([0-9.]+)', line.strip())
        if m:
            n = int(m.group(1))
            tracklets = int(m.group(2))
            cumul_ms = float(m.group(3))
            results.append((n, tracklets, cumul_ms))

    return results


# ══════════════════════════════════════════════════════════════════════════
# FIGURE 1: Cumulative MCPT Latency (Streaming vs Batch)
# ══════════════════════════════════════════════════════════════════════════
def generate_cumulative_mcpt(stream_windows, batch_incremental, num_windows=25):
    """
    Cumulative MCPT-only latency chart.

    - Streaming: actual per-window Total MCPT Time accumulated.
    - Batch: actual per-window incremental MCPT measurements from
      runIncrementalMcptBenchmark(), re-processing all accumulated
      tracklets at each window.
    """
    fig, ax = plt.subplots(figsize=(9, 5.5))

    windows = list(range(1, num_windows + 1))

    # ── Streaming cumulative ──
    mcpt_per_win = [w['total'] for w in stream_windows]
    stream_cumul = []
    s = 0
    for v in mcpt_per_win:
        s += v
        stream_cumul.append(s)
    total_stream = s

    # ── Batch cumulative (real incremental measurements) ──
    batch_cumul = [entry[2] for entry in batch_incremental]  # cumulative_ms
    total_batch = batch_cumul[-1] if batch_cumul else 0

    speedup = total_batch / total_stream if total_stream > 0 else 0

    # ── Plot ──
    ax.plot(windows, batch_cumul, 's-', color=COLOR_BATCH, linewidth=2.5,
            markersize=5, markerfacecolor='white',
            label='Java Batch Baseline', zorder=3)
    ax.plot(windows, stream_cumul, 'o-', color=COLOR_STREAM, linewidth=2.5,
            markersize=5, label='StreamTrack (Java streaming)', zorder=4)

    # Fill
    ax.fill_between(windows, stream_cumul, batch_cumul, alpha=0.10,
                    color=COLOR_SPEEDUP,
                    label=f'Savings ({speedup:.1f}\u00d7)')

    # ── Batch annotation ──
    ax.annotate(f'Batch (cumulative): {total_batch:,.0f} ms',
                xy=(num_windows, batch_cumul[-1]),
                xytext=(num_windows * 0.62, batch_cumul[-1] * 0.80),
                fontsize=10, color=COLOR_BATCH, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=COLOR_BATCH, lw=1.5),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FDEDEC',
                          edgecolor=COLOR_BATCH, alpha=0.9))

    # ── Streaming annotation ──
    ax.annotate(f'Streaming (cumulative): {total_stream:,.0f} ms',
                xy=(num_windows, stream_cumul[-1]),
                xytext=(num_windows * 0.62, stream_cumul[-1] * 1.3),
                fontsize=10, color=COLOR_STREAM, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=COLOR_STREAM, lw=1.5),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#D6EAF8',
                          edgecolor=COLOR_STREAM, alpha=0.9))

    # ── Speedup callout ──
    ax.text(0.97, 0.93,
            f'Cumulative Speedup\n{speedup:.1f}\u00d7',
            transform=ax.transAxes, ha='right', va='top', fontsize=13,
            fontweight='bold', color='#1A5276',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#D5F5E3',
                      edgecolor=COLOR_SPEEDUP, alpha=0.9))

    ax.set_title('Cumulative MCPT Latency \u2014 Streaming vs Batch Baseline',
                 fontweight='bold')
    ax.set_xlabel('Synchronisation Window')
    ax.set_ylabel('Cumulative MCPT Time (ms)')
    ax.set_xticks(windows)
    ax.legend(loc='upper left', framealpha=0.9)
    ax.grid(True, linestyle='--', alpha=0.25)
    ax.set_xlim(0.5, num_windows + 0.5)
    ax.set_ylim(bottom=0)

    path = os.path.join(OUT_DIR, 'fig_cumulative_mcpt.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')
    print(f'  Streaming cumulative: {total_stream:,.0f} ms')
    print(f'  Batch cumulative:     {total_batch:,.0f} ms')
    print(f'  Speedup:              {speedup:.1f}x')


# ══════════════════════════════════════════════════════════════════════════
# FIGURE 2: Per-Stage Speedup Bar Chart
# ══════════════════════════════════════════════════════════════════════════
def generate_stage_speedup(stream_windows, batch_stages):
    # ── Map streaming stages to batch stages ──
    stage_map = {
        'Stage 1: Measure World Coordinates':   'Stage 3: Measure World Coordinates',
        'Stage 2: Representative Selection':     'Stage 4: Representative Selection',
        'Stage 3: Matrix Gen (Raw)':             'Stage 5: Matrix Gen (Raw)',
        'Stage 4: Matrix Zeroing':               'Stage 6: Matrix Zeroing',
        'Stage 5: Similarity Replace (World)':   'Stage 7: Similarity Replace (World)',
        'Stage 6: Clustering (HC)':              'Stage 8: Clustering (HC)',
        'Stage 7: Global ID Assignment':         'Stage 9: Global ID Assignment',
    }

    display_names = [
        'Measure World\nCoordinates',
        'Representative\nSelection',
        'Re-ID Similarity\nMatrix',
        'Matrix\nZeroing',
        'Similarity\nReplace (World)',
        'Clustering\n(HAC)',
        'Global ID\nAssignment',
    ]

    s_names = list(stage_map.keys())

    # Compute per-stage averages from streaming data
    s_avgs = {}
    for s_name in s_names:
        vals = []
        for w in stream_windows:
            if s_name in w['stages']:
                vals.append(w['stages'][s_name])
        s_avgs[s_name] = np.mean(vals) if vals else 0

    # Build arrays
    speedups = []
    batch_vals = []
    stream_vals = []
    labels = []

    for s_name, b_name in stage_map.items():
        if b_name in batch_stages and s_avgs[s_name] > 0:
            b_val = batch_stages[b_name]
            s_val = s_avgs[s_name]
            speedups.append(b_val / s_val)
            batch_vals.append(b_val)
            stream_vals.append(s_val)
            labels.append(display_names[len(speedups) - 1])

    # ── Figure 2a: Grouped bar chart (batch vs streaming, log scale) ──
    fig, ax = plt.subplots(figsize=(10, 5))

    x = np.arange(len(labels))
    width = 0.35

    bars_batch = ax.bar(x - width/2, batch_vals, width,
                        label='Batch (cumulative)', color=COLOR_BATCH,
                        edgecolor='#C0392B', linewidth=0.6, alpha=0.9)
    bars_stream = ax.bar(x + width/2, stream_vals, width,
                         label='Streaming (per-window avg)', color=COLOR_STREAM,
                         edgecolor='#1B4F72', linewidth=0.6, alpha=0.9)

    ax.set_yscale('log')
    ax.set_ylabel('Processing Time (ms, log scale)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.set_ylim(0.01, 50000)
    ax.grid(axis='y', alpha=0.25, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Speedup annotations on bars
    for i, sp in enumerate(speedups):
        y_pos = max(batch_vals[i], stream_vals[i]) * 1.5
        ax.annotate(f'{sp:.1f}×', xy=(x[i], y_pos),
                    ha='center', va='bottom', fontsize=8.5, fontweight='bold',
                    color='#1A5276',
                    bbox=dict(boxstyle='round,pad=0.2',
                              facecolor='#D4E6F1', edgecolor='#1A5276', alpha=0.85))

    ax.set_title('Stage-by-Stage Performance: Batch vs Streaming',
                 fontweight='bold')

    path = os.path.join(OUT_DIR, 'fig_stage_speedup.png')
    fig.savefig(path)
    plt.close(fig)
    print(f'  Saved: {path}')


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
def main():
    # Paths (relative to repo root — script lives in paper/Evidence/)
    repo_root = os.path.join(os.path.dirname(__file__), '..', '..')
    stream_path = os.path.join(repo_root, 'output', 'streaming_25w.txt')
    batch_path  = os.path.join(repo_root, 'output', 'batch_25w.txt')
    incremental_path = os.path.join(repo_root, 'output', 'batch_incremental_25w.log')

    print('Parsing streaming log...')
    stream_windows = parse_streaming_log(stream_path)
    print(f'  Found {len(stream_windows)} windows')

    print('Parsing incremental batch benchmark...')
    batch_incremental = parse_incremental_benchmark(incremental_path)
    print(f'  Found {len(batch_incremental)} data points')
    for n, trk, cumul in batch_incremental:
        print(f'    Window {n}: {trk} tracklets, {cumul:.2f} ms cumulative')

    print('Parsing batch stage log...')
    batch_stages = parse_batch_log(batch_path)
    batch_total = batch_stages.get('Total Core', 0)
    print(f'  Batch total core: {batch_total:.2f} ms')
    for k, v in batch_stages.items():
        if k != 'Total Core':
            print(f'    {k}: {v:.2f} ms')

    # ── Generate Figure 1: Cumulative End-to-End ──
    print('\nGenerating Figure 1: Cumulative End-to-End Latency...')
    generate_cumulative_mcpt(stream_windows, batch_incremental, num_windows=len(batch_incremental))

    # ── Generate Figure 2: Stage Speedup ──
    print('Generating Figure 2: Stage Speedup...')
    generate_stage_speedup(stream_windows, batch_stages)

    print('\nDone! Both figures saved to paper/Evidence/')


if __name__ == '__main__':
    main()
