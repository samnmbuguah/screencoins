from django.http import JsonResponse
from django.views import View
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from .models import ValueAreaResult

class ValueAreaCheckView(View):
    def get(self, request, *args, **kwargs):
        try:
            # Calculate the timestamp for 24 hours ago
            last_24_hours = timezone.now() - timedelta(hours=24)
            
            # Filter results from the last 24 hours, annotate with count, and order by count
            results = (ValueAreaResult.objects
                       .filter(timestamp__gte=last_24_hours)
                       .values('symbol')
                       .annotate(symbol_count=Count('symbol'))
                       .order_by('-symbol_count'))
            
            # Extract the symbols from the results
            symbols = [result['symbol'] for result in results]
            
            return JsonResponse(symbols, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)