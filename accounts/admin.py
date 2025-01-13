from django.contrib import admin
from .models import MarketUser, Landowner, ProjectDeveloper

@admin.register(MarketUser)
class MarketUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'is_email_confirmed')
    search_fields = ('email', 'first_name','last_name')
    list_filter = ('role', 'is_email_confirmed')

@admin.register(Landowner)
class LandownerAdmin(admin.ModelAdmin):
    list_display = ('email', 'position')
    search_fields = ('email', 'position')

@admin.register(ProjectDeveloper)
class ProjectDeveloperAdmin(admin.ModelAdmin):
    list_display = ('email', 'company_name', 'company_website')
    search_fields = ('email', 'company_name')
