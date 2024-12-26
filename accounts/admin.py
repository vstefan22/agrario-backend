from django.contrib import admin
from .models import MarketUser, Landowner, ProjectDeveloper

@admin.register(MarketUser)
class MarketUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_email_confirmed')
    search_fields = ('username', 'email')
    list_filter = ('role', 'is_email_confirmed')

@admin.register(Landowner)
class LandownerAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'position')
    search_fields = ('username', 'email', 'position')

@admin.register(ProjectDeveloper)
class ProjectDeveloperAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'company_name', 'company_website')
    search_fields = ('username', 'email', 'company_name')
