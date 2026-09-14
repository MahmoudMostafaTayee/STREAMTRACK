import re

# Read topology log
with open(r'.\output\benchmark\log_topology.txt', encoding='utf-8') as f:
    lines = f.readlines()

# Extract all MCPT times
times = [float(m.group(1)) for line in lines if (m := re.search(r'Total MCPT Time:\s+([\d.]+)\s+ms', line))]

# Skip first 2 warmup entries
times = times[2:]

# In topology mode, there are 4 groups per window -> 4 MCPT calls per window
groups_per_window = 4
n_windows = len(times) // groups_per_window

print(f'Total MCPT entries (after warmup skip): {len(times)}')
print(f'Groups per window: {groups_per_window}')
print(f'Complete windows: {n_windows}')
print()

# Compute per-window stats
window_sums = []
window_maxes = []
all_calls = []

for w in range(n_windows):
    group_times = times[w*groups_per_window : (w+1)*groups_per_window]
    window_sums.append(sum(group_times))
    window_maxes.append(max(group_times))
    all_calls.extend(group_times)

avg_per_call = sum(all_calls) / len(all_calls)
avg_sum = sum(window_sums) / len(window_sums)
avg_max = sum(window_maxes) / len(window_maxes)

print(f'Avg MCPT per call (measured):     {avg_per_call:.2f} ms')
print(f'Avg window sum (sequential):      {avg_sum:.2f} ms')
print(f'Avg window max (parallel):        {avg_max:.2f} ms')
print()

# Read global log
with open(r'.\output\benchmark\log_global.txt', encoding='utf-8') as f:
    glines = f.readlines()

gtimes = [float(m.group(1)) for line in glines if (m := re.search(r'Total MCPT Time:\s+([\d.]+)\s+ms', line))]
gtimes = gtimes[2:]
global_avg = sum(gtimes) / len(gtimes)
print(f'Global avg (measured):            {global_avg:.2f} ms')
print()
print(f'Speedup (per call):    {global_avg/avg_per_call:.1f}x')
print(f'Speedup (sequential):  {global_avg/avg_sum:.1f}x')
print(f'Speedup (parallel):    {global_avg/avg_max:.1f}x')
