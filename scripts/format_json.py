import sys
import os
import json

def format_file(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Formatted: {filepath}")
    except Exception as e:
        print(f"Error formatting {filepath}: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python format_json.py <file_or_directory>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    if os.path.isfile(target):
        format_file(target)
    elif os.path.isdir(target):
        count = 0
        for root, dirs, files in os.walk(target):
            for file in files:
                if file.endswith(".json"):
                    format_file(os.path.join(root, file))
                    count += 1
        if count == 0:
             print(f"No JSON files found in {target}")
    else:
        print(f"Target not found: {target}")

if __name__ == "__main__":
    main()
