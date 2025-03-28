import ccxt
import pandas as pd
from datetime import datetime, timezone, timedelta
import json
from utils import get_ohlcv_data

def analyze_btc_fvgs():
    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True
        }
    })

    symbol = "BTC/USDT"
    print(f"\nAnalyzing 1H FVGs for {symbol}...")

    # Get current price
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker["last"]
    print(f"Current Price: {current_price:.2f}")

    # Fetch 1H data (3 months)
    since_1h = int((datetime.now(timezone.utc) - timedelta(days=90)).timestamp() * 1000)
    df_1h = get_ohlcv_data(exchange, symbol, "1h", since_1h)
    if df_1h is None:
        print("Failed to fetch 1H data")
        return

    # Find 1H FVGs
    fvg_1h_list = []
    for i in range(1, len(df_1h) - 1):
        # Bullish FVG: Gap between i-1 high and i+1 low, and i+1 close below i high
        if (df_1h.iloc[i-1]["High"] < df_1h.iloc[i+1]["Low"] and 
            df_1h.iloc[i+1]["Close"] < df_1h.iloc[i]["High"]):
            fvg_1h_list.append({
                "type": "bullish",
                "high": df_1h.iloc[i-1]["High"],
                "low": df_1h.iloc[i+1]["Low"],
                "timestamp": df_1h.index[i].isoformat(),
                "gap_size": df_1h.iloc[i+1]["Low"] - df_1h.iloc[i-1]["High"],
                "current_price_in_fvg": "Yes" if df_1h.iloc[i+1]["Low"] <= current_price <= df_1h.iloc[i-1]["High"] else "No"
            })
        # Bearish FVG: Gap between i+1 high and i-1 low, and i+1 close above i low
        if (df_1h.iloc[i+1]["High"] > df_1h.iloc[i-1]["Low"] and 
            df_1h.iloc[i+1]["Close"] > df_1h.iloc[i]["Low"]):
            fvg_1h_list.append({
                "type": "bearish",
                "high": df_1h.iloc[i+1]["High"],
                "low": df_1h.iloc[i-1]["Low"],
                "timestamp": df_1h.index[i].isoformat(),
                "gap_size": df_1h.iloc[i+1]["High"] - df_1h.iloc[i-1]["Low"],
                "current_price_in_fvg": "Yes" if df_1h.iloc[i-1]["Low"] <= current_price <= df_1h.iloc[i+1]["High"] else "No"
            })

    # Create results dictionary
    results = {
        "symbol": symbol,
        "current_price": current_price,
        "analysis_time": datetime.now(timezone.utc).isoformat(),
        "fvgs": fvg_1h_list
    }

    # Save results to JSON file
    output_file = "btc_fvg_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Print results
    print(f"\nFound {len(fvg_1h_list)} 1H FVGs:")
    for fvg in fvg_1h_list:
        print(f"\nType: {fvg['type'].upper()}")
        print(f"Timestamp: {fvg['timestamp']}")
        print(f"High: {fvg['high']:.2f}")
        print(f"Low: {fvg['low']:.2f}")
        print(f"Gap Size: {fvg['gap_size']:.2f}")
        print(f"Current Price in FVG: {fvg['current_price_in_fvg']}")

    print(f"\nResults saved to {output_file}")

if __name__ == "__main__":
    analyze_btc_fvgs() 