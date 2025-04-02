import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import os
import json
import ccxt
import time
from concurrent.futures import ProcessPoolExecutor

# Minimum gap percentage for FVGs (0.42%)
MIN_GAP_PERCENT = 0.42

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

# Cache expiry time in seconds
CACHE_EXPIRY = 3600  # 1 hour cache validity

def load_cached_data(symbol, timeframe):
    """Get OHLCV data from cache if available and not expired."""
    clean_symbol = symbol.replace('/', '_').replace(':', '_')
    
    cache_dir = os.path.join("cache")
    if not os.path.exists(cache_dir):
        return None
    
    cache_file = os.path.join(cache_dir, f"{clean_symbol}_{timeframe}.json")
    if os.path.exists(cache_file):
        # Check if cache is still valid
        cache_age = time.time() - os.path.getmtime(cache_file)
        if cache_age < CACHE_EXPIRY:
            try:
                df = pd.read_json(cache_file)
                if not df.empty:
                    return df
            except:
                pass
    
    return None

def save_cached_data(symbol, timeframe, df):
    """Save OHLCV data to cache."""
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
            # Only keep needed columns to save memory
            needed_columns = ['Open', 'High', 'Low', 'Close']
            return cached_df[needed_columns]
    
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
        
        # Only keep needed columns to save memory
        needed_columns = ['Open', 'High', 'Low', 'Close']
        return df[needed_columns]
    except Exception as e:
        print(f"\rProcessing symbol {symbol} - Error: {str(e)}", end="")
        return None

def check_fvg(exchange, symbol, timeframe="1h", consider_open_close=True):
    """
    Check if a specific symbol has fair value gap (FVG) in the specified timeframe.
    
    Args:
        exchange (ccxt.Exchange): The exchange object
        symbol (str): The trading pair symbol
        timeframe (str): Timeframe for analysis
        consider_open_close (bool): Consider if candle close is in the gap
        
    Returns:
        bool: True if FVG is found, False otherwise
    """
    try:
        # Get current price
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        # Get OHLCV data for the symbol
        since = int((datetime.now(timezone.utc) - timedelta(days=90)).timestamp() * 1000)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since)
        
        if len(ohlcv) < 3:
            return False
        
        # Convert to pandas dataframe
        df = pd.DataFrame(ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms", utc=True)
        df.set_index("Timestamp", inplace=True)
        
        # Find FVG patterns
        fvg_list = []
        min_gap = 0  # Can filter out small FVGs
        
        for i in range(1, len(df)-1):
            prev_high = df.iloc[i-1]["High"]
            prev_low = df.iloc[i-1]["Low"]
            curr_high = df.iloc[i]["High"]
            curr_low = df.iloc[i]["Low"]
            next_high = df.iloc[i+1]["High"]
            next_low = df.iloc[i+1]["Low"]
            
            # Calculate reference price for percentage calculation (closing price of the middle candle)
            reference_price = df.iloc[i]["Close"]

            # Check for FVG
            if curr_low > prev_high:
                gap_size = curr_low - prev_high
                gap_percent = (gap_size / reference_price) * 100
                if gap_percent >= MIN_GAP_PERCENT:
                    fvg_list.append((prev_high, curr_low))
            elif next_low > curr_low:
                gap_size = next_low - curr_low
                gap_percent = (gap_size / reference_price) * 100
                if gap_percent >= MIN_GAP_PERCENT:
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

def process_symbol(data):
    """Process a single symbol for FVG setups - for parallel processing."""
    symbol, exchange, market_type, recent_period = data
    fvg_setups = []
    
    try:
        # Get current price
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker["last"]
        
        # Skip symbols with price too low (often have lower liquidity)
        if current_price < 0.001:
            return []

        # Fetch 1H data (3 months)
        since_1h = int((datetime.now(timezone.utc) - timedelta(days=90)).timestamp() * 1000)
        df_1h = get_ohlcv_data(exchange, symbol, "1h", since_1h)
        if df_1h is None or len(df_1h) < 3:  # Need at least 3 candles for FVG
            return []
            
        # Check price volatility - skip low volatility coins
        price_range = (df_1h['High'].max() - df_1h['Low'].min()) / df_1h['Low'].min()
        if price_range < 0.05:  # Less than 5% range
            return []

        # Find 1H FVGs using vectorized operations
        fvg_1h_list = []
        for i in range(1, len(df_1h) - 1):
            # Bullish FVG: Gap between i-1 high and i+1 low - with minimum gap filter
            if df_1h.iloc[i-1]["High"] < df_1h.iloc[i+1]["Low"]:
                # Calculate gap size as percentage of price
                gap_size = df_1h.iloc[i+1]["Low"] - df_1h.iloc[i-1]["High"]
                gap_percent = (gap_size / df_1h.iloc[i-1]["Close"]) * 100
                
                # Only include FVGs with gap >= MIN_GAP_PERCENT
                if gap_percent >= MIN_GAP_PERCENT:
                    fvg_1h_list.append({
                        "type": "bullish",
                        "high": df_1h.iloc[i]["High"],
                        "low": df_1h.iloc[i+1]["Low"],
                        "timestamp": df_1h.index[i],
                        "gap_percent": gap_percent
                    })
                    
            # Bearish FVG: Gap between i+1 high and i-1 low - with minimum gap filter
            if df_1h.iloc[i+1]["High"] > df_1h.iloc[i-1]["Low"]:
                # Calculate gap size as percentage of price
                gap_size = df_1h.iloc[i+1]["High"] - df_1h.iloc[i-1]["Low"]
                gap_percent = (gap_size / df_1h.iloc[i-1]["Close"]) * 100
                
                # Only include FVGs with gap >= MIN_GAP_PERCENT
                if gap_percent >= MIN_GAP_PERCENT:
                    fvg_1h_list.append({
                        "type": "bearish",
                        "high": df_1h.iloc[i+1]["High"],
                        "low": df_1h.iloc[i]["Low"],
                        "timestamp": df_1h.index[i],
                        "gap_percent": gap_percent
                    })

        # If no 1H FVGs found, return empty list
        if not fvg_1h_list:
            return []

        # Fetch 5M data (for the recent period)
        since_5m = int(recent_period.timestamp() * 1000)
        df_5m = get_ohlcv_data(exchange, symbol, "5m", since_5m)
        if df_5m is None or len(df_5m) < 3:  # Need at least 3 candles for FVG
            return []

        # Check for interactions with any 1H FVG, regardless of when it formed
        for fvg_1h in fvg_1h_list:
            # Process all 5M candles
            for i in range(2, len(df_5m) - 1):  # Start at 2 to allow for i-2 check
                if fvg_1h["type"] == "bullish":
                    # Check if this is a bullish 5M FVG formation - with minimum gap filter
                    bullish_gap = df_5m.iloc[i+1]["Low"] - df_5m.iloc[i-1]["High"]
                    bullish_gap_percent = (bullish_gap / df_5m.iloc[i-1]["Close"]) * 100
                    
                    is_bullish_5m_fvg = (df_5m.iloc[i-1]["High"] < df_5m.iloc[i+1]["Low"] and 
                                         bullish_gap_percent >= MIN_GAP_PERCENT)
                    
                    # Check if price crossed into the upper line of the 1H FVG
                    crossed_upper_line = (df_5m.iloc[i-2]["High"] < fvg_1h["high"] and 
                                       df_5m.iloc[i-1]["High"] >= fvg_1h["high"])
                    
                    # Check if the 1H FVG line falls within the 5M FVG range
                    fvg_on_upper_line = df_5m.iloc[i-1]["High"] <= fvg_1h["high"] <= df_5m.iloc[i+1]["Low"]
                    
                    if is_bullish_5m_fvg and crossed_upper_line and fvg_on_upper_line:
                        fvg_setups.append({
                            "symbol": symbol,
                            "type": "bullish",
                            "current_price": current_price,
                            "fvg_1h": fvg_1h,
                            "fvg_5m": {
                                "high": df_5m.iloc[i-1]["High"],
                                "low": df_5m.iloc[i+1]["Low"],
                                "gap_size": bullish_gap,
                                "gap_percent": bullish_gap_percent,
                                "timestamp": df_5m.index[i]
                            },
                            "stop_loss": df_5m.iloc[i]["High"],
                            "risk_reward": 2  # Default to 2R, can be adjusted
                        })
                else:  # bearish
                    # Check if this is a bearish 5M FVG formation - with minimum gap filter
                    bearish_gap = df_5m.iloc[i+1]["High"] - df_5m.iloc[i-1]["Low"]
                    bearish_gap_percent = (bearish_gap / df_5m.iloc[i-1]["Close"]) * 100
                    
                    is_bearish_5m_fvg = (df_5m.iloc[i+1]["High"] > df_5m.iloc[i-1]["Low"] and 
                                         bearish_gap_percent >= MIN_GAP_PERCENT)
                    
                    # Check if price crossed into the lower line of the 1H FVG
                    crossed_lower_line = (df_5m.iloc[i-2]["Low"] > fvg_1h["low"] and 
                                       df_5m.iloc[i-1]["Low"] <= fvg_1h["low"])
                    
                    # Check if the 1H FVG line falls within the 5M FVG range
                    fvg_on_lower_line = df_5m.iloc[i-1]["Low"] <= fvg_1h["low"] <= df_5m.iloc[i+1]["High"]
                    
                    if is_bearish_5m_fvg and crossed_lower_line and fvg_on_lower_line:
                        fvg_setups.append({
                            "symbol": symbol,
                            "type": "bearish",
                            "current_price": current_price,
                            "fvg_1h": fvg_1h,
                            "fvg_5m": {
                                "high": df_5m.iloc[i+1]["High"],
                                "low": df_5m.iloc[i-1]["Low"],
                                "gap_size": bearish_gap,
                                "gap_percent": bearish_gap_percent,
                                "timestamp": df_5m.index[i]
                            },
                            "stop_loss": df_5m.iloc[i]["Low"],
                            "risk_reward": 2  # Default to 2R, can be adjusted
                        })
        
        return fvg_setups
    
    except Exception as e:
        print(f"\rProcessing symbol {symbol} - Error: {str(e)}", end="")
        return []

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
    total_symbols = len(symbols)
    # We'll still look for 5M FVGs in the recent past (last 7 days) for performance reasons
    recent_period = datetime.now(timezone.utc) - timedelta(days=7)
    
    print(f"\nProcessing {total_symbols} symbols using parallel processing...")
    print(f"Using minimum FVG gap filter: {MIN_GAP_PERCENT}% of price")
    
    # Setup for parallel processing
    max_workers = min(os.cpu_count(), 4)  # Use up to 4 CPU cores
    
    # Prepare data for parallel processing
    symbol_data = [(symbol, exchange, market_type, recent_period) for symbol in symbols]
    
    all_setups = []
    
    # Process in chunks to avoid memory issues
    chunk_size = 50
    for i in range(0, len(symbol_data), chunk_size):
        chunk = symbol_data[i:i+chunk_size]
        
        # Process symbols in parallel
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_symbol, chunk))
        
        # Flatten results
        chunk_setups = [setup for symbol_setups in results for setup in symbol_setups]
        all_setups.extend(chunk_setups)
        
        print(f"\rProcessed {min(i+chunk_size, total_symbols)}/{total_symbols} symbols, found {len(all_setups)} setups so far...", end="")
    
    print("\n\nScreening complete!")
    return all_setups