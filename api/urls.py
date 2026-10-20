from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, CaseViewSet, AppointmentViewSet

router = DefaultRouter()
router.register('clients', ClientViewSet, basename='client')
router.register('cases', CaseViewSet, basename='case')
router.register('appointments', AppointmentViewSet, basename='appointment')
urlpatterns = router.urls
