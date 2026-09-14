#!/usr/bin/env python3
"""Compare final tracking outputs between Java and Python pipelines."""

import json
import sys

def compare_outputs(java_path, python_path):
    with open(java_path) as f:
        java = json.load(f)
    
    # Python file might have NaN - handle that
    raw = open(python_path).read().replace('NaN', 'null')
    py = json.loads(raw)
    
    for cam_id in java:
        if cam_id not in py:
            print(f"Camera {cam_id} missing from Python")
            continue
        
        java_items = sorted(java[cam_id].values(), key=lambda x: (x['Frame'], x['Coordinate']['x1'], x['Coordinate']['y1']))
        py_items = sorted(py[cam_id].values(), key=lambda x: (x['Frame'], x['Coordinate']['x1'], x['Coordinate']['y1']))
        
        print(f"Camera {cam_id}: Java {len(java_items)} entries, Python {len(py_items)} entries")
        
        mismatch = 0
        match_count = 0
        max_mismatches = 20
        id_mapping = {}  # java_id -> set of python_ids
        
        for i, (jv, pv) in enumerate(zip(java_items, py_items)):
            same_frame = jv['Frame'] == pv['Frame']
            same_x1 = abs(jv['Coordinate']['x1'] - pv['Coordinate']['x1']) < 2
            same_y1 = abs(jv['Coordinate']['y1'] - pv['Coordinate']['y1']) < 2
            
            if same_frame and same_x1 and same_y1:
                jid = jv.get('OfflineID')
                pid = pv.get('OfflineID')
                if jid != pid:
                    mismatch += 1
                    if jid not in id_mapping:
                        id_mapping[jid] = set()
                    id_mapping[jid].add(pid)
                    if mismatch <= max_mismatches:
                        print(f"  MISMATCH Frame={jv['Frame']} pos=({jv['Coordinate']['x1']},{jv['Coordinate']['y1']}): "
                              f"Java OfflineID={jid} vs Python OfflineID={pid}")
                else:
                    match_count += 1
                    if jid not in id_mapping:
                        id_mapping[jid] = set()
                    id_mapping[jid].add(pid)
        
        total_compared = mismatch + match_count
        print(f"  Matched: {match_count}/{total_compared} ({match_count/total_compared*100:.1f}%)")
        print(f"  Mismatched: {mismatch}/{total_compared} ({mismatch/total_compared*100:.1f}%)")
        print(f"\n  Java OfflineID -> Python OfflineID mapping:")
        consistent = 0
        ambiguous = 0
        for jid in sorted(id_mapping.keys()):
            pids = id_mapping[jid]
            if len(pids) == 1:
                consistent += 1
            else:
                ambiguous += 1
            print(f"    Java {jid:4d} -> Python {sorted(pids)}")
        print(f"\n  Consistent mappings (1-to-1): {consistent}")
        print(f"  Ambiguous mappings: {ambiguous}")


if __name__ == "__main__":
    java_path = sys.argv[1] if len(sys.argv) > 1 else "output/scene2/batch_whole_tracking_results.json"
    python_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not python_path:
        print("Usage: python scripts/compare_final_outputs.py <java_results.json> <python_results.json>")
        print("  java_path default: output/scene2/batch_whole_tracking_results.json")
        print("  Provide the path to the Python pipeline's whole_tracking_results.json as the second argument.")
        sys.exit(1)
    
    compare_outputs(java_path, python_path)
