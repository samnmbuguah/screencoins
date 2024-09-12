from django.http import JsonResponse
from django.views import View
from .models import ValueAreaResult

class ValueAreaCheckView(View):
    def get(self, request, *args, **kwargs):
        try:
            # Fetch only the 'symbol' field and limit to the first 5 results
            results = ValueAreaResult.objects.values_list('symbol', flat=True)[:5]
            return JsonResponse(list(results), safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)