import ccxt
import os
import json
from datetime import datetime, timezone
from utils import find_fvg_setups

def load_valid_futures_symbols():
    """Load valid futures symbols from the JSON file."""
    results_dir = "results"
    symbols_file = os.path.join(results_dir, "valid_futures_symbols.json")
    
    if not os.path.exists(symbols_file):
        print("Valid futures symbols file not found. Please run extract_futures_symbols.py first.")
        return None
        
    with open(symbols_file, 'r') as f:
        data = json.load(f)
        return data['symbols']

def main():
    print("Initializing FVG Screener...")
    
    # Load valid futures symbols
    valid_symbols = load_valid_futures_symbols()
    if valid_symbols is None:
        return
        
    print(f"Loaded {len(valid_symbols)} valid futures symbols")

    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })

    # Find FVG setups
    fvg_setups = find_fvg_setups(exchange, valid_symbols, "futures")

    # Create results directory if it doesn't exist
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    # Generate timestamp for filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_filename = os.path.join(results_dir, f"fvg_setups_{timestamp}.json")

    # Save results to JSON file
    with open(json_filename, 'w') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_symbols": len(valid_symbols),
            "setups": fvg_setups
        }, f, indent=2, default=str)

    # Print results
    print("\n=== FVG Setups ===")
    if fvg_setups:
        for setup in fvg_setups:
            print(f"\nSymbol: {setup['symbol']}")
            print(f"Type: {setup['type'].upper()}")
            print(f"Current Price: {setup['current_price']:.8f}")
            print(f"1H FVG High: {setup['fvg_1h']['high']:.8f}")
            print(f"1H FVG Low: {setup['fvg_1h']['low']:.8f}")
            print(f"5M FVG High: {setup['fvg_5m']['high']:.8f}")
            print(f"5M FVG Low: {setup['fvg_5m']['low']:.8f}")
            print(f"Stop Loss: {setup['stop_loss']:.8f}")
            print(f"Risk/Reward: {setup['risk_reward']}R")
    else:
        print("No FVG setups found.")

    print(f"\nResults saved to: {json_filename}")

if __name__ == "__main__":
    main() 