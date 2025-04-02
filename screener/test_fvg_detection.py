import ccxt
import pandas as pd
from datetime import datetime, timezone, timedelta
from utils import get_ohlcv_data
import json
import os

# Minimum gap percentage thresholds
MIN_1H_GAP_PERCENT = 0.4
MIN_5M_GAP_PERCENT = 0.1

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
    
    # Get XRP data for 1H timeframe
    symbol = "XRP/USDT"
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    since = int(start_date.timestamp() * 1000)
    
    df_1h = get_ohlcv_data(exchange, symbol, "1h", since)
    if df_1h is None or len(df_1h) < 3:
        print("Failed to get 1H data")
        return
    
    # Find 1H FVGs
    fvg_1h_list = []
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
                print(f"\nFound Bullish 1H FVG at {df_1h.index[i-1]}")
                print(f"Upper line: {current_candle['Low']:.4f}")
                print(f"Lower line: {prev2_candle['High']:.4f}")
                print(f"Gap percent: {gap_percent:.2f}%")
        
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
                print(f"\nFound Bearish 1H FVG at {df_1h.index[i-1]}")
                print(f"Upper line: {prev2_candle['Low']:.4f}")
                print(f"Lower line: {current_candle['High']:.4f}")
                print(f"Gap percent: {gap_percent:.2f}%")
    
    print(f"\nTotal 1H FVGs found: {len(fvg_1h_list)}")
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
    
    # Get XRP data for 5M timeframe
    symbol = "XRP/USDT"
    start_date = datetime(2025, 3, 24, tzinfo=timezone.utc)
    end_date = start_date + timedelta(days=7)
    
    since = int(start_date.timestamp() * 1000)
    df_5m = get_ohlcv_data(exchange, symbol, "5m", since)
    
    if df_5m is None or len(df_5m) < 3:
        print("Failed to get 5M data")
        return
    
    # Filter to specific date range
    end_timestamp = int(end_date.timestamp() * 1000)
    df_5m = df_5m[df_5m.index < pd.Timestamp(end_timestamp, unit='ms', tz='UTC')]
    
    # Find 5M FVGs
    fvg_5m_list = []
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
                print(f"\nFound Bullish 5M FVG at {df_5m.index[i-1]}")
                print(f"Upper line: {current_candle['Low']:.4f}")
                print(f"Lower line: {prev2_candle['High']:.4f}")
                print(f"Gap percent: {gap_percent:.2f}%")
        
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
                print(f"\nFound Bearish 5M FVG at {df_5m.index[i-1]}")
                print(f"Upper line: {prev2_candle['Low']:.4f}")
                print(f"Lower line: {current_candle['High']:.4f}")
                print(f"Gap percent: {gap_percent:.2f}%")
    
    print(f"\nTotal 5M FVGs found: {len(fvg_5m_list)}")
    return fvg_5m_list

def test_fvg_alignment(fvg_1h_list, fvg_5m_list):
    """Test alignment between 1H and 5M FVGs"""
    print("\n=== Testing FVG Alignment ===")
    
    aligned_setups = []
    
    for fvg_1h in fvg_1h_list:
        print(f"\nChecking 1H FVG at {fvg_1h['timestamp']}")
        print(f"Type: {fvg_1h['type']}")
        print(f"Upper line: {fvg_1h['upper_line']:.4f}")
        print(f"Lower line: {fvg_1h['lower_line']:.4f}")
        
        for fvg_5m in fvg_5m_list:
            # Check if 5M FVG is within 1 hour of 1H FVG
            time_diff = abs((fvg_5m['timestamp'] - fvg_1h['timestamp']).total_seconds())
            if time_diff <= 3600:  # Within 1 hour
                print(f"\nFound 5M FVG at {fvg_5m['timestamp']}")
                print(f"Type: {fvg_5m['type']}")
                print(f"Upper line: {fvg_5m['upper_line']:.4f}")
                print(f"Lower line: {fvg_5m['lower_line']:.4f}")
                
                # Check alignment - the 1H FVG line should be within the 5M FVG range
                if fvg_5m['type'] == 'bullish':
                    # For bullish 5M FVG, check if 1H FVG's upper line is within the 5M FVG range
                    line_in_range = fvg_5m['lower_line'] <= fvg_1h['upper_line'] <= fvg_5m['upper_line']
                else:  # bearish
                    # For bearish 5M FVG, check if 1H FVG's lower line is within the 5M FVG range
                    line_in_range = fvg_5m['lower_line'] <= fvg_1h['lower_line'] <= fvg_5m['upper_line']
                
                print(f"Line in range: {line_in_range}")
                
                if line_in_range:
                    aligned_setups.append({
                        "1h_fvg": fvg_1h,
                        "5m_fvg": fvg_5m,
                        "time_diff_seconds": time_diff
                    })
    
    print(f"\nTotal aligned setups found: {len(aligned_setups)}")
    return aligned_setups

def main():
    print("Starting FVG Detection Tests for XRP/USDT")
    
    # Test 1H FVG detection
    fvg_1h_list = test_1h_fvg_detection()
    
    # Test 5M FVG detection
    fvg_5m_list = test_5m_fvg_detection()
    
    # Test alignment between FVGs
    aligned_setups = test_fvg_alignment(fvg_1h_list, fvg_5m_list)
    
    # Create results directory if it doesn't exist
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    # Generate timestamp for filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_filename = os.path.join(results_dir, f"fvg_test_results_{timestamp}.json")

    # Save results to JSON file
    with open(json_filename, 'w') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": "XRP/USDT",
            "analysis_periods": {
                "1h_fvgs": "From 2025-01-01T00:00:00+00:00 to present",
                "5m_fvgs": "One week period (2025-03-24T00:00:00+00:00 to 2025-03-31T00:00:00+00:00)"
            },
            "fvg_logic": {
                "bullish": "For bearish previous candle, current high < low of 2 candles ago",
                "bearish": "For bullish previous candle, current low > high of 2 candles ago"
            },
            "min_gap_thresholds": {
                "1h": MIN_1H_GAP_PERCENT,
                "5m": MIN_5M_GAP_PERCENT
            },
            "total_1h_fvgs": len(fvg_1h_list),
            "total_5m_fvgs": len(fvg_5m_list),
            "total_aligned_setups": len(aligned_setups),
            "1h_fvgs": fvg_1h_list,
            "5m_fvgs": fvg_5m_list,
            "aligned_setups": aligned_setups
        }, f, indent=2, default=str)

    print(f"\nResults saved to: {json_filename}")

if __name__ == "__main__":
    main() 