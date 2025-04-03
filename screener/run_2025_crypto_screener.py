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

def get_monthly_value_area(exchange, symbol, timestamp=None):
    """
    Get monthly Value Area for a symbol based on the month of the timestamp
    If timestamp is not provided, uses current date
    
    The Value Area will be the price range where 70% of the volume occurred
    For monthly data, we use a simple approximation based on the high/low range
    """
    try:
        # Use the month from the provided timestamp, or current date if None
        if timestamp is None:
            target_date = datetime.now(timezone.utc)
        else:
            # If timestamp is a string, convert to datetime
            if isinstance(timestamp, str):
                target_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                target_date = timestamp
                
        # Get the first day of the month that contains the target date
        first_day_of_month = datetime(target_date.year, target_date.month, 1, tzinfo=timezone.utc)
        
        # Get monthly data for that specific month
        since = int(first_day_of_month.timestamp() * 1000)
        
        # Try to get daily data for more accurate Value Area calculation
        daily_data = exchange.fetch_ohlcv(symbol, '1d', since=since, limit=31)  # Max 31 days in a month
        
        if not daily_data or len(daily_data) < 3:  # Need at least a few days for meaningful calculation
            # Fall back to monthly candle if daily data is insufficient
            monthly_data = exchange.fetch_ohlcv(symbol, '1M', since=since, limit=1)
            
            if not monthly_data:
                return None, None
            
            # Unpack the OHLCV data
            timestamp, open_price, high, low, close, volume = monthly_data[0]
            
            # Calculate the Value Area (70% of the price range)
            # For simplicity with monthly data, we'll use a value area that's 70% of the range centered at the middle
            mid_price = (high + low) / 2
            full_range = high - low
            va_range = full_range * 0.7  # 70% of the total range
            
            # The Value Area is centered around the mid price
            va_high = mid_price + (va_range / 2)
            va_low = mid_price - (va_range / 2)
            
            # Make sure Value Area stays within the month's high/low
            va_high = min(va_high, high)
            va_low = max(va_low, low)
            
            print(f"Monthly VA for {symbol} ({target_date.strftime('%Y-%m')}): H={high:.4f}, L={low:.4f}, VAH={va_high:.4f}, VAL={va_low:.4f}")
            
            return va_high, va_low
        
        # If we have daily data, use it for a more accurate Value Area calculation
        # Convert to DataFrame for easier manipulation
        df_daily = pd.DataFrame(daily_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_daily['timestamp'] = pd.to_datetime(df_daily['timestamp'], unit='ms')
        df_daily.set_index('timestamp', inplace=True)
        
        # Sort by volume (descending)
        df_daily_sorted = df_daily.sort_values(by='volume', ascending=False)
        
        # Calculate cumulative volume percentage
        total_volume = df_daily['volume'].sum()
        df_daily_sorted['vol_pct'] = df_daily_sorted['volume'].cumsum() / total_volume * 100
        
        # Select days that make up 70% of the total volume
        value_area_days = df_daily_sorted[df_daily_sorted['vol_pct'] <= 70]
        
        if len(value_area_days) < 1:
            # If no days match (shouldn't happen), include at least the highest volume day
            value_area_days = df_daily_sorted.iloc[:1]
        
        # Get high and low of the Value Area
        va_high = value_area_days['high'].max()
        va_low = value_area_days['low'].min()
        
        # Get overall month high and low for reference
        month_high = df_daily['high'].max()
        month_low = df_daily['low'].min()
        
        print(f"Daily-based VA for {symbol} ({target_date.strftime('%Y-%m')}): H={month_high:.4f}, L={month_low:.4f}, VAH={va_high:.4f}, VAL={va_low:.4f}")
        
        return va_high, va_low
        
    except Exception as e:
        print(f"Error getting monthly Value Area for {symbol}: {str(e)}")
        return None, None

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
                
                # Get monthly Value Area based on the 5M FVG's timestamp
                # This ensures we use the Value Area for the specific month of the 5M FVG
                timestamp_5m = df_5m.index[i-1]  # Use the middle candle timestamp (i-1)
                va_high, va_low = get_monthly_value_area(exchange, symbol, timestamp_5m)
                if va_high is None or va_low is None:
                    # Skip this candle if we couldn't get the Value Area
                    continue
                
                # Check if previous candle is bearish or bullish
                is_prev_bearish_5m = prev_candle_5m["Open"] > prev_candle_5m["Close"]
                
                # Check for BULLISH 5M FVG using the same PineScript logic
                if not is_prev_bearish_5m and current_candle_5m["Low"] > prev2_candle_5m["High"]:
                    # This is a bullish 5M FVG
                    bullish_gap = current_candle_5m["Low"] - prev2_candle_5m["High"]
                    bullish_gap_percent = (bullish_gap / prev_candle_5m["Close"]) * 100
                    
                    # Only include FVGs with gap >= MIN_5M_GAP_PERCENT and below Value Area Low
                    if bullish_gap_percent >= MIN_5M_GAP_PERCENT and current_candle_5m["Low"] < va_low:
                        # For bullish setup, check if the 1H FVG's LOWER line is within the 5M FVG range
                        line_in_range = prev2_candle_5m["High"] <= fvg_1h["lower_line"] <= current_candle_5m["Low"]
                        
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
                                "alignment_type": "lower",              # For bullish setups, we align on lower line
                                "va_high": va_high,                     # Add Value Area information
                                "va_low": va_low
                            })
                
                # Check for BEARISH 5M FVG using the same PineScript logic
                if is_prev_bearish_5m and current_candle_5m["High"] < prev2_candle_5m["Low"]:
                    # This is a bearish 5M FVG
                    bearish_gap = prev2_candle_5m["Low"] - current_candle_5m["High"]
                    bearish_gap_percent = (bearish_gap / prev_candle_5m["Close"]) * 100
                    
                    # Only include FVGs with gap >= MIN_5M_GAP_PERCENT and above Value Area High
                    if bearish_gap_percent >= MIN_5M_GAP_PERCENT and current_candle_5m["High"] > va_high:
                        # For bearish setup, check if the 1H FVG's UPPER line is within the 5M FVG range
                        line_in_range = current_candle_5m["High"] <= fvg_1h["upper_line"] <= prev2_candle_5m["Low"]
                        
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
                                "alignment_type": "upper",              # For bearish setups, we align on upper line
                                "va_high": va_high,                     # Add Value Area information
                                "va_low": va_low
                            })
        
        return fvg_setups
    
    except Exception as e:
        print(f"\rProcessing symbol {symbol} - Error: {str(e)}", end="")
        return []

def main():
    print("Initializing FVG Screener for All USDT Futures Pairs - Last Week Analysis")
    
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
    
    # Get list of pairs from the data folder
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(data_dir):
        print(f"Error: Data directory '{data_dir}' not found")
        return
        
    # Get all JSON files in the data directory
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    if not json_files:
        print(f"Error: No JSON files found in '{data_dir}' directory")
        return
        
    # Extract unique pairs from all JSON files
    usdt_futures = set()
    for json_file in json_files:
        try:
            with open(os.path.join(data_dir, json_file), 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            # Handle format like "BTC/USDT:USDT"
                            if item.endswith(':USDT'):
                                symbol = item.split(':')[0]  # Get the part before ':USDT'
                                if symbol.endswith('/USDT'):
                                    usdt_futures.add(symbol)
                        elif isinstance(item, dict) and 'symbol' in item:
                            symbol = item['symbol']
                            if symbol.endswith('/USDT'):
                                usdt_futures.add(symbol)
        except Exception as e:
            print(f"Error reading {json_file}: {str(e)}")
            continue
    
    # Convert set to sorted list for consistent output
    usdt_futures = sorted(list(usdt_futures))
    
    if not usdt_futures:
        print("Error: No USDT pairs found in the data files")
        return
        
    print(f"\nFound {len(usdt_futures)} USDT pairs to analyze")
    print("Pairs:", ', '.join(usdt_futures))
    print(f"Using minimum gap thresholds: 1H >= {MIN_1H_GAP_PERCENT}%, 5M >= {MIN_5M_GAP_PERCENT}%")
    
    # Process symbols with custom date range
    total_symbols = len(usdt_futures)
    print(f"\nProcessing {total_symbols} symbols using parallel processing...")
    
    # Setup for parallel processing
    max_workers = min(os.cpu_count(), 4)  # Use up to 4 CPU cores
    
    # Prepare data for parallel processing with the different date ranges
    symbol_data = [(symbol, exchange, "futures", start_of_2025, start_date_5m, end_date_5m) for symbol in usdt_futures]
    
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
            "coins_analyzed": usdt_futures,
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
    for symbol in usdt_futures:
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
                print(f"     Value Area: High {setup['va_high']:.8f}, Low {setup['va_low']:.8f}")
            if len(setups) > 3:
                print(f"     ... and {len(setups) - 3} more {setup_type} setups")
    else:
        print("No FVG setups found for any pairs in the specified period.")

    print(f"\nResults saved to: {json_filename}")

if __name__ == "__main__":
    main() 