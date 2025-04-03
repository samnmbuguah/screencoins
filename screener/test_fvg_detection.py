import ccxt
import pandas as pd
from datetime import datetime, timezone, timedelta
from utils import get_ohlcv_data, calculate_value_area
import json
import os
import numpy as np
# Since both MarketProfile and market-profile aren't working correctly,
# let's implement our own volume profile calculation

# Minimum gap percentage thresholds
MIN_1H_GAP_PERCENT = 0.4
MIN_5M_GAP_PERCENT = 0.1

def get_monthly_value_area(exchange, symbol, timestamp=None):
    """
    Get monthly Value Area for a symbol based on the month of the timestamp
    If timestamp is not provided, uses current date
    
    Uses the existing calculate_value_area function from utils.py
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
        
        # Get hourly data for the entire month for more precise Value Area calculation
        hourly_data = exchange.fetch_ohlcv(symbol, '1h', since=since, limit=744)  # Max 31 days (744 hours) in a month
        
        if not hourly_data or len(hourly_data) < 24:  # Need at least some data
            # Fall back to daily data if hourly is not available
            daily_data = exchange.fetch_ohlcv(symbol, '1d', since=since, limit=31)
            
            if not daily_data or len(daily_data) < 3:
                return None, None
                
            # Use daily data for the calculations below
            data = daily_data
        else:
            # Use hourly data for better accuracy
            data = hourly_data
            
        # Convert data to DataFrame
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Rename columns to match the calculate_value_area function expectation
        df = df.rename(columns={'close': 'Close', 'volume': 'Volume'})
        
        # Calculate Value Area using the utils function
        va_high, va_low = calculate_value_area(df, percentage=0.7, bins=100)
        
        return va_high, va_low
        
    except Exception as e:
        # Simplified fallback with minimal logging
        try:
            monthly_data = exchange.fetch_ohlcv(symbol, '1M', since=since, limit=1)
            if not monthly_data:
                return None, None
                
            timestamp, open_price, high, low, close, volume = monthly_data[0]
            
            # Calculate a simple Value Area (70% of the range around the middle)
            mid_price = (high + low) / 2
            full_range = high - low
            va_range = full_range * 0.7
            
            va_high = mid_price + (va_range / 2)
            va_low = mid_price - (va_range / 2)
            
            return va_high, va_low
            
        except Exception:
            return None, None

def test_1h_fvg_detection():
    """Test 1H FVG detection logic"""
    print("\n=== Testing 1H FVG Detection ===")
    print(f"Using minimum gap threshold: {MIN_1H_GAP_PERCENT}%")
    
    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })
    
    # Get BTC data for 1H timeframe from the beginning of last year
    symbol = "BTC/USDT"
    # Start from the beginning of last year (2024-01-01)
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    since = int(start_date.timestamp() * 1000)
    
    df_1h = get_ohlcv_data(exchange, symbol, "1h", since)
    if df_1h is None or len(df_1h) < 3:
        print("Failed to get 1H data")
        return []
    
    print(f"Loaded {len(df_1h)} 1H candles for {symbol} from {start_date.strftime('%Y-%m-%d')}")
    
    # Find 1H FVGs
    fvg_1h_list = []
    bullish_count, bearish_count = 0, 0
    
    for i in range(2, len(df_1h)):
        current_candle = df_1h.iloc[i]
        prev_candle = df_1h.iloc[i-1]
        prev2_candle = df_1h.iloc[i-2]
                
        is_prev_bearish = prev_candle["Open"] > prev_candle["Close"]
        
        # Bullish FVG
        if not is_prev_bearish and current_candle["Low"] > prev2_candle["High"]:
            gap_size = current_candle["Low"] - prev2_candle["High"]
            gap_percent = (gap_size / prev_candle["Close"]) * 100
            
            # Only include FVGs with gap >= MIN_1H_GAP_PERCENT
            if gap_percent >= MIN_1H_GAP_PERCENT:
                fvg_1h_list.append({
                    "type": "bullish",
                    "upper_line": current_candle["Low"],
                    "lower_line": prev2_candle["High"],
                    "timestamp": df_1h.index[i-1],
                    "gap_percent": gap_percent
                })
                bullish_count += 1
        
        # Bearish FVG
        if is_prev_bearish and current_candle["High"] < prev2_candle["Low"]:
            gap_size = prev2_candle["Low"] - current_candle["High"]
            gap_percent = (gap_size / prev_candle["Close"]) * 100
            
            # Only include FVGs with gap >= MIN_1H_GAP_PERCENT
            if gap_percent >= MIN_1H_GAP_PERCENT:
                fvg_1h_list.append({
                    "type": "bearish",
                    "upper_line": prev2_candle["Low"],
                    "lower_line": current_candle["High"],
                    "timestamp": df_1h.index[i-1],
                    "gap_percent": gap_percent
                })
                bearish_count += 1
    
    print(f"\nTotal 1H FVGs found: {len(fvg_1h_list)} (Bullish: {bullish_count}, Bearish: {bearish_count})")
    return fvg_1h_list

def test_5m_fvg_detection():
    """Test 5M FVG detection logic"""
    print("\n=== Testing 5M FVG Detection ===")
    print(f"Using minimum gap threshold: {MIN_5M_GAP_PERCENT}%")
    
    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })
    
    # Get BTC data for 5M timeframe for the past week from today
    symbol = "BTC/USDT"
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    
    print(f"Analyzing 5M data for {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    since = int(start_date.timestamp() * 1000)
    df_5m = get_ohlcv_data(exchange, symbol, "5m", since)
    
    if df_5m is None or len(df_5m) < 3:
        print("Failed to get 5M data")
        return []
    
    # Filter to specific date range
    end_timestamp = int(end_date.timestamp() * 1000)
    df_5m = df_5m[df_5m.index < pd.Timestamp(end_timestamp, unit='ms', tz='UTC')]
    
    print(f"Loaded {len(df_5m)} 5M candles for analysis")
    
    # Find 5M FVGs
    fvg_5m_list = []
    bullish_count, bearish_count = 0, 0
    
    for i in range(2, len(df_5m)):
        current_candle = df_5m.iloc[i]
        prev_candle = df_5m.iloc[i-1]
        prev2_candle = df_5m.iloc[i-2]
        
        is_prev_bearish = prev_candle["Open"] > prev_candle["Close"]
        
        # Bullish FVG
        if not is_prev_bearish and current_candle["Low"] > prev2_candle["High"]:
            gap_size = current_candle["Low"] - prev2_candle["High"]
            gap_percent = (gap_size / prev_candle["Close"]) * 100
            
            # Only include FVGs with gap >= MIN_5M_GAP_PERCENT
            if gap_percent >= MIN_5M_GAP_PERCENT:
                fvg_5m_list.append({
                    "type": "bullish",
                    "upper_line": current_candle["Low"],
                    "lower_line": prev2_candle["High"],
                    "timestamp": df_5m.index[i-1],
                    "gap_percent": gap_percent
                })
                bullish_count += 1
        
        # Bearish FVG
        if is_prev_bearish and current_candle["High"] < prev2_candle["Low"]:
            gap_size = prev2_candle["Low"] - current_candle["High"]
            gap_percent = (gap_size / prev_candle["Close"]) * 100
            
            # Only include FVGs with gap >= MIN_5M_GAP_PERCENT
            if gap_percent >= MIN_5M_GAP_PERCENT:
                fvg_5m_list.append({
                    "type": "bearish",
                    "upper_line": prev2_candle["Low"],
                    "lower_line": current_candle["High"],
                    "timestamp": df_5m.index[i-1],
                    "gap_percent": gap_percent
                })
                bearish_count += 1
    
    print(f"\nTotal 5M FVGs found: {len(fvg_5m_list)} (Bullish: {bullish_count}, Bearish: {bearish_count})")
    return fvg_5m_list

def test_fvg_alignment(one_hour_fvgs, five_min_fvgs, apply_va_filter=False):
    """
    Test alignment between 1H and 5M FVGs
    """
    aligned_setups = []
    
    # Initialize exchange for Value Area calculations
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })
    
    symbol = "BTC/USDT"
    
    for one_hour_fvg in one_hour_fvgs:
        print(f"\nChecking 1H FVG at {one_hour_fvg['timestamp']}")
        print(f"Type: {one_hour_fvg['type']}, Upper: {one_hour_fvg['upper_line']:.2f}, Lower: {one_hour_fvg['lower_line']:.2f}")
        
        aligned_count = 0
        for five_min_fvg in five_min_fvgs:
            # Get monthly Value Area based on the 5M FVG's timestamp
            # Only do this when needed to avoid excessive API calls
            monthly_va = None
            if apply_va_filter:
                vah, val = get_monthly_value_area(exchange, symbol, five_min_fvg['timestamp'])
                if vah is not None and val is not None:
                    monthly_va = (vah, val)
            
            # Check for alignment based on FVG types
            if one_hour_fvg['type'] == 'bullish':
                # For bullish 1H FVG, check if 5M FVG's lower or upper line is within the 1H FVG range
                lower_check = (five_min_fvg['lower_line'] <= one_hour_fvg['lower_line'] <= five_min_fvg['upper_line'])
                upper_check = (five_min_fvg['lower_line'] <= one_hour_fvg['upper_line'] <= five_min_fvg['upper_line'])
                either_check = lower_check or upper_check
                
                va_condition = True  # Default to True if VA filtering is disabled
                
                if monthly_va and apply_va_filter:
                    vah, val = monthly_va
                    va_condition = (five_min_fvg['type'] == 'bullish' and five_min_fvg['upper_line'] < val) or \
                                  (five_min_fvg['type'] == 'bearish' and five_min_fvg['lower_line'] > vah)
                
                if either_check and (not apply_va_filter or va_condition):
                    aligned_setup = {
                        "1h_fvg": one_hour_fvg,
                        "5m_fvg": five_min_fvg,
                        "alignment_type": "bullish_1h_with_5m",
                        "value_area": monthly_va if monthly_va else None
                    }
                    aligned_setups.append(aligned_setup)
                    aligned_count += 1
                    
                    print(f"  Found alignment with 5M FVG: {five_min_fvg['type']} at {five_min_fvg['timestamp']}")
                    print(f"  Upper={five_min_fvg['upper_line']:.2f}, Lower={five_min_fvg['lower_line']:.2f}")
                    
            elif one_hour_fvg['type'] == 'bearish':
                # For bearish 1H FVG, check if 5M FVG's lower or upper line is within the 1H FVG range
                lower_check = (five_min_fvg['lower_line'] <= one_hour_fvg['lower_line'] <= five_min_fvg['upper_line'])
                upper_check = (five_min_fvg['lower_line'] <= one_hour_fvg['upper_line'] <= five_min_fvg['upper_line'])
                either_check = lower_check or upper_check
                
                va_condition = True  # Default to True if VA filtering is disabled
                
                if monthly_va and apply_va_filter:
                    vah, val = monthly_va
                    va_condition = (five_min_fvg['type'] == 'bullish' and five_min_fvg['upper_line'] < val) or \
                                  (five_min_fvg['type'] == 'bearish' and five_min_fvg['lower_line'] > vah)
                
                if either_check and (not apply_va_filter or va_condition):
                    aligned_setup = {
                        "1h_fvg": one_hour_fvg,
                        "5m_fvg": five_min_fvg,
                        "alignment_type": "bearish_1h_with_5m",
                        "value_area": monthly_va if monthly_va else None
                    }
                    aligned_setups.append(aligned_setup)
                    aligned_count += 1
                    
                    print(f"  Found alignment with 5M FVG: {five_min_fvg['type']} at {five_min_fvg['timestamp']}")
                    print(f"  Upper={five_min_fvg['upper_line']:.2f}, Lower={five_min_fvg['lower_line']:.2f}")
        
        if aligned_count > 0:
            print(f"  Total alignments for this 1H FVG: {aligned_count}")
    
    print(f"\nTotal aligned setups found: {len(aligned_setups)}")
    return aligned_setups

def main():
    print("Starting FVG Detection Tests for BTC/USDT")
    print("1H data from beginning of last year (2024)")
    print("5M data from the past week")
    
    # Test 1H FVG detection
    one_hour_fvgs = test_1h_fvg_detection()
    
    # Test 5M FVG detection
    five_min_fvgs = test_5m_fvg_detection()
    
    # Set this to True to apply Value Area filtering
    apply_va_filter = True
    
    print(f"\nApplying Value Area filter: {apply_va_filter}")
    
    # Test alignment between 1H and 5M FVGs
    aligned_setups = test_fvg_alignment(one_hour_fvgs, five_min_fvgs, apply_va_filter)
    
    # Create results directory if it doesn't exist
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    # Get the current datetime
    datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save the results to a JSON file
    results_file = os.path.join(results_dir, f"btc_fvg_test_results_{datetime_str}.json")
    with open(results_file, 'w') as f:
        json.dump({
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": "BTC/USDT",
            "timeframes": {
                "1h": "From 2024-01-01 to present",
                "5m": f"Past week ({(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')})"
            },
            "value_area_filter": apply_va_filter,
            "total_1h_fvgs": len(one_hour_fvgs),
            "total_5m_fvgs": len(five_min_fvgs),
            "total_aligned_setups": len(aligned_setups),
            "1h_fvgs": one_hour_fvgs,
            "5m_fvgs": five_min_fvgs,
            "aligned_setups": aligned_setups
        }, f, indent=2, default=str)
    
    print(f"\nResults saved to: {results_file}")

if __name__ == "__main__":
    main() 