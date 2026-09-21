import json
import os

def fix_trains_null_times(input_path, output_path):
    """Fix remaining null time values in trains data"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    fixed_count = 0
    
    for feature in features:
        props = feature['properties']
        for time_field in ['arrival', 'departure']:
            time_val = props.get(time_field)
            if time_val is None:
                props[time_field] = ""
                fixed_count += 1
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return fixed_count

if __name__ == '__main__':
    base_path = os.path.join(os.path.dirname(__file__), 'data', 'processed')
    
    print("Fixing remaining null time values in trains data...")
    fixed = fix_trains_null_times(
        os.path.join(base_path, 'trains_cleaned.json'),
        os.path.join(base_path, 'trains_cleaned.json')
    )
    print(f"Fixed {fixed} null time values")
