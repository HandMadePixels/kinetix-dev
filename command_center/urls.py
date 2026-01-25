"""
URL Configuration for Kinetix
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.static import serve

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API v1
    path('api/v1/', include('api.urls')),
    
    # Dashboard (main UI)
    path('', include('dashboard.urls')),
    
    # Serve media files in production (Waitress/Production mode)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# Custom admin site configuration
admin.site.site_header = "Kinetix Administration"
admin.site.site_title = "Kinetix Admin"
admin.site.index_title = "Welcome to Kinetix Portal"
