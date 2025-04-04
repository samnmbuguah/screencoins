import ccxt
import json
import os
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from screener.models import ValueAreaResult
from screener.utils import get_value_area_pairs, is_price_within_fvg

class Command(BaseCommand):
    help = 'Update value area results'

    def handle(self, *args, **kwargs):
        try:
            # Initialize Binance exchange with API key and secret from environment variables
            exchange = ccxt.binance(
                {
                    "apiKey": settings.BINANCE_API_KEY,
                    "secret": settings.BINANCE_API_SECRET,
                }
            )
            
            # Get the start of the month
            now = datetime.now(timezone.utc)
            start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            
            # Load markets from matching_futures_markets.json
            matching_file_path = os.path.join(settings.BASE_DIR, 'screener', 'data', 'matching_futures_markets.json')
            with open(matching_file_path, 'r') as file:
                futures_symbols = json.load(file)
            
            # Filter futures_symbols where the price is within an FVG
            filtered_futures_symbols = []
            for symbol in futures_symbols:
                # Fetch the current price
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                # Check if the current price is within an FVG
                if is_price_within_fvg(exchange, symbol, current_price):
                    filtered_futures_symbols.append(symbol)
            
            # Get value area pairs for spot and futures prices
            spot_results = get_value_area_pairs(exchange, filtered_futures_symbols, "spot", start_of_month, percentage=0.99)
            futures_results = get_value_area_pairs(exchange, filtered_futures_symbols, "futures", start_of_month, percentage=0.99)

            # Convert results to dictionaries for easy lookup
            spot_dict = {result['symbol']: result for result in spot_results}
            futures_dict = {result['symbol'].replace(':USDT', ''): result for result in futures_results}
            
            # Find symbols where both spot and futures prices are outside the value area
            outside_value_area = []
            
            for symbol in filtered_futures_symbols:
                normalized_symbol = symbol.replace(':USDT', '')
                if normalized_symbol in spot_dict and normalized_symbol in futures_dict:
                    spot_result = spot_dict[normalized_symbol]
                    futures_result = futures_dict[normalized_symbol]
            
                    if (spot_result['current_price'] > spot_result['vah'] or spot_result['current_price'] < spot_result['val']) and \
                       (futures_result['current_price'] > futures_result['vah'] or futures_result['current_price'] < futures_result['val']):
                        outside_value_area.append({
                            'symbol': f"{normalized_symbol}:USDT",
                            'current_price': spot_result['current_price'],
                            'vah': spot_result['vah'],
                            'val': spot_result['val']
                        })
            
            # Save new results without clearing old results
            for result in outside_value_area:
                ValueAreaResult.objects.create(
                    symbol=result['symbol'],
                    current_price=result['current_price'],
                    vah=result['vah'],
                    val=result['val']
                )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error: {str(e)}'))
        else:
            self.stdout.write(self.style.SUCCESS('Successfully updated value area results'))