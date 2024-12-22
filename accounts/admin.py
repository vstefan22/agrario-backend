from django.contrib import admin
from .models import MarketUser, Landowner, ProjectDeveloper

admin.site.register(MarketUser)
admin.site.register(Landowner)
admin.site.register(ProjectDeveloper)
