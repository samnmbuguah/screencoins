from django.db import models

class ValueAreaResult(models.Model):
    symbol = models.CharField(max_length=50)
    current_price = models.FloatField()
    vah = models.FloatField()
    val = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.symbol