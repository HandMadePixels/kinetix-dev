"""
API Views for REST endpoints
"""

from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.models import Device, DeviceGroup, AuditLog
from inventory.models import InventorySnapshot
from updates.models import Update, UpdatePush
from api.serializers import (
    DeviceSerializer, DeviceRegistrationSerializer,
    InventorySubmissionSerializer, UpdateSerializer,
    UpdateUploadSerializer, PushUpdateSerializer,
    UpdatePushSerializer, AuditLogSerializer,
    DeviceGroupSerializer, UpdateStatusSerializer
)


class DeviceRegistrationView(generics.CreateAPIView):
    """
    Public endpoint for device registration.
    Returns JWT token and public key for signature verification.
    """
    
    serializer_class = DeviceRegistrationSerializer
    permission_classes = [AllowAny]
    throttle_scope = 'register'
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        device = result['device']
        
        # Ensure IP is synced with connection IP immediately
        device.update_heartbeat(self.get_client_ip())
        
        # Log registration
        AuditLog.objects.create(
            device=result['device'],
            ip_address=self.get_client_ip(),
            action='device_register',
            severity='info',
            description=f"Device registered: {result['device'].hostname}",
            resource_type='Device',
            resource_id=str(result['device'].id)
        )
        
        return Response({
            'device_id': str(result['device'].id),
            'hostname': result['device'].hostname,
            'token': result['token'],
            'refresh': result['refresh'],
            'public_key': result['public_key']
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class DeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for device CRUD operations.
    Supports filtering, searching, and pagination.
    """
    
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'group', 'hostname']
    search_fields = ['hostname', 'ip_address', 'os_version']
    ordering_fields = ['hostname', 'last_seen', 'registered_at']
    ordering = ['-last_seen']
    
    @action(detail=True, methods=['post'])
    def heartbeat(self, request, pk=None):
        """Update device heartbeat"""
        device = self.get_object()
        ip_address = self.get_client_ip()
        device.update_heartbeat(ip_address)
        
        return Response({
            'status': 'ok',
            'last_seen': device.last_seen
        })
    
    @action(detail=True, methods=['post'])
    def request_refresh(self, request, pk=None):
        """Request a forced inventory refresh from the device"""
        device = self.get_object()
        device.refresh_inventory_requested = True
        device.save(update_fields=['refresh_inventory_requested'])
        
        return Response({'status': 'refresh_requested'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate device"""
        device = self.get_object()
        device.status = 'inactive'
        device.save()
        
        AuditLog.objects.create(
            user=request.user,
            device=device,
            ip_address=self.get_client_ip(),
            action='device_update',
            severity='warning',
            description=f"Device deactivated: {device.hostname}",
            resource_type='Device',
            resource_id=str(device.id)
        )
        
        return Response({'status': 'deactivated'})

    def destroy(self, request, *args, **kwargs):
        """Permanently delete a device and its history"""
        device = self.get_object()
        hostname = device.hostname
        device_id = str(device.id)
        
        response = super().destroy(request, *args, **kwargs)
        
        AuditLog.objects.create(
            user=request.user,
            ip_address=self.get_client_ip(),
            action='device_delete',
            severity='critical',
            description=f"Device permanently deleted: {hostname}",
            resource_type='Device',
            resource_id=device_id
        )
        
        return response
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class UpdateUploadView(generics.CreateAPIView):
    """
    Upload update files with automatic hash computation and signing.
    Triggers async malware scanning.
    """
    
    serializer_class = UpdateUploadSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = 'upload'
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update = serializer.save()
        
        # Log upload
        AuditLog.objects.create(
            user=request.user,
            ip_address=self.get_client_ip(),
            action='update_upload',
            severity='info',
            description=f"Update uploaded: {update.filename} v{update.version}",
            resource_type='Update',
            resource_id=str(update.id),
            metadata={
                'filename': update.filename,
                'version': update.version,
                'size': update.file_size
            }
        )
        
        return Response(
            UpdateSerializer(update).data,
            status=status.HTTP_201_CREATED
        )
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class UpdateDetailView(generics.RetrieveAPIView):
    """
    Retrieve update details including scan results.
    """
    
    queryset = Update.objects.all()
    serializer_class = UpdateSerializer
    permission_classes = [IsAuthenticated]


class PushUpdateView(generics.CreateAPIView):
    """
    Push updates to target devices.
    Creates UpdatePush records and queues Celery tasks.
    """
    
    serializer_class = PushUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        push_records = serializer.save()
        
        # Log push
        update_id = serializer.validated_data['update_id']
        update = Update.objects.get(id=update_id)
        AuditLog.objects.create(
            user=request.user,
            ip_address=self.get_client_ip(),
            action='update_push',
            severity='info',
            description=f"Update pushed: {update.filename} to {len(push_records)} devices",
            resource_type='Update',
            resource_id=str(update.id),
            metadata={
                'target_count': len(push_records),
                'target_hostnames': serializer.validated_data.get('target_hostnames', []),
                'group_ids': serializer.validated_data.get('group_ids', []),
                'push_to_all': serializer.validated_data.get('push_to_all', False)
            }
        )
        
        return Response({
            'status': 'queued',
            'push_count': len(push_records),
            'push_ids': [str(p.id) for p in push_records]
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class InventorySubmissionView(generics.CreateAPIView):
    """
    Receive inventory data from devices.
    Stores services and installed applications.
    """
    
    serializer_class = InventorySubmissionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    
    def create(self, request, *args, **kwargs):
        # Pass the authenticated device to the serializer context
        serializer = self.get_serializer(data=request.data, context={'request': request, 'device': request.user})
        serializer.is_valid(raise_exception=True)
        snapshot = serializer.save()
        
        # Update device heartbeat
        device = snapshot.device
        
        reported_ip = serializer.validated_data.get('ip_address')
        os_version = serializer.validated_data.get('os_version')
        connection_ip = self.get_client_ip()
        
        if os_version:
            device.os_version = os_version
            device.save(update_fields=['os_version'])

        if reported_ip:
            # Trust reported IP for primary address (likely local/VPN IP)
            device.update_heartbeat(reported_ip, update_primary=True)
            # Store connection IP as last_ip if different (for debugging/audit)
            if connection_ip != reported_ip:
                device.last_ip = connection_ip
                device.save(update_fields=['last_ip'])
        else:
            # Fallback to connection IP
            device.update_heartbeat(connection_ip, update_primary=True)
        
        # Log submission
        AuditLog.objects.create(
            device=device,
            ip_address=self.get_client_ip(),
            action='inventory_submit',
            severity='info',
            description=f"Inventory submitted: {device.hostname}",
            resource_type='InventorySnapshot',
            resource_id=str(snapshot.id),
            metadata={
                'service_count': snapshot.services.count(),
                'app_count': snapshot.applications.count()
            }
        )
        
        return Response({
            'status': 'success',
            'snapshot_id': str(snapshot.id),
            'service_count': snapshot.services.count(),
            'app_count': snapshot.applications.count()
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class InventoryDetailView(generics.RetrieveAPIView):
    """
    Retrieve latest inventory for a device by hostname.
    """
    
    permission_classes = [IsAuthenticated]
    lookup_field = 'hostname'
    
    def retrieve(self, request, hostname=None):
        device = get_object_or_404(Device, hostname=hostname)
        snapshot = InventorySnapshot.objects.filter(device=device).order_by('-collected_at').first()
        
        if not snapshot:
            return Response({
                'error': 'No inventory data available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'device': DeviceSerializer(device).data,
            'collected_at': snapshot.collected_at,
            'services': [
                {
                    'name': s.name,
                    'display_name': s.display_name,
                    'status': s.status
                }
                for s in snapshot.services.all()
            ],
            'applications': [
                {
                    'display_name': a.display_name,
                    'version': a.version,
                    'publisher': a.publisher
                }
                for a in snapshot.applications.all()
            ]
        })


class DeviceCommandsView(generics.GenericAPIView):
    """
    Polled by devices to retrieve pending commands (e.g., updates to install).
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        device = request.user
        
        if not isinstance(device, Device):
            return Response({
                'error': 'Device authentication required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Update heartbeat
        # Don't overwrite the primary IP with the connection IP during routine polling
        device.update_heartbeat(self.get_client_ip(), update_primary=False)
        
        # Get pending update pushes
        pending_pushes = UpdatePush.objects.filter(
            device=device,
            status='pending',
            scheduled_at__lte=timezone.now()
        ).select_related('update').order_by('scheduled_at')
        
        commands = []
        
        # Check for forced inventory refresh
        if device.refresh_inventory_requested:
            commands.append({
                'command': 'collect_inventory',
                'description': 'Forced inventory refresh'
            })
            device.refresh_inventory_requested = False
            device.save(update_fields=['refresh_inventory_requested'])

        for push in pending_pushes:
            commands.append({
                'command': 'update',
                'push_id': str(push.id),
                'update_url': request.build_absolute_uri(push.update.file.url),
                'version': push.update.version,
                'description': push.update.description,
                'sha256': push.update.sha256_hash,
                'signature': push.update.signature,
                'filename': push.update.filename
            })
            
            # Mark as in progress
            push.status = 'in_progress'
            push.pushed_at = timezone.now()
            push.save()
        
        return Response({
            'commands': commands
        })
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain view with audit logging"""
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                ip_address=self.get_client_ip(),
                action='login',
                severity='info',
                description=f"User logged in: {request.data.get('username')}",
                metadata={'username': request.data.get('username')}
            )
        else:
            AuditLog.objects.create(
                ip_address=self.get_client_ip(),
                action='failed_auth',
                severity='warning',
                description=f"Failed login attempt: {request.data.get('username')}",
                metadata={'username': request.data.get('username')}
            )
        
        return response
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class CustomTokenRefreshView(TokenRefreshView):
    """Custom JWT token refresh view"""
    pass


class UpdateStatusView(generics.CreateAPIView):
    """
    Endpoint for agents to report installation status of an update.
    """
    
    serializer_class = UpdateStatusSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'device': request.user})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        push = get_object_or_404(UpdatePush, id=data['push_id'])
        
        if data['status'] == 'completed':
            push.mark_completed()
            severity = 'info'
            description = f"Update successfully installed: {push.update.filename}"
        else:
            push.mark_failed(data.get('error_message', 'Unknown error'))
            severity = 'error'
            description = f"Update failed to install: {push.update.filename} - {data.get('error_message')}"
            
        # Update device heartbeat/IP
        push.device.update_heartbeat(self.get_client_ip())

        # Log result
        AuditLog.objects.create(
            device=push.device,
            ip_address=self.get_client_ip(),
            action='update_verify',
            severity=severity,
            description=description,
            resource_type='UpdatePush',
            resource_id=str(push.id)
        )
        
        return Response({'status': 'received'})

    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class UpdateStatusPollView(generics.ListAPIView):
    """
    Endpoint for dashboard to poll for status of specific update pushes.
    """
    serializer_class = UpdatePushSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        push_ids = self.request.query_params.getlist('ids')
        if not push_ids:
            return UpdatePush.objects.none()
        return UpdatePush.objects.filter(id__in=push_ids).select_related('update', 'device')
    
    def get_client_ip(self):
        """Extract client IP from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
