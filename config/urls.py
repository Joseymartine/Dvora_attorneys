from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from core import views

urlpatterns = [
    path('api/', include('api.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('appointments/', include('appointments.urls')),
    path('accounts/login/', views.RoleLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('cases/', include('cases.urls')),
    path("admin/", admin.site.urls),
    path("clients/", include("clients.urls")),
    path("", views.home, name="home"),
]
