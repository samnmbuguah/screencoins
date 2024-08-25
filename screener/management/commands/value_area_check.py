import ccxt
import pandas as pd
from datetime import datetime, timezone
from market_profile import MarketProfile
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fetches USDT-margined perpetual pairs and checks if their current price is above or below the value area"

    def handle(self, *args, **kwargs):
        try:
            print("Starting value_area_check command...")
            
            # Initialize Binance exchange
            exchange = ccxt.binance()
            
            # Get the start of the month
            now = datetime.now(timezone.utc)
            start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            
            # Fetch markets and filter for USDT-margined perpetual pairs
            markets = exchange.load_markets()
            futures_symbols = [
                symbol
                for symbol in markets
                if markets[symbol]["quote"] == "USDT" and markets[symbol]["type"] == "swap"
            ]

            # Get value area pairs for spot and futures prices
            spot_results = get_value_area_pairs(exchange, futures_symbols, "spot", start_of_month, mode="tpo")
            futures_results = get_value_area_pairs(exchange, futures_symbols, "futures", start_of_month, mode="tpo")

            # Convert results to dictionaries for easy lookup
            spot_dict = {result['symbol']: result for result in spot_results}
            futures_dict = {result['symbol'].replace(':USDT', ''): result for result in futures_results}
            
            # Find symbols where both spot and futures prices are outside the value area
            outside_value_area = []
            
            for symbol in futures_symbols:
                normalized_symbol = symbol.replace(':USDT', '')
                if normalized_symbol in spot_dict and normalized_symbol in futures_dict:
                    spot_result = spot_dict[normalized_symbol]
                    futures_result = futures_dict[normalized_symbol]
            
                    if (spot_result['current_price'] > spot_result['vah'] or spot_result['current_price'] < spot_result['val']) and \
                       (futures_result['current_price'] > futures_result['vah'] or futures_result['current_price'] < futures_result['val']):
                        outside_value_area.append({
                            'symbol': normalized_symbol,
                            'spot_current_price': spot_result['current_price'],
                            'spot_vah': spot_result['vah'],
                            'spot_val': spot_result['val'],
                            'futures_current_price': futures_result['current_price'],
                            'futures_vah': futures_result['vah'],
                            'futures_val': futures_result['val']
                        })
            
            print(f"Total pairs outside value area: {len(outside_value_area)}")
            for result in outside_value_area:
                self.stdout.write(
                    f"Symbol: {result['symbol']}, Spot Current Price: {result['spot_current_price']}, Spot VAH: {result['spot_vah']}, Spot VAL: {result['spot_val']}, "
                    f"Futures Current Price: {result['futures_current_price']}, Futures VAH: {result['futures_vah']}, Futures VAL: {result['futures_val']}"
                )
            print("Finished value_area_check command.")
        except Exception as e:
            print(f"Error: {e}")


def get_value_area_pairs(exchange, symbols, market_type, start_of_month, mode="tpo"):
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
            ohlcv = exchange.fetch_ohlcv(symbol, "1h", since)
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

            # Get tick size for the symbol
            tick_size = float(exchange.markets[symbol]["precision"]["price"])

            # Create MarketProfile object with tick size and mode
            mp = MarketProfile(df, tick_size=tick_size, mode=mode)

            # Slice the MarketProfile object
            try:
                mp_slice = mp[df.index.min() : df.index.max()]
            except Exception:
                continue

            # Get Value areas
            val, vah = mp_slice.value_area

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
