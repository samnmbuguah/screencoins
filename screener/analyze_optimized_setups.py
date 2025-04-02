import json
from datetime import datetime
from collections import defaultdict, Counter

def main():
    # Input files
    optimized_file = "results/optimized_coin_setups_20250329_121303.json"
    previous_file = "results/filtered_setups_march_28_29.json"
    
    # Load the JSON data
    with open(optimized_file, 'r') as f:
        optimized_data = json.load(f)
    
    with open(previous_file, 'r') as f:
        previous_data = json.load(f)
    
    # Get the setups
    optimized_setups = optimized_data['setups']
    previous_setups = previous_data['setups']
    
    # Group setups by date
    opt_by_date = defaultdict(list)
    for setup in optimized_setups:
        timestamp_str = setup['fvg_5m']['timestamp']
        timestamp = datetime.fromisoformat(timestamp_str.replace('+00:00', ''))
        date_str = timestamp.strftime('%Y-%m-%d')
        opt_by_date[date_str].append(setup)
    
    prev_by_date = defaultdict(list)
    for setup in previous_setups:
        timestamp_str = setup['fvg_5m']['timestamp']
        timestamp = datetime.fromisoformat(timestamp_str.replace('+00:00', ''))
        date_str = timestamp.strftime('%Y-%m-%d')
        prev_by_date[date_str].append(setup)
    
    # Get coin and type stats
    opt_coins = Counter([setup['symbol'] for setup in optimized_setups])
    prev_coins = Counter([setup['symbol'] for setup in previous_setups])
    
    opt_types = Counter([setup['type'] for setup in optimized_setups])
    prev_types = Counter([setup['type'] for setup in previous_setups])
    
    # Print comparison
    print("\n===== COMPARISON OF SETUPS =====")
    print(f"Previous total setups: {len(previous_setups)}")
    print(f"Optimized total setups: {len(optimized_setups)}")
    print(f"Difference: {len(optimized_setups) - len(previous_setups)} setups")
    
    if 'execution_time_seconds' in optimized_data:
        print(f"\nOptimized execution time: {optimized_data['execution_time_seconds']:.2f} seconds")
    
    print("\n=== Setups by Date ===")
    all_dates = sorted(set(list(opt_by_date.keys()) + list(prev_by_date.keys())))
    for date in all_dates:
        opt_count = len(opt_by_date.get(date, []))
        prev_count = len(prev_by_date.get(date, []))
        print(f"{date}: Previous: {prev_count}, Optimized: {opt_count}, Diff: {opt_count - prev_count}")
    
    print("\n=== Setups by Coin ===")
    all_coins = sorted(set(list(opt_coins.keys()) + list(prev_coins.keys())))
    for coin in all_coins:
        opt_count = opt_coins.get(coin, 0)
        prev_count = prev_coins.get(coin, 0)
        print(f"{coin}: Previous: {prev_count}, Optimized: {opt_count}, Diff: {opt_count - prev_count}")
    
    print("\n=== Setups by Type ===")
    all_types = sorted(set(list(opt_types.keys()) + list(prev_types.keys())))
    for type_name in all_types:
        opt_count = opt_types.get(type_name, 0)
        prev_count = prev_types.get(type_name, 0)
        print(f"{type_name.upper()}: Previous: {prev_count}, Optimized: {opt_count}, Diff: {opt_count - prev_count}")
    
    print("\n=== Example Optimized Setup ===")
    if optimized_setups:
        setup = optimized_setups[0]
        print(f"Symbol: {setup['symbol']}")
        print(f"Type: {setup['type'].upper()}")
        print(f"Current Price: {setup['current_price']}")
        print(f"1H FVG: {setup['fvg_1h']['high']} - {setup['fvg_1h']['low']} ({setup['fvg_1h']['timestamp']})")
        print(f"5M FVG: {setup['fvg_5m']['high']} - {setup['fvg_5m']['low']} ({setup['fvg_5m']['timestamp']})")
        
        # Calculate gap size for both FVGs
        h1_gap_size = abs(float(setup['fvg_1h']['high']) - float(setup['fvg_1h']['low'])) / float(setup['fvg_1h']['low']) * 100
        m5_gap_size = abs(float(setup['fvg_5m']['high']) - float(setup['fvg_5m']['low'])) / float(setup['fvg_5m']['low']) * 100
        
        print(f"1H FVG Gap Size: {h1_gap_size:.2f}%")
        print(f"5M FVG Gap Size: {m5_gap_size:.2f}%")
        
        # Check alignment
        if setup['type'] == 'bullish':
            alignment = abs(float(setup['fvg_5m']['high']) - float(setup['fvg_1h']['high'])) / float(setup['fvg_1h']['high']) * 100
            print(f"5M High to 1H High alignment: {alignment:.4f}%")
        else:
            alignment = abs(float(setup['fvg_5m']['low']) - float(setup['fvg_1h']['low'])) / float(setup['fvg_1h']['low']) * 100
            print(f"5M Low to 1H Low alignment: {alignment:.4f}%")

if __name__ == "__main__":
    main() 