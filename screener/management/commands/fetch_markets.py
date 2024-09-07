import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
import ccxt

class Command(BaseCommand):
    help = 'Fetches spot and futures markets and saves them to JSON files'

    def handle(self, *args, **kwargs):
        try:
            # Initialize Binance exchange with API key and secret from environment variables
            exchange = ccxt.binance({
                "apiKey": settings.BINANCE_API_KEY,
                "secret": settings.BINANCE_API_SECRET,
            })

            # Fetch markets
            markets = exchange.load_markets()

            # Define the quotes to filter
            valid_quotes = {"USDT"}

            # Filter for futures markets with valid quotes
            futures_symbols = [
                symbol for symbol in markets
                if markets[symbol]["quote"] in valid_quotes and markets[symbol]["type"] == "swap"
            ]

            # Filter for spot markets with valid quotes
            spot_symbols = [
                symbol for symbol in markets
                if markets[symbol]["quote"] in valid_quotes and markets[symbol]["type"] == "spot"
            ]

            # Extract base symbols from spot markets
            spot_base_symbols = set()
            for symbol in spot_symbols:
                base_symbol = symbol.split('/')[0]
                spot_base_symbols.add(base_symbol)

            # List of delisted coins
            delisted_coins = {"CVC", "BTCST", "SC", "RAY", "FTT"}

            # Find matching futures markets and filter out delisted coins
            matching_futures_symbols = [
                symbol for symbol in futures_symbols
                if symbol.split('/')[0].replace('1000', '') in spot_base_symbols and symbol.split('/')[0] not in delisted_coins
            ]

            # Define file paths
            futures_file_path = os.path.join(settings.BASE_DIR, 'screener', 'data', 'futures_markets.json')
            spot_file_path = os.path.join(settings.BASE_DIR, 'screener', 'data', 'spot_markets.json')
            matching_file_path = os.path.join(settings.BASE_DIR, 'screener', 'data', 'matching_futures_markets.json')

            # Save futures markets to JSON file
            with open(futures_file_path, 'w') as futures_file:
                json.dump(futures_symbols, futures_file, indent=4)
            self.stdout.write(self.style.SUCCESS('Successfully saved futures markets to futures_markets.json'))

            # Save spot markets to JSON file
            with open(spot_file_path, 'w') as spot_file:
                json.dump(spot_symbols, spot_file, indent=4)
            self.stdout.write(self.style.SUCCESS('Successfully saved spot markets to spot_markets.json'))

            # Save matching futures markets to JSON file
            with open(matching_file_path, 'w') as matching_file:
                json.dump(matching_futures_symbols, matching_file, indent=4)
            self.stdout.write(self.style.SUCCESS('Successfully saved matching futures markets to matching_futures_markets.json'))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error fetching markets: {e}'))