import json
import os
from datetime import datetime
import pytz

def main():
    # Input file
    input_file = "results/specific_coins_fvg_setups_20250329_111203.json"
    
    # Load the JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Get the original setups
    original_setups = data['setups']
    
    # Filter for setups where the 5M FVG timestamp is from March 28 or 29, 2025
    filtered_setups = []
    
    for setup in original_setups:
        # Parse the timestamp string to a datetime object
        timestamp_str = setup['fvg_5m']['timestamp']
        timestamp = datetime.fromisoformat(timestamp_str.replace('+00:00', ''))
        
        # Add timezone info if missing
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=pytz.UTC)
        
        # Check if the date is March 28 or 29, 2025
        if timestamp.year == 2025 and timestamp.month == 3 and timestamp.day in [28, 29]:
            filtered_setups.append(setup)
    
    # Create a new data structure with the filtered setups
    filtered_data = {
        "timestamp": datetime.now().isoformat(),
        "coins_analyzed": data['coins_analyzed'],
        "setups": filtered_setups,
        "total_filtered_setups": len(filtered_setups),
        "filter_criteria": "5M FVG timestamps from March 28-29, 2025"
    }
    
    # Generate output filename
    output_file = "results/filtered_setups_march_28_29.json"
    
    # Save filtered results to a new JSON file
    with open(output_file, 'w') as f:
        json.dump(filtered_data, f, indent=2, default=str)
    
    # Print summary
    print(f"Total setups in original file: {len(original_setups)}")
    print(f"Total setups after filtering: {len(filtered_setups)}")
    print(f"Filtered results saved to: {output_file}")
    
    # Print first few filtered setups for verification
    if filtered_setups:
        print("\n=== Recent Setups (March 28-29, 2025) ===")
        for i, setup in enumerate(filtered_setups[:5]):  # Show first 5 setups only
            print(f"\nSetup {i+1}:")
            print(f"Symbol: {setup['symbol']}")
            print(f"Type: {setup['type'].upper()}")
            print(f"5M FVG Timestamp: {setup['fvg_5m']['timestamp']}")
            print(f"Current Price: {setup['current_price']}")
        
        if len(filtered_setups) > 5:
            print(f"\n... and {len(filtered_setups) - 5} more setups.")

if __name__ == "__main__":
    main() 