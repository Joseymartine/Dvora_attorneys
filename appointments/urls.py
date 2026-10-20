from django.urls import path
from . import views

app_name = 'appointments'
urlpatterns = [
    path('', views.AppointmentListView.as_view(), name='list'),
    path('add/', views.AppointmentCreateView.as_view(), name='create'),
    path('<int:pk>/', views.AppointmentDetailView.as_view(), name='detail'),
    path('<int:pk>/approve/', views.AppointmentApproveView.as_view(), name='approve'),
    path('<int:pk>/edit/', views.AppointmentUpdateView.as_view(), name='update'),
]
