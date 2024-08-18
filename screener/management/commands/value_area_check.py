import ccxt
import pandas as pd
from datetime import datetime, timezone
from market_profile import MarketProfile
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Fetches USDT-margined perpetual pairs and checks if their current price is above or below the value area'

    def handle(self, *args, **kwargs):
        try:
            print("Starting value_area_check command...")
            results = get_value_area_pairs()
            print(f"Total results: {len(results)}")
            for result in results:
                self.stdout.write(f"Symbol: {result['symbol']}, Current Price: {result['current_price']}, VAH: {result['vah']}, VAL: {result['val']}")
            print("Finished value_area_check command.")
        except Exception as e:
            print(f"Error: {e}")

def get_value_area_pairs():
    # Initialize Binance exchange
    exchange = ccxt.binance()
    print("Initialized Binance exchange")

    # Get the start of the month
    now = datetime.now(timezone.utc)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    print(f"Start of the month: {start_of_month}")

    # Fetch markets and filter for USDT-margined perpetual pairs
    markets = exchange.load_markets()
    # print(f"Fetched markets: {markets}")

    usdt_perpetual_symbols = [symbol for symbol in markets if markets[symbol]['quote'] == 'USDT' and markets[symbol]['type'] == 'swap']
    print(f"USDT-margined perpetual pairs: {usdt_perpetual_symbols}")

    vah_val_results = []

    for symbol in usdt_perpetual_symbols:
        try:
            print(f"Processing symbol: {symbol}")
            since = int(start_of_month.timestamp() * 1000)
            ohlcv = exchange.fetch_ohlcv(symbol, '1d', since)
            if not ohlcv:
                print(f"No OHLCV data for symbol: {symbol}")
                continue

            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            print(f"OHLCV data for {symbol}: {df}")

            # Create MarketProfile object
            mp = MarketProfile(df)
            mp_slice = mp[df.index.min():df.index.max()]

            # Get VAH and VAL
            vah, val = mp_slice.value_area
            print(f"VAH: {vah}, VAL: {val} for symbol: {symbol}")

            # Get the current price
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            print(f"Current price for {symbol}: {current_price}")

            # Check if the current price is above VAH or below VAL
            if current_price > vah or current_price < val:
                print(f"Symbol {symbol} is outside the value area")
                vah_val_results.append({
                    'symbol': symbol,
                    'current_price': current_price,
                    'vah': vah,
                    'val': val
                })
            else:
                print(f"Symbol {symbol} is within the value area")
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")

    return vah_val_results