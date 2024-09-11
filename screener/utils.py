import pandas as pd
import numpy as np

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
        # Fetch OHLCV data for the 1-day timeframe
        ohlcv = exchange.fetch_ohlcv(symbol, '1d')
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