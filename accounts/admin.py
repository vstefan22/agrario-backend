"""Admin configuration for the accounts application.

This module registers models related to the accounts application
with the Django admin site.
"""

from django.contrib import admin

from .models import Landowner, MarketUser, ProjectDeveloper

# Register models to be managed through the Django admin interface
admin.site.register(MarketUser)
admin.site.register(Landowner)
admin.site.register(ProjectDeveloper)
