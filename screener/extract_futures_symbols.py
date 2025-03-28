import ccxt
import json
import os
from datetime import datetime, timezone

def extract_futures_symbols():
    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })

    # Load markets
    print("Loading markets...")
    try:
        # Get futures tickers directly
        tickers = exchange.fapiPublicGetTickerPrice()
        valid_futures = [ticker['symbol'].replace('USDT', '/USDT') for ticker in tickers]
        
        # Sort symbols alphabetically
        valid_futures.sort()
        
        # Create results directory if it doesn't exist
        results_dir = "results"
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        # Save to file
        output_file = os.path.join(results_dir, "valid_futures_symbols.json")
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_symbols": len(valid_futures),
                "symbols": valid_futures
            }, f, indent=2)
        
        print(f"\nFound {len(valid_futures)} valid futures symbols")
        print(f"Results saved to: {output_file}")
        
        # Print first few symbols as example
        if valid_futures:
            print("\nExample symbols:")
            for symbol in valid_futures[:5]:
                print(f"- {symbol}")
        
        return valid_futures
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

if __name__ == "__main__":
    extract_futures_symbols() 