import json
import os

def find_invalid_times(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    invalid_records = []
    
    for feature in features:
        props = feature['properties']
        for time_field in ['arrival', 'departure']:
            time_val = props.get(time_field)
            if time_val and time_val != '':
                try:
                    parts = time_val.split(':')
                    if len(parts) != 3:
                        invalid_records.append({
                            'train_number': props['number'],
                            'train_name': props['name'],
                            'field': time_field,
                            'value': time_val
                        })
                    else:
                        h, m, s = parts
                        if not (h.isdigit() and m.isdigit() and s.isdigit()):
                            invalid_records.append({
                                'train_number': props['number'],
                                'train_name': props['name'],
                                'field': time_field,
                                'value': time_val
                            })
                except:
                    invalid_records.append({
                        'train_number': props['number'],
                        'train_name': props['name'],
                        'field': time_field,
                        'value': time_val
                    })
    
    return invalid_records

if __name__ == '__main__':
    base_path = os.path.join(os.path.dirname(__file__), 'data', 'processed')
    invalid = find_invalid_times(os.path.join(base_path, 'trains_cleaned.json'))
    
    print(f"Found {len(invalid)} invalid time records:")
    for i, record in enumerate(invalid[:10], 1):
        print(f"{i}. Train {record['train_number']} ({record['train_name']}) - {record['field']}: {record['value']}")
