import json
import os
from datetime import datetime

def clean_stations(input_path, output_path):
    """Clean stations data"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    cleaned_features = []
    removed_count = 0
    
    for feature in features:
        # Remove stations with null geometry
        if feature['geometry'] is None:
            removed_count += 1
            continue
        
        # Keep stations with valid geometry
        cleaned_features.append(feature)
    
    cleaned_data = {
        "type": "FeatureCollection",
        "features": cleaned_features
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    return {
        'original_count': len(features),
        'cleaned_count': len(cleaned_features),
        'removed_count': removed_count
    }

def clean_trains(input_path, output_path):
    """Clean trains data"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data['features']
    cleaned_features = []
    fixed_time_count = 0
    
    for feature in features:
        props = feature['properties']
        
        # Fix time formats
        for time_field in ['arrival', 'departure']:
            time_val = props.get(time_field)
            if time_val is None or time_val == '' or time_val == 'None':
                # Convert null/empty/"None" string to empty string
                props[time_field] = ""
                fixed_time_count += 1
            elif time_val and time_val != '':
                # Ensure proper HH:MM:SS format
                parts = time_val.split(':')
                if len(parts) == 2:
                    # Add seconds if missing
                    props[time_field] = f"{time_val}:00"
                    fixed_time_count += 1
                elif len(parts) == 3:
                    # Pad hours/minutes/seconds if needed
                    h, m, s = parts
                    props[time_field] = f"{h.zfill(2)}:{m.zfill(2)}:{s.zfill(2)}"
                    if len(h) < 2 or len(m) < 2 or len(s) < 2:
                        fixed_time_count += 1
        
        # Handle missing return_train - set to empty string if None
        if props.get('return_train') is None:
            props['return_train'] = ""
        
        # Handle missing numeric fields - set to 0 if None
        for field in ['duration_m', 'duration_h', 'distance']:
            if props.get(field) is None:
                props[field] = 0
        
        # Handle missing classes - set to empty string
        if props.get('classes') is None:
            props['classes'] = ""
        
        cleaned_features.append(feature)
    
    cleaned_data = {
        "type": "FeatureCollection",
        "features": cleaned_features
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    return {
        'original_count': len(features),
        'cleaned_count': len(cleaned_features),
        'fixed_time_count': fixed_time_count
    }

def clean_schedules(input_path, output_path):
    """Clean schedules data"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cleaned_records = []
    fixed_none_count = 0
    fixed_day_count = 0
    
    for record in data:
        # Handle "None" string values - convert to None
        for key, value in record.items():
            if value == 'None':
                record[key] = None
                fixed_none_count += 1
        
        # Fix invalid day values
        day = record.get('day')
        if day is not None:
            try:
                day_int = int(day)
                if day_int < 1 or day_int > 7:
                    record['day'] = None
                    fixed_day_count += 1
                else:
                    record['day'] = day_int
            except (ValueError, TypeError):
                record['day'] = None
                fixed_day_count += 1
        
        cleaned_records.append(record)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_records, f, ensure_ascii=False, indent=2)
    
    return {
        'original_count': len(data),
        'cleaned_count': len(cleaned_records),
        'fixed_none_count': fixed_none_count,
        'fixed_day_count': fixed_day_count
    }

if __name__ == '__main__':
    base_path = os.path.join(os.path.dirname(__file__), 'data', 'raw', 'datameet_railways')
    output_path = os.path.join(os.path.dirname(__file__), 'data', 'processed')
    
    print("=" * 60)
    print("CLEANING STATIONS DATA")
    print("=" * 60)
    stations_result = clean_stations(
        os.path.join(base_path, 'stations.json'),
        os.path.join(output_path, 'stations_cleaned.json')
    )
    print(f"Original records: {stations_result['original_count']}")
    print(f"Cleaned records: {stations_result['cleaned_count']}")
    print(f"Removed (null geometry): {stations_result['removed_count']}")
    
    print("\n" + "=" * 60)
    print("CLEANING TRAINS DATA")
    print("=" * 60)
    trains_result = clean_trains(
        os.path.join(base_path, 'trains.json'),
        os.path.join(output_path, 'trains_cleaned.json')
    )
    print(f"Original records: {trains_result['original_count']}")
    print(f"Cleaned records: {trains_result['cleaned_count']}")
    print(f"Fixed time formats: {trains_result['fixed_time_count']}")
    
    print("\n" + "=" * 60)
    print("CLEANING SCHEDULES DATA")
    print("=" * 60)
    schedules_result = clean_schedules(
        os.path.join(base_path, 'schedules.json'),
        os.path.join(output_path, 'schedules_cleaned.json')
    )
    print(f"Original records: {schedules_result['original_count']}")
    print(f"Cleaned records: {schedules_result['cleaned_count']}")
    print(f"Fixed 'None' strings: {schedules_result['fixed_none_count']}")
    print(f"Fixed invalid day values: {schedules_result['fixed_day_count']}")
    
    print("\n" + "=" * 60)
    print("CLEANING COMPLETE")
    print(f"Cleaned files saved to: {output_path}")
    print("=" * 60)
