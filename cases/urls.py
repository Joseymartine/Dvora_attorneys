from django.urls import path
from . import views

app_name = 'cases'
urlpatterns = [
    path('', views.CaseListView.as_view(), name='list'),
    path('add/', views.CaseCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CaseDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CaseUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.CaseDeleteView.as_view(), name='delete'),
]
