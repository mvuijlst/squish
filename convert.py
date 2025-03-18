import json
import pandas as pd
import os
import sys

def json_to_excel(json_file, excel_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Normalize the JSON data to a flat table
    df = pd.json_normalize(data, sep='_')
    
    # Save the dataframe to an Excel file
    df.to_excel(excel_file, index=False)

def excel_to_json(excel_file, json_file):
    df = pd.read_excel(excel_file, engine='openpyxl')
    
    # Convert the dataframe back to the original nested structure
    data = []
    for _, row in df.iterrows():
        entry = {
            "level": row["level"],
            "pull_blocks": row["pull_blocks"],
            "speed_up": row["speed_up"],
            "explosive_blocks": row["explosive_blocks"],
            "winning_level": row["winning_level"],
            "enemies": {}
        }
        
        if not pd.isna(row["enemies_hunter_count"]):
            entry["enemies"]["hunter"] = {
                "count": row["enemies_hunter_count"],
                "speed_ms": row["enemies_hunter_speed_ms"],
                "accuracy": row["enemies_hunter_accuracy"],
                "speed_variability": row["enemies_hunter_speed_variability"],
                "mutation_ratio": row["enemies_hunter_mutation_ratio"]
            }
            if not pd.isna(row.get("enemies_hunter_mutates_into")):
                entry["enemies"]["hunter"]["mutates_into"] = row["enemies_hunter_mutates_into"]
        
        if not pd.isna(row.get("enemies_egg_count")):
            entry["enemies"]["egg"] = {
                "count": row["enemies_egg_count"],
                "incubation_s": row["enemies_egg_incubation_s"],
                "hatches_into": row["enemies_egg_hatches_into"]
            }
        
        data.append(entry)
    
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python convert.py <input_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if input_file.endswith('.json'):
        json_to_excel(input_file, 'levels.xlsx')
        print(f"Converted {input_file} to levels.xlsx")
    elif input_file.endswith('.xlsx'):
        excel_to_json(input_file, 'levels.json')
        print(f"Converted {input_file} to levels.json")
    else:
        print("Unsupported file format. Please provide a .json or .xlsx file.")