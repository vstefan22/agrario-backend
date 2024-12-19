from django.urls import path, include

urlpatterns = [
    # Include accounts application URLs
    path('api/accounts/', include('accounts.urls')),
    path('api/offers/', include('offers.urls'))
]
