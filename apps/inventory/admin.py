"""Registro de modelos de inventário no Django Admin."""

from django.contrib import admin

from .models import Location, Material, StockBalance, StockLot

admin.site.register(Location)
admin.site.register(Material)
admin.site.register(StockLot)
admin.site.register(StockBalance)
