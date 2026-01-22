from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
import datetime
from core.models import Device, AuditLog
from updates.models import Update, UpdatePush
from inventory.models import InventorySnapshot, ApplicationInventory

class DashboardLogoutView(LogoutView):
    next_page = reverse_lazy('admin:login')

class UpdateCenterView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/update_center.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_updates'] = Update.objects.filter(scan_status__in=['clean', 'pending']).order_by('-uploaded_at')
        context['devices'] = Device.objects.filter(status='active').order_by('hostname')
        context['device_count'] = context['devices'].count()
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
        
        # Recent Logs
        context['recent_logs'] = AuditLog.objects.order_by('-timestamp')[:10]
        
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

class ApplicationInventoryListView(LoginRequiredMixin, ListView):
    model = ApplicationInventory
    template_name = 'dashboard/application_inventory.html'
    context_object_name = 'applications'

    def get_queryset(self):
        # Get latest snapshot ID for each device
        latest_snapshots = InventorySnapshot.objects.values('device').annotate(
            latest_id=Max('id')
        ).values_list('latest_id', flat=True)
        
        # Base queryset filtered to latest snapshots only
        queryset = ApplicationInventory.objects.filter(
            snapshot_id__in=latest_snapshots
        )

        # Apply search filter BEFORE grouping/aggregation
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

class DeviceListView(LoginRequiredMixin, ListView):
    model = Device
    template_name = 'dashboard/device_list.html'
    context_object_name = 'devices'

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(hostname__icontains=query) |
                Q(ip_address__icontains=query) |
                Q(os_version__icontains=query) |
                Q(inventory_snapshots__applications__display_name__icontains=query)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context

class DeviceInventoryView(LoginRequiredMixin, DetailView):
    model = Device
    template_name = 'dashboard/device_inventory.html'
    context_object_name = 'device'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device = self.get_object()
        snapshot = InventorySnapshot.objects.filter(device=device).order_by('-collected_at').first()
        
        if snapshot:
            context['snapshot'] = snapshot
            context['services'] = snapshot.services.all()
            context['applications'] = snapshot.applications.all()
        
        return context
