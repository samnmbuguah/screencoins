import ccxt
import pandas as pd
from datetime import datetime
from market_profile import MarketProfile

# Initialize Binance exchange
exchange = ccxt.binance()

# Get the start of the month
now = datetime.utcnow()
start_of_month = datetime(now.year, now.month, 1)

# Fetch historical data
since = int(start_of_month.timestamp() * 1000)
symbols = exchange.load_markets().keys()
vah_val_results = []

for symbol in symbols:
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1d', since)
        if not ohlcv:
            continue

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        # Create MarketProfile object
        mp = MarketProfile(df)
        mp_slice = mp[df.index.min():df.index.max()]

        # Get VAH and VAL
        vah, val = mp_slice.value_area

        # Get the current price
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # Check if the current price is above VAH or below VAL
        if current_price > vah or current_price < val:
            vah_val_results.append({
                'symbol': symbol,
                'current_price': current_price,
                'vah': vah,
                'val': val
            })
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")

# Output the results
for result in vah_val_results:
    print(f"Symbol: {result['symbol']}, Current Price: {result['current_price']}, VAH: {result['vah']}, VAL: {result['val']}")

