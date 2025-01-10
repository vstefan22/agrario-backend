from django.contrib import admin
from .models import Report

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("identifier", "created", "area_m2", "visible_for")
    search_fields = ("identifier",)
    list_filter = ("visible_for",)
