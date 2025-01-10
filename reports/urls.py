from rest_framework.routers import DefaultRouter
from .views import ReportViewSet, DownloadReportView

router = DefaultRouter()
router.register(r"", ReportViewSet, basename="report")

urlpatterns = router.urls