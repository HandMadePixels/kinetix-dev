from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LogoutView
from django.db.models import Count, Max, Q, OuterRef, Subquery
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
import datetime
from core.models import Device, AuditLog, DeviceGroup
from updates.models import Update, UpdatePush
from inventory.models import InventorySnapshot, ApplicationInventory, ServiceInventory

class DashboardLogoutView(LogoutView):
    next_page = reverse_lazy('admin:login')

class UpdateCenterView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/update_center.html'

    def test_func(self):
        return self.request.user.has_perm('updates.add_update') or \
               self.request.user.has_perm('updates.can_deploy_updates')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_updates'] = Update.objects.filter(scan_status__in=['clean', 'pending']).order_by('-uploaded_at')
        context['devices'] = Device.objects.filter(status='active').order_by('hostname')
        context['device_count'] = context['devices'].count()
        context['device_groups'] = DeviceGroup.objects.annotate(num_devices=Count('devices')).order_by('name')
        context['recent_pushes'] = UpdatePush.objects.select_related('update', 'device').order_by('-scheduled_at', '-pushed_at')[:20]
        return context

class DashboardIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # KPI Stats
        context['total_devices'] = Device.objects.count()
        
        # Online devices (seen in last 5 minutes)
        timeout = timezone.now() - timezone.timedelta(seconds=300)
        context['online_devices'] = Device.objects.filter(last_seen__gte=timeout).count()
        
        context['pending_pushes'] = UpdatePush.objects.filter(status='pending').count()
        context['recent_updates'] = Update.objects.order_by('-uploaded_at')[:5]
        
        # Device Status Chart
        online_count = context['online_devices']
        offline_count = context['total_devices'] - online_count
        context['device_status_labels'] = ['Online', 'Offline']
        context['device_status_data'] = [online_count, offline_count]
        
        # Deployment History (Last 7 Days)
        seven_days_ago = timezone.now().date() - datetime.timedelta(days=7)
        history = UpdatePush.objects.filter(scheduled_at__date__gte=seven_days_ago) \
            .annotate(date=TruncDate('scheduled_at')) \
            .values('date') \
            .annotate(count=Count('id')) \
            .order_by('date')
        
        push_labels = []
        push_data = []
        for i in range(7, -1, -1):
            date = timezone.now().date() - datetime.timedelta(days=i)
            push_labels.append(date.strftime('%b %d'))
            count = 0
            for entry in history:
                if entry['date'] == date:
                    count = entry['count']
                    break
            push_data.append(count)
        
        context['push_history_labels'] = push_labels
        context['push_history_data'] = push_data
        
        # OS Distribution
        os_dist = Device.objects.values('os_version').annotate(count=Count('id')).order_by('-count')
        context['os_dist_labels'] = [item['os_version'] or 'Unknown' for item in os_dist]
        context['os_dist_data'] = [item['count'] for item in os_dist]
        
        return context

class AuditLogListView(LoginRequiredMixin, ListView):
    model = AuditLog
    template_name = 'dashboard/audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        return AuditLog.objects.select_related('user', 'device').order_by('-timestamp')

class ApplicationInventoryListView(LoginRequiredMixin, ListView):
    model = ApplicationInventory
    template_name = 'dashboard/application_inventory.html'
    context_object_name = 'applications'

    def get_queryset(self):
        # Get all application records that belong to the latest snapshot of their respective device.
        # We use snapshot__device to traverse the relationship from ApplicationInventory to Device.
        queryset = ApplicationInventory.objects.filter(
            snapshot_id=Subquery(
                InventorySnapshot.objects.filter(
                    device=OuterRef('snapshot__device')
                ).order_by('-collected_at').values('id')[:1]
            )
        )

        # Apply search filter
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(display_name__icontains=query) |
                Q(publisher__icontains=query) |
                Q(version__icontains=query)
            )
        
        # Group and aggregate
        queryset = queryset.values(
            'display_name', 'version', 'publisher'
        ).annotate(
            device_count=Count('snapshot__device', distinct=True)
        ).order_by('display_name')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context

class ServiceInventoryListView(LoginRequiredMixin, ListView):
    model = ServiceInventory
    template_name = 'dashboard/service_inventory.html'
    context_object_name = 'services'

    def get_queryset(self):
        # Get all service records that belong to the latest snapshot of their respective device.
        queryset = ServiceInventory.objects.filter(
            snapshot_id=Subquery(
                InventorySnapshot.objects.filter(
                    device=OuterRef('snapshot__device')
                ).order_by('-collected_at').values('id')[:1]
            )
        )

        # Apply search filter
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(display_name__icontains=query) |
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )
        
        # Group and aggregate
        # We group by name, display_name, and startup_type
        queryset = queryset.values(
            'name', 'display_name', 'startup_type'
        ).annotate(
            device_count=Count('snapshot__device', distinct=True),
            running_count=Count('snapshot__device', filter=Q(status='running'), distinct=True),
            stopped_count=Count('snapshot__device', filter=Q(status='stopped'), distinct=True)
        ).order_by('display_name')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context

class DeviceListView(LoginRequiredMixin, ListView):
    model = Device
    template_name = 'dashboard/device_list.html'
    context_object_name = 'devices'

    def get_queryset(self):
        # Annotate with the timestamp of the latest inventory snapshot
        latest_snapshot = InventorySnapshot.objects.filter(
            device=OuterRef('pk')
        ).order_by('-collected_at').values('collected_at')[:1]

        queryset = super().get_queryset().select_related('group').annotate(
            latest_refresh_time=Subquery(latest_snapshot)
        )
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(hostname__icontains=query) |
                Q(ip_address__icontains=query) |
                Q(os_version__icontains=query) |
                Q(inventory_snapshots__applications__display_name__icontains=query) |
                Q(inventory_snapshots__services__display_name__icontains=query) |
                Q(inventory_snapshots__services__name__icontains=query)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['groups'] = DeviceGroup.objects.all()
        return context

class DeviceInventoryView(LoginRequiredMixin, DetailView):
    model = Device
    template_name = 'dashboard/device_inventory.html'
    context_object_name = 'device'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device = self.get_object()
        snapshot = InventorySnapshot.objects.filter(device=device).order_by('-collected_at').first()
        
        context['snapshot'] = snapshot
        if snapshot:
            context['services'] = snapshot.services.all()
            context['applications'] = snapshot.applications.all()
            context['reported_updates'] = snapshot.windows_updates.all().order_by('-installed_at')
        else:
            from inventory.models import ServiceInventory, ApplicationInventory, WindowsUpdate
            context['services'] = ServiceInventory.objects.none()
            context['applications'] = ApplicationInventory.objects.none()
            context['reported_updates'] = WindowsUpdate.objects.none()
        
        # Add deployment history
        context['update_pushes'] = UpdatePush.objects.filter(device=device).select_related('update').order_by('-scheduled_at')
        
        return context

class DeploymentReportListView(LoginRequiredMixin, ListView):
    """View for detailed deployment reporting"""
    model = UpdatePush
    template_name = 'dashboard/deployment_report.html'
    context_object_name = 'pushes'
    paginate_by = 50

    def get_queryset(self):
        queryset = UpdatePush.objects.select_related('update', 'device').order_by('-scheduled_at')
        
        # Filtering
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        update_id = self.request.GET.get('update_id')
        if update_id:
            queryset = queryset.filter(update_id=update_id)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['updates'] = Update.objects.all()
        context['status_choices'] = UpdatePush.STATUS_CHOICES
        return context

class DeploymentReportExportView(LoginRequiredMixin, TemplateView):
    """Export deployment report as CSV"""
    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse
        
        # Get filtered queryset similar to ListView
        queryset = UpdatePush.objects.select_related('update', 'device').order_by('-scheduled_at')
        
        status = request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        update_id = request.GET.get('update_id')
        if update_id:
            queryset = queryset.filter(update_id=update_id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="deployment_report_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Software Name', 'Version', 'Device Hostname', 'IP Address', 'Status', 'Scheduled At', 'Pushed At', 'Completed At', 'Error Message'])

        for push in queryset:
            writer.writerow([
                push.update.name,
                push.update.version,
                push.device.hostname,
                push.device.ip_address,
                push.get_status_display(),
                push.scheduled_at,
                push.pushed_at or '',
                push.completed_at or '',
                push.error_message
            ])

        return response
