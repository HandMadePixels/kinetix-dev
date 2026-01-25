"""
API URL Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api import views

# Create router for viewsets
router = DefaultRouter()
router.register(r'devices', views.DeviceViewSet, basename='device')
router.register(r'pushes', views.UpdatePushViewSet, basename='push')
router.register(r'commands-history', views.RemoteCommandViewSet, basename='command-history')

app_name = 'api'

urlpatterns = [
    # Device registration (public endpoint)
    path('register/', views.DeviceRegistrationView.as_view(), name='register'),
    
    # Update management
    path('updates/', views.UpdateUploadView.as_view(), name='update-upload'),
    path('updates/<uuid:pk>/', views.UpdateDetailView.as_view(), name='update-detail'),
    path('push-update/', views.PushUpdateView.as_view(), name='push-update'),
    path('remote-command/', views.RemoteCommandActionView.as_view(), name='remote-command'),
    
    # Inventory submission
    path('inventory/', views.InventorySubmissionView.as_view(), name='inventory-submit'),
    path('inventory/<str:hostname>/', views.InventoryDetailView.as_view(), name='inventory-detail'),
    
    # Device commands (polled by agents)
    path('commands/', views.DeviceCommandsView.as_view(), name='device-commands'),
    path('command-status/', views.RemoteCommandStatusView.as_view(), name='command-status'),
    path('update-status/', views.UpdateStatusView.as_view(), name='update-status'),
    path('push-status/', views.UpdateStatusPollView.as_view(), name='push-status'),
    
    # Router URLs (devices CRUD)
    path('', include(router.urls)),
    
    # JWT token endpoints
    path('token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', views.CustomTokenRefreshView.as_view(), name='token_refresh'),
]
