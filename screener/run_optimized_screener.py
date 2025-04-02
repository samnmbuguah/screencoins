import ccxt
import os
import json
from datetime import datetime, timezone
from utils import find_fvg_setups
import time

def main():
    print("Initializing Optimized FVG Screener for Specific Coins...")
    
    # List of specific coins to analyze
    specific_symbols = [
        "JELLYJELLY/USDT",
        "MAVIA/USDT",
        "PAXG/USDT",
        "WAL/USDT"
    ]
        
    print(f"Will analyze the following {len(specific_symbols)} coins: {', '.join(specific_symbols)}")

    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })

    # Track execution time
    start_time = time.time()
    
    # Find FVG setups using optimized method
    fvg_setups = find_fvg_setups(exchange, specific_symbols, "futures")
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Create results directory if it doesn't exist
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    # Generate timestamp for filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_filename = os.path.join(results_dir, f"optimized_coin_setups_{timestamp}.json")

    # Save results to JSON file
    with open(json_filename, 'w') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "coins_analyzed": specific_symbols,
            "execution_time_seconds": execution_time,
            "total_setups": len(fvg_setups),
            "setups": fvg_setups
        }, f, indent=2, default=str)

    # Print results
    print(f"\nExecution time: {execution_time:.2f} seconds")
    print(f"Total setups found: {len(fvg_setups)}")
    
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
        print("No FVG setups found for the specified coins.")

    print(f"\nResults saved to: {json_filename}")

if __name__ == "__main__":
    main() 