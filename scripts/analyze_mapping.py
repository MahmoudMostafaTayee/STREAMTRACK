#!/usr/bin/env python3
"""Analyze OfflineID mapping between Java and Python final outputs."""

import json
import sys
from collections import defaultdict

def analyze_mapping(java_path, python_path):
    with open(java_path) as f:
        java = json.load(f)
    
    raw = open(python_path).read().replace('NaN', 'null')
    py = json.loads(raw)
    
    java_items = sorted(java['1'].values(), key=lambda x: (x['Frame'], x['Coordinate']['x1'], x['Coordinate']['y1']))
    py_items = sorted(py['1'].values(), key=lambda x: (x['Frame'], x['Coordinate']['x1'], x['Coordinate']['y1']))
    
    # Count how many detections per OfflineID
    java_counts = defaultdict(int)
    py_counts = defaultdict(int)
    for v in java['1'].values():
        java_counts[v.get('OfflineID')] += 1
    for v in py['1'].values():
        py_counts[v.get('OfflineID')] += 1
    
    print("Java OfflineID counts:")
    for jid in sorted(java_counts.keys()):
        print(f"  ID {jid:4d}: {java_counts[jid]:4d} detections")
    
    print(f"\nPython OfflineID counts:")
    for pid in sorted(py_counts.keys()):
        print(f"  ID {pid:4d}: {py_counts[pid]:4d} detections")
    
    # For the ambiguous -1 in Java, see what Python IDs they map to
    print("\n\nAmbiguous -1 cases in Java:")
    for jv, pv in zip(java_items, py_items):
        jid = jv.get('OfflineID')
        pid = pv.get('OfflineID')
        if jid == -1 and pid == -1:
            continue
        if jid == -1 or pid == -1:
            same_frame = jv['Frame'] == pv['Frame']
            same_x1 = abs(jv['Coordinate']['x1'] - pv['Coordinate']['x1']) < 2
            same_y1 = abs(jv['Coordinate']['y1'] - pv['Coordinate']['y1']) < 2
            if same_frame and same_x1 and same_y1:
                print(f"  Frame={jv['Frame']}: Java={jid} Python={pid}")

if __name__ == "__main__":
    analyze_mapping(sys.argv[1] if len(sys.argv) > 1 else "output/scene2/batch_whole_tracking_results.json",
                    sys.argv[2] if len(sys.argv) > 2 else "output/scene2/python_whole_tracking_results.json")
