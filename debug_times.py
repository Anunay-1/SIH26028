import json
import os

def debug_times(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    invalid_samples = []
    
    for feature in features:
        props = feature['properties']
        for time_field in ['arrival', 'departure']:
            time_val = props.get(time_field)
            if time_val and time_val != '':
                try:
                    parts = time_val.split(':')
                    if len(parts) != 3:
                        invalid_samples.append({
                            'train': props['number'],
                            'field': time_field,
                            'value': time_val,
                            'reason': 'not 3 parts'
                        })
                    else:
                        h, m, s = parts
                        if not (h.isdigit() and m.isdigit() and s.isdigit()):
                            invalid_samples.append({
                                'train': props['number'],
                                'field': time_field,
                                'value': time_val,
                                'reason': 'non-digit parts',
                                'h': h,
                                'm': m,
                                's': s
                            })
                except Exception as e:
                    invalid_samples.append({
                        'train': props['number'],
                        'field': time_field,
                        'value': time_val,
                        'reason': f'exception: {e}'
                    })
    
    return invalid_samples

if __name__ == '__main__':
    base_path = os.path.join(os.path.dirname(__file__), 'data', 'processed')
    invalid = debug_times(os.path.join(base_path, 'trains_cleaned.json'))
    
    print(f"Found {len(invalid)} invalid time samples:")
    for i, sample in enumerate(invalid[:10], 1):
        print(f"{i}. {sample}")
