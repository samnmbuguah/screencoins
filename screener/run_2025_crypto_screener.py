import ccxt
import os
import json
from datetime import datetime, timezone, timedelta
from utils import find_fvg_setups, process_symbol, get_ohlcv_data
import time
from concurrent.futures import ProcessPoolExecutor
import pandas as pd

# Minimum gap percentage thresholds
MIN_1H_GAP_PERCENT = 0.4
MIN_5M_GAP_PERCENT = 0.1

def custom_process_symbol(data):
    """Modified process_symbol function that uses different date ranges for 1H and 5M timeframes."""
    symbol, exchange, market_type, start_of_2025, start_date_5m, end_date_5m = data
    fvg_setups = []
    
    try:
        # Get current price
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker["last"]
        
        # Skip symbols with price too low (often have lower liquidity)
        if current_price < 0.000001:
            return []

        # Fetch 1H data from beginning of 2025
        since_1h = int(start_of_2025.timestamp() * 1000)
        df_1h = get_ohlcv_data(exchange, symbol, "1h", since_1h)
        if df_1h is None or len(df_1h) < 3:  # Need at least 3 candles for FVG
            print(f"No 1H data for {symbol} since beginning of 2025")
            return []
        
        # Find 1H FVGs using the PineScript logic
        fvg_1h_list = []
        for i in range(2, len(df_1h)):  # Start at i=2 to access i, i-1, i-2
            # Get candle data
            current_candle = df_1h.iloc[i]      # Current candle (i)
            prev_candle = df_1h.iloc[i-1]       # Previous candle (i-1)
            prev2_candle = df_1h.iloc[i-2]      # Two candles back (i-2)
            
            # Check if previous candle is bearish or bullish
            is_prev_bearish = prev_candle["Open"] > prev_candle["Close"]
            
            # Bullish FVG: check if current high < low of 2 candles ago
            if not is_prev_bearish and current_candle["Low"] > prev2_candle["High"]:
                # This is a bullish FVG - gap between current high and prev2 low
                gap_size = current_candle["Low"] - prev2_candle["High"]
                gap_percent = (gap_size / prev_candle["Close"]) * 100
                
                # Only include FVGs with gap >= MIN_1H_GAP_PERCENT
                if gap_percent >= MIN_1H_GAP_PERCENT:
                    fvg_1h_list.append({
                        "type": "bullish",
                        "upper_line": current_candle["Low"],    # Upper boundary of the gap
                        "lower_line": prev2_candle["High"], # Lower boundary of the gap 
                        "middle_candle_high": prev_candle["High"],  # Store middle candle info
                        "middle_candle_low": prev_candle["Low"],
                        "timestamp": df_1h.index[i-1],        # Gap occurs at the middle candle (i-1)
                        "gap_percent": gap_percent
                    })
            
            # Bearish FVG: check if current low > high of 2 candles ago
            if is_prev_bearish and current_candle["High"] < prev2_candle["Low"]:
                # This is a bearish FVG - gap between current low and prev2 high
                gap_size = prev2_candle["Low"] - current_candle["High"]
                gap_percent = (gap_size / prev_candle["Close"]) * 100
                
                # Only include FVGs with gap >= MIN_1H_GAP_PERCENT
                if gap_percent >= MIN_1H_GAP_PERCENT:
                    fvg_1h_list.append({
                        "type": "bearish",
                        "upper_line": prev2_candle["Low"],   # Upper boundary of the gap
                        "lower_line": current_candle["High"],    # Lower boundary of the gap
                        "middle_candle_high": prev_candle["High"],  # Store middle candle info
                        "middle_candle_low": prev_candle["Low"],
                        "timestamp": df_1h.index[i-1],         # Gap occurs at the middle candle (i-1)
                        "gap_percent": gap_percent
                    })

        # If no 1H FVGs found, return empty list
        if not fvg_1h_list:
            print(f"No 1H FVGs found for {symbol}")
            return []

        # Fetch 5M data from March 24-31, 2025 only
        since_5m = int(start_date_5m.timestamp() * 1000)
        df_5m = get_ohlcv_data(exchange, symbol, "5m", since_5m)
        if df_5m is None or len(df_5m) < 3:  # Need at least 3 candles for FVG
            print(f"No 5M data for {symbol} for the specified period")
            return []
            
        # Filter 5M data to only include the date range we want
        end_timestamp = int(end_date_5m.timestamp() * 1000)
        df_5m = df_5m[df_5m.index < pd.Timestamp(end_timestamp, unit='ms', tz='UTC')]
        
        if len(df_5m) < 3:
            print(f"Insufficient 5M data for {symbol} in the specified period after filtering")
            return []

        # Check for interactions with any 1H FVG, regardless of when it formed
        for fvg_1h in fvg_1h_list:
            # Process all 5M candles
            for i in range(2, len(df_5m) - 1):  # Start at 2 to access i, i-1, i-2
                # Get candle data for 5M
                current_candle_5m = df_5m.iloc[i]     # Current candle (i)
                prev_candle_5m = df_5m.iloc[i-1]      # Previous candle (i-1)
                prev2_candle_5m = df_5m.iloc[i-2]     # Two candles back (i-2)
                
                # Check if previous candle is bearish or bullish
                is_prev_bearish_5m = prev_candle_5m["Open"] > prev_candle_5m["Close"]
                
                # Check for BULLISH 5M FVG using the same PineScript logic
                if not is_prev_bearish_5m and current_candle_5m["Low"] > prev2_candle_5m["High"]:
                    # This is a bullish 5M FVG
                    bullish_gap = current_candle_5m["Low"] - prev2_candle_5m["High"]
                    bullish_gap_percent = (bullish_gap / prev_candle_5m["Close"]) * 100
                    
                    # Only include FVGs with gap >= MIN_5M_GAP_PERCENT
                    if bullish_gap_percent >= MIN_5M_GAP_PERCENT:
                        # For bullish setup, check if the 1H FVG's upper line is within the 5M FVG range
                        line_in_range = prev2_candle_5m["High"] <= fvg_1h["upper_line"] <= current_candle_5m["Low"]
                        
                        if line_in_range:
                            fvg_setups.append({
                                "symbol": symbol,
                                "type": "bullish",
                                "current_price": current_price,
                                "fvg_1h": {
                                    "type": fvg_1h["type"],
                                    "upper_line": fvg_1h["upper_line"],
                                    "lower_line": fvg_1h["lower_line"],
                                    "timestamp": fvg_1h["timestamp"],
                                    "gap_percent": fvg_1h["gap_percent"]
                                },
                                "fvg_5m": {
                                    "upper_line": current_candle_5m["Low"],    # Upper boundary of gap
                                    "lower_line": prev2_candle_5m["High"], # Lower boundary of gap
                                    "middle_candle_high": prev_candle_5m["High"],  # Middle candle info
                                    "middle_candle_low": prev_candle_5m["Low"],
                                    "gap_size": bullish_gap,
                                    "gap_percent": bullish_gap_percent,
                                    "timestamp": df_5m.index[i-1]       # Gap occurs at middle candle (i-1)
                                },
                                "stop_loss": prev_candle_5m["Low"],     # Using middle candle low as stop
                                "risk_reward": 2,                        # Default to 2R
                                "alignment_type": "upper"               # For bullish setups, we align on upper line
                            })
                
                # Check for BEARISH 5M FVG using the same PineScript logic
                if is_prev_bearish_5m and current_candle_5m["High"] < prev2_candle_5m["Low"]:
                    # This is a bearish 5M FVG
                    bearish_gap = prev2_candle_5m["Low"] - current_candle_5m["High"]
                    bearish_gap_percent = (bearish_gap / prev_candle_5m["Close"]) * 100
                    
                    # Only include FVGs with gap >= MIN_5M_GAP_PERCENT
                    if bearish_gap_percent >= MIN_5M_GAP_PERCENT:
                        # For bearish setup, check if the 1H FVG's lower line is within the 5M FVG range
                        line_in_range = current_candle_5m["High"] <= fvg_1h["lower_line"] <= prev2_candle_5m["Low"]
                        
                        if line_in_range:
                            fvg_setups.append({
                                "symbol": symbol,
                                "type": "bearish",
                                "current_price": current_price,
                                "fvg_1h": {
                                    "type": fvg_1h["type"],
                                    "upper_line": fvg_1h["upper_line"],
                                    "lower_line": fvg_1h["lower_line"],
                                    "timestamp": fvg_1h["timestamp"],
                                    "gap_percent": fvg_1h["gap_percent"]
                                },
                                "fvg_5m": {
                                    "upper_line": prev2_candle_5m["Low"],  # Upper boundary of gap
                                    "lower_line": current_candle_5m["High"],   # Lower boundary of gap
                                    "middle_candle_high": prev_candle_5m["High"],  # Middle candle info
                                    "middle_candle_low": prev_candle_5m["Low"],
                                    "gap_size": bearish_gap,
                                    "gap_percent": bearish_gap_percent,
                                    "timestamp": df_5m.index[i-1]       # Gap occurs at middle candle (i-1)
                                },
                                "stop_loss": prev_candle_5m["High"],    # Using middle candle high as stop
                                "risk_reward": 2,                        # Default to 2R
                                "alignment_type": "lower"               # For bearish setups, we align on lower line
                            })
        
        return fvg_setups
    
    except Exception as e:
        print(f"\rProcessing symbol {symbol} - Error: {str(e)}", end="")
        return []

def main():
    print("Initializing FVG Screener for Major Crypto Pairs (BTC, ETH, SOL, XRP) - Last Week Analysis")
    
    # List of specific coins to analyze
    specific_symbols = [
        "BTC/USDT",
        "XRP/USDT"
    ]
        
    print(f"Will analyze the following {len(specific_symbols)} coins: {', '.join(specific_symbols)}")
    print(f"Using minimum gap thresholds: 1H >= {MIN_1H_GAP_PERCENT}%, 5M >= {MIN_5M_GAP_PERCENT}%")

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
    
    # Define the beginning of 2025 for 1H FVGs analysis period
    start_of_2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    
    # Define March 24, 2025 as the start date for 5M analysis
    start_date_5m = datetime(2025, 3, 24, tzinfo=timezone.utc)
    # Define end date (start date + 1 week)
    end_date_5m = start_date_5m + timedelta(days=7)
    
    print(f"Analyzing 1H FVGs from {start_of_2025.isoformat()} to now")
    print(f"Finding 5M setups only for one week from {start_date_5m.isoformat()} to {end_date_5m.isoformat()}")
    print(f"Using PineScript FVG definition: non-overlapping candles")
    print(f"Bullish FVG: For bearish previous candle, current high < low of 2 candles ago")
    print(f"Bearish FVG: For bullish previous candle, current low > high of 2 candles ago")
    
    # Process symbols with custom date range
    total_symbols = len(specific_symbols)
    print(f"\nProcessing {total_symbols} symbols using parallel processing...")
    
    # Setup for parallel processing
    max_workers = min(os.cpu_count(), 4)  # Use up to 4 CPU cores
    
    # Prepare data for parallel processing with the different date ranges
    symbol_data = [(symbol, exchange, "futures", start_of_2025, start_date_5m, end_date_5m) for symbol in specific_symbols]
    
    all_setups = []
    
    # Process symbols using our custom function
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(custom_process_symbol, symbol_data))
    
    # Flatten results
    all_setups = [setup for symbol_setups in results for setup in symbol_setups]
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Create results directory if it doesn't exist
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    # Generate timestamp for filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_filename = os.path.join(results_dir, f"crypto_gap_filter_{timestamp}.json")

    # Save results to JSON file
    with open(json_filename, 'w') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "coins_analyzed": specific_symbols,
            "analysis_periods": {
                "1h_fvgs": f"From {start_of_2025.isoformat()} to present",
                "5m_setups": f"One week period ({start_date_5m.isoformat()} to {end_date_5m.isoformat()})"
            },
            "fvg_logic": {
                "bullish": "For bearish previous candle, current high < low of 2 candles ago",
                "bearish": "For bullish previous candle, current low > high of 2 candles ago"
            },
            "min_gap_thresholds": {
                "1h": MIN_1H_GAP_PERCENT,
                "5m": MIN_5M_GAP_PERCENT
            },
            "execution_time_seconds": execution_time,
            "total_setups": len(all_setups),
            "setups": all_setups
        }, f, indent=2, default=str)

    # Count setups by symbol
    setups_by_symbol = {}
    for setup in all_setups:
        symbol = setup['symbol']
        if symbol not in setups_by_symbol:
            setups_by_symbol[symbol] = {"bullish": 0, "bearish": 0}
        setups_by_symbol[symbol][setup['type']] += 1
    
    # Organize results by symbol and type
    results_by_symbol_type = {}
    for setup in all_setups:
        symbol = setup['symbol']
        setup_type = setup['type']
        key = f"{symbol}_{setup_type}"
        if key not in results_by_symbol_type:
            results_by_symbol_type[key] = []
        results_by_symbol_type[key].append(setup)
    
    # Print summary of results by symbol
    print(f"\nExecution time: {execution_time:.2f} seconds")
    print(f"Total setups found: {len(all_setups)}")
    print("\n=== Summary By Symbol ===")
    for symbol in specific_symbols:
        if symbol in setups_by_symbol:
            bull_count = setups_by_symbol[symbol]["bullish"]
            bear_count = setups_by_symbol[symbol]["bearish"]
            print(f"{symbol}: {bull_count + bear_count} setups ({bull_count} bullish, {bear_count} bearish)")
        else:
            print(f"{symbol}: No setups found")
    
    print("\n=== Detailed FVG Setups ===")
    if all_setups:
        for key in results_by_symbol_type:
            symbol, setup_type = key.split('_')
            setups = results_by_symbol_type[key]
            print(f"\n{symbol}: Found {len(setups)} {setup_type.upper()} setups")
            for i, setup in enumerate(setups[:3], 1):  # Show max 3 setups per symbol/type
                print(f"  {i}. {setup_type.upper()} setup")
                print(f"     1H FVG: Upper {setup['fvg_1h']['upper_line']:.8f} - Lower {setup['fvg_1h']['lower_line']:.8f} (Gap: {setup['fvg_1h'].get('gap_percent', 0):.2f}%)")
                print(f"     5M FVG: Upper {setup['fvg_5m']['upper_line']:.8f} - Lower {setup['fvg_5m']['lower_line']:.8f} (Gap: {setup['fvg_5m'].get('gap_percent', 0):.2f}%)")
                print(f"     Current Price: {setup['current_price']:.8f}, Stop: {setup['stop_loss']:.8f}")
            if len(setups) > 3:
                print(f"     ... and {len(setups) - 3} more {setup_type} setups")
    else:
        print("No FVG setups found for the major crypto pairs in the specified period.")

    print(f"\nResults saved to: {json_filename}")

if __name__ == "__main__":
    main() 