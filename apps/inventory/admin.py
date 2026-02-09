from django.contrib import admin
from .models import Location, Material, StockLot, StockBalance

admin.site.register(Location)
admin.site.register(Material)
admin.site.register(StockLot)
admin.site.register(StockBalance)
