from django.urls import path
from dashboard import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardIndexView.as_view(), name='index'),
    path('logout/', views.DashboardLogoutView.as_view(), name='logout'),
    path('updates/', views.UpdateCenterView.as_view(), name='update_center'),
    path('devices/', views.DeviceListView.as_view(), name='device_list'),
    path('applications/', views.ApplicationInventoryListView.as_view(), name='application_inventory'),
    path('devices/<uuid:pk>/inventory/', views.DeviceInventoryView.as_view(), name='device_inventory'),
    path('logs/', views.AuditLogListView.as_view(), name='audit_logs'),
    path('reports/deployments/', views.DeploymentReportListView.as_view(), name='deployment_report'),
    path('reports/deployments/export/', views.DeploymentReportExportView.as_view(), name='deployment_report_export'),
]
