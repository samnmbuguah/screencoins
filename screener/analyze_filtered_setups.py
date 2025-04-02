import json
from datetime import datetime
from collections import defaultdict, Counter

def main():
    # Input file
    input_file = "results/filtered_setups_march_28_29.json"
    
    # Load the JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Get the filtered setups
    setups = data['setups']
    
    # Group setups by date
    setups_by_date = defaultdict(list)
    for setup in setups:
        timestamp_str = setup['fvg_5m']['timestamp']
        timestamp = datetime.fromisoformat(timestamp_str.replace('+00:00', ''))
        date_str = timestamp.strftime('%Y-%m-%d')
        setups_by_date[date_str].append(setup)
    
    # Get coin counts
    coin_counter = Counter([setup['symbol'] for setup in setups])
    
    # Get setup type counts
    type_counter = Counter([setup['type'] for setup in setups])
    
    # Get 1H FVG dates
    h1_fvg_dates = defaultdict(int)
    for setup in setups:
        timestamp_str = setup['fvg_1h']['timestamp']
        timestamp = datetime.fromisoformat(timestamp_str.replace('+00:00', ''))
        date_str = timestamp.strftime('%Y-%m-%d')
        h1_fvg_dates[date_str] += 1
    
    # Print summary
    print("\n===== FILTERED SETUPS SUMMARY =====")
    print(f"Total setups: {len(setups)}")
    print("\n=== Setups by 5M FVG Date ===")
    for date, date_setups in sorted(setups_by_date.items()):
        print(f"{date}: {len(date_setups)} setups")
    
    print("\n=== Setups by Coin ===")
    for coin, count in coin_counter.most_common():
        print(f"{coin}: {count} setups")
    
    print("\n=== Setups by Type ===")
    for type_name, count in type_counter.most_common():
        print(f"{type_name.upper()}: {count} setups")
    
    print("\n=== 1H FVG Formation Dates ===")
    for date, count in sorted(h1_fvg_dates.items()):
        print(f"{date}: {count} setups used 1H FVGs from this date")
    
    print("\n=== Sample Setups From Each Day ===")
    for date, date_setups in sorted(setups_by_date.items()):
        print(f"\n--- {date} ---")
        # Show just one example setup from each date
        setup = date_setups[0]
        print(f"Symbol: {setup['symbol']}")
        print(f"Type: {setup['type'].upper()}")
        print(f"Current Price: {setup['current_price']}")
        print(f"1H FVG: {setup['fvg_1h']['high']} - {setup['fvg_1h']['low']} ({setup['fvg_1h']['timestamp']})")
        print(f"5M FVG: {setup['fvg_5m']['high']} - {setup['fvg_5m']['low']} ({setup['fvg_5m']['timestamp']})")
        print(f"Stop Loss: {setup['stop_loss']}")

if __name__ == "__main__":
    main() 