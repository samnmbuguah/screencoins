import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import os
import json

def get_value_area_pairs(exchange, symbols, market_type, start_of_month, percentage=0.84):
    vah_val_results = []

    for symbol in symbols:
        try:
            since = int(start_of_month.timestamp() * 1000)
            
            if market_type == "spot":
                symbol = symbol.split(':')[0]  # Remove ':USDT' part for spot market
                if symbol.startswith('1000'):
                    symbol = symbol[4:]  # Remove '1000' prefix
            elif market_type == "futures":
                symbol = symbol  # Keep the symbol as is for futures market

            # Fetch OHLCV data
            ohlcv = exchange.fetch_ohlcv(symbol, "4h", since)
            if not ohlcv:
                continue

            # Convert to DataFrame with all OHLCV columns
            df = pd.DataFrame(
                ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"]
            )
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms")
            df.set_index("Timestamp", inplace=True)

            # Ensure DataFrame has the correct index and columns
            if not all(
                col in df.columns for col in ["Open", "High", "Low", "Close", "Volume"]
            ):
                continue

            # Calculate VAH and VAL using TA-Lib
            vah, val = calculate_value_area(df, percentage)

            # Get the current price
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker["last"]

            # Check if the current price is above VAH or below VAL
            if current_price > vah or current_price < val:
                vah_val_results.append(
                    {
                        "symbol": symbol,
                        "current_price": current_price,
                        "vah": vah,
                        "val": val,
                    }
                )
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")

    return vah_val_results

def calculate_value_area(df, percentage=0.84, bins=100):
    """
    Calculates the value area based on volume.

    Args:
        df (pd.DataFrame): The price and volume data.
        percentage (float): The percentage of total volume.
        bins (int): The number of bins for the histogram.

    Returns:
        tuple: (value_area_high, value_area_low)
    """
    # Create a histogram of volume distribution
    histogram, bin_edges = np.histogram(df['Close'], bins=bins, weights=df['Volume'])

    # Find the point of control (POC)
    poc_index = np.argmax(histogram)
    poc = bin_edges[poc_index]

    # Calculate value area
    value_area_high = poc
    value_area_low = poc
    cumulative_volume = histogram[poc_index]

    total_volume = histogram.sum()

    # Expand the range upwards and downwards until the cumulative volume reaches the specified percentage
    for i in range(1, len(histogram)):
        if cumulative_volume >= total_volume * percentage:
            break
        if poc_index - i >= 0:
            cumulative_volume += histogram[poc_index - i]
            value_area_low = bin_edges[poc_index - i]
        if poc_index + i < len(histogram):
            cumulative_volume += histogram[poc_index + i]
            value_area_high = bin_edges[poc_index + i]

    return value_area_high, value_area_low


def is_price_within_fvg(exchange, symbol, current_price, min_gap=0, consider_open_close=False):
    """
    Checks if the current price is within an unfilled Fair Value Gap (FVG) in the 1-day timeframe.

    Args:
        exchange (ccxt.Exchange): The exchange object.
        symbol (str): The trading pair symbol.
        current_price (float): The current price.
        min_gap (float, optional): Minimum price gap size for FVG (default: 0).
        consider_open_close (bool, optional): Consider price at open/close of current candle (default: False).

    Returns:
        bool: True if the current price is within an unfilled FVG, False otherwise.
    """
    try:
        # Calculate the timestamp for the beginning of the last year
        now = datetime.now(timezone.utc)
        start_of_last_year = datetime(now.year - 1, 1, 1, tzinfo=timezone.utc)
        since = int(start_of_last_year.timestamp() * 1000)

        # Fetch OHLCV data for the 1-day timeframe from the beginning of last year
        ohlcv = exchange.fetch_ohlcv(symbol, '1d', since)
        if not ohlcv:
            return False

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms")
        df.set_index("Timestamp", inplace=True)

        # Identify FVGs
        fvg_list = []
        for i in range(1, len(df) - 1):
            prev_high = df.iloc[i - 1]["High"]
            curr_low = df.iloc[i]["Low"]
            next_low = df.iloc[i + 1]["Low"]

            # Check for FVG
            if curr_low > prev_high and (curr_low - prev_high) >= min_gap:
                fvg_list.append((prev_high, curr_low))
            elif next_low > curr_low and (next_low - curr_low) >= min_gap:
                fvg_list.append((curr_low, next_low))

        # Check if current price is within any FVG
        for fvg in fvg_list:
            if consider_open_close:
                if fvg[0] <= current_price <= fvg[1]:
                    return True
            else:
                if fvg[0] < current_price < fvg[1]:
                    return True

        return False
    except Exception as e:
        print(f"Error checking FVG for {symbol}: {e}")
        return False

def load_cached_data(symbol, timeframe):
    """Load cached OHLCV data for a symbol and timeframe."""
    # Clean symbol name for filename
    clean_symbol = symbol.replace('/', '_').replace(':', '_')
    
    cache_dir = os.path.join("cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    cache_file = os.path.join(cache_dir, f"{clean_symbol}_{timeframe}.json")
    if os.path.exists(cache_file):
        try:
            df = pd.read_json(cache_file)
            df.index = pd.to_datetime(df.index, utc=True)
            return df
        except:
            return None
    return None

def save_cached_data(symbol, timeframe, df):
    """Save OHLCV data to cache."""
    # Clean symbol name for filename
    clean_symbol = symbol.replace('/', '_').replace(':', '_')
    
    cache_dir = os.path.join("cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    cache_file = os.path.join(cache_dir, f"{clean_symbol}_{timeframe}.json")
    try:
        df_copy = df.copy()
        df_copy.to_json(cache_file, date_format='iso')
    except:
        pass  # If saving fails, just continue without caching

def get_ohlcv_data(exchange, symbol, timeframe, since):
    """Get OHLCV data, using cache if available."""
    # Try to load from cache first
    cached_df = load_cached_data(symbol, timeframe)
    if cached_df is not None:
        # Check if we need to fetch more recent data
        latest_cached = cached_df.index.max()
        latest_required = pd.Timestamp(since, unit='ms', tz='UTC')
        
        if latest_cached >= latest_required:
            return cached_df
    
    # If no cache or cache is old, fetch new data
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since)
        if not ohlcv:
            return None
        
        df = pd.DataFrame(ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms", utc=True)
        df.set_index("Timestamp", inplace=True)
        
        # Save to cache
        save_cached_data(symbol, timeframe, df)
        return df
    except Exception as e:
        print(f"\rProcessing symbol {symbol} - Error: {str(e)}", end="")
        return None

def find_fvg_setups(exchange, symbols, market_type):
    """
    Screens for Fair Value Gap (FVG) setups on 1H and 5M timeframes.
    All historical 1H FVGs will be considered regardless of when they formed.
    
    Args:
        exchange (ccxt.Exchange): The exchange object
        symbols (list): List of trading pair symbols
        market_type (str): Either "spot" or "futures"
        
    Returns:
        list: List of FVG setups
    """
    fvg_setups = []
    total_symbols = len(symbols)
    # We'll still look for 5M FVGs in the recent past (last 7 days) for performance reasons
    recent_period = datetime.now(timezone.utc) - timedelta(days=7)
    
    print(f"\nProcessing {total_symbols} symbols...")
    
    for idx, symbol in enumerate(symbols, 1):
        try:
            # Get current price
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker["last"]

            # Fetch 1H data (3 months) - we can extend this to get more historical data if needed
            since_1h = int((datetime.now(timezone.utc) - timedelta(days=90)).timestamp() * 1000)
            print(f"\rProcessing {idx}/{total_symbols}: {symbol} - Fetching 1H data...", end="")
            df_1h = get_ohlcv_data(exchange, symbol, "1h", since_1h)
            if df_1h is None:
                continue

            # Find 1H FVGs - no time restriction
            fvg_1h_list = []
            for i in range(1, len(df_1h) - 1):
                # Bullish FVG: Gap between i-1 high and i+1 low, and i+1 close below i high
                if (df_1h.iloc[i-1]["High"] < df_1h.iloc[i+1]["Low"] and 
                    df_1h.iloc[i+1]["Close"] < df_1h.iloc[i]["High"]):
                    fvg_1h_list.append({
                        "type": "bullish",
                        "high": df_1h.iloc[i]["High"],  # Middle candle high
                        "low": df_1h.iloc[i+1]["Low"],  # Right candle low
                        "timestamp": df_1h.index[i]
                    })
                # Bearish FVG: Gap between i+1 high and i-1 low, and i+1 close above i low
                if (df_1h.iloc[i+1]["High"] > df_1h.iloc[i-1]["Low"] and 
                    df_1h.iloc[i+1]["Close"] > df_1h.iloc[i]["Low"]):
                    fvg_1h_list.append({
                        "type": "bearish",
                        "high": df_1h.iloc[i+1]["High"],  # Right candle high
                        "low": df_1h.iloc[i]["Low"],      # Middle candle low
                        "timestamp": df_1h.index[i]
                    })

            # If no 1H FVGs found, continue to next symbol
            if not fvg_1h_list:
                continue

            print(f"\rProcessing {idx}/{total_symbols}: {symbol} - Found {len(fvg_1h_list)} 1H FVGs, checking 5M...", end="")

            # Fetch 5M data (for the recent period - 7 days is enough to find recent setups)
            since_5m = int(recent_period.timestamp() * 1000)
            df_5m = get_ohlcv_data(exchange, symbol, "5m", since_5m)
            if df_5m is None:
                continue

            # Check for interactions with any 1H FVG, regardless of when it formed
            for fvg_1h in fvg_1h_list:
                # Look for 5M FVG in the recent period
                for i in range(1, len(df_5m) - 1):
                    if fvg_1h["type"] == "bullish":
                        # Check if this is a bullish 5M FVG formation - only check for the gap
                        is_bullish_5m_fvg = df_5m.iloc[i-1]["High"] < df_5m.iloc[i+1]["Low"]
                        
                        # Check if price crossed into the upper line of the 1H FVG
                        crossed_upper_line = False
                        if i > 0:  # Make sure we can check the previous candle
                            # Price crossed from below to above the upper line of 1H FVG
                            crossed_upper_line = (df_5m.iloc[i-2]["High"] < fvg_1h["high"] and 
                                               df_5m.iloc[i-1]["High"] >= fvg_1h["high"])
                        
                        # Check if any of the three candles forming the FVG touch the upper line
                        touches_upper_line = (abs(df_5m.iloc[i-1]["High"] - fvg_1h["high"]) / fvg_1h["high"] < 0.001 or
                                           abs(df_5m.iloc[i]["High"] - fvg_1h["high"]) / fvg_1h["high"] < 0.001 or
                                           abs(df_5m.iloc[i+1]["High"] - fvg_1h["high"]) / fvg_1h["high"] < 0.001)
                        
                        if is_bullish_5m_fvg and crossed_upper_line and touches_upper_line:
                            fvg_setups.append({
                                "symbol": symbol,
                                "type": "bullish",
                                "current_price": current_price,
                                "fvg_1h": fvg_1h,
                                "fvg_5m": {
                                    "high": df_5m.iloc[i-1]["High"],
                                    "low": df_5m.iloc[i+1]["Low"],
                                    "timestamp": df_5m.index[i]
                                },
                                "stop_loss": df_5m.iloc[i]["High"],
                                "risk_reward": 2  # Default to 2R, can be adjusted
                            })
                    else:  # bearish
                        # Check if this is a bearish 5M FVG formation - only check for the gap
                        is_bearish_5m_fvg = df_5m.iloc[i+1]["High"] > df_5m.iloc[i-1]["Low"]
                        
                        # Check if price crossed into the lower line of the 1H FVG
                        crossed_lower_line = False
                        if i > 0:  # Make sure we can check the previous candle
                            # Price crossed from above to below the lower line of 1H FVG
                            crossed_lower_line = (df_5m.iloc[i-2]["Low"] > fvg_1h["low"] and 
                                              df_5m.iloc[i-1]["Low"] <= fvg_1h["low"])
                        
                        # Check if any of the three candles forming the FVG touch the lower line
                        touches_lower_line = (abs(df_5m.iloc[i-1]["Low"] - fvg_1h["low"]) / fvg_1h["low"] < 0.001 or
                                          abs(df_5m.iloc[i]["Low"] - fvg_1h["low"]) / fvg_1h["low"] < 0.001 or
                                          abs(df_5m.iloc[i+1]["Low"] - fvg_1h["low"]) / fvg_1h["low"] < 0.001)
                        
                        if is_bearish_5m_fvg and crossed_lower_line and touches_lower_line:
                            fvg_setups.append({
                                "symbol": symbol,
                                "type": "bearish",
                                "current_price": current_price,
                                "fvg_1h": fvg_1h,
                                "fvg_5m": {
                                    "high": df_5m.iloc[i+1]["High"],
                                    "low": df_5m.iloc[i-1]["Low"],
                                    "timestamp": df_5m.index[i]
                                },
                                "stop_loss": df_5m.iloc[i]["Low"],
                                "risk_reward": 2  # Default to 2R, can be adjusted
                            })

            if fvg_setups and fvg_setups[-1]["symbol"] == symbol:
                print(f"\rProcessing {idx}/{total_symbols}: {symbol} - Found setup!                    ", end="")
            else:
                print(f"\rProcessing {idx}/{total_symbols}: {symbol} - No setup found.                    ", end="")

        except Exception as e:
            print(f"\rProcessing {idx}/{total_symbols}: {symbol} - Error: {str(e)}                    ", end="")
            continue

    print("\n\nScreening complete!")
    return fvg_setups