"""
DRF Serializers for API endpoints
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from core.models import Device, DeviceGroup, AuditLog, RemoteCommand
from inventory.models import ServiceInventory, ApplicationInventory
from updates.models import Update, UpdatePush


class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for Device model"""
    
    is_online = serializers.SerializerMethodField()
    group_name = serializers.CharField(source='group.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Device
        fields = [
            'id', 'hostname', 'ip_address', 'os_version', 'status',
            'is_online', 'group', 'group_name', 'registered_at',
            'last_seen', 'last_ip', 'notes', 'current_user',
            'last_boot_time', 'uptime'
        ]
        read_only_fields = ['id', 'registered_at', 'last_seen', 'last_ip']
    
    def get_is_online(self, obj):
        return obj.is_online()


class DeviceRegistrationSerializer(serializers.Serializer):
    """Serializer for device registration"""
    
    hostname = serializers.CharField(max_length=255)
    ip_address = serializers.IPAddressField()
    os_version = serializers.CharField(max_length=255)
    device_id = serializers.UUIDField(required=False, allow_null=True)
    
    def create(self, validated_data):
        """Create or update device and generate JWT token"""
        from rest_framework_simplejwt.tokens import RefreshToken
        from core.models import RSAKeyPair
        
        hostname = validated_data.pop('hostname')
        device_id = validated_data.pop('device_id', None)
        
        # Security: Check if hostname is already registered
        existing_device = Device.objects.filter(hostname=hostname).first()
        
        if existing_device:
            # If device is blocked/inactive, don't allow re-registration
            if existing_device.status == 'blocked':
                raise serializers.ValidationError("This device has been blocked and cannot register.")
            
            # If ID is provided, it must match
            if device_id and str(existing_device.id) != str(device_id):
                raise serializers.ValidationError("Device ID mismatch for this hostname.")
            
            # Update existing
            for attr, value in validated_data.items():
                setattr(existing_device, attr, value)
            existing_device.save()
            device = existing_device
        else:
            # New device
            device = Device.objects.create(
                hostname=hostname,
                **validated_data
            )
        
        # Generate JWT token for device
        refresh = RefreshToken.for_user(device)
        access_token = str(refresh.access_token)
        
        # Store encrypted token
        device.auth_token = access_token
        device.save()
        
        # Get public key for signature verification
        keypair = RSAKeyPair.get_keypair()
        
        return {
            'device': device,
            'token': access_token,
            'refresh': str(refresh),
            'public_key': keypair.public_key
        }


class ServiceInventorySerializer(serializers.ModelSerializer):
    """Serializer for service inventory"""
    
    class Meta:
        model = ServiceInventory
        fields = ['name', 'display_name', 'status']


class ApplicationInventorySerializer(serializers.ModelSerializer):
    """Serializer for installed application inventory"""
    
    class Meta:
        model = ApplicationInventory
        fields = ['display_name', 'version', 'publisher', 'uninstall_string']


class InventorySubmissionSerializer(serializers.Serializer):
    """Serializer for inventory submission from devices"""
    
    services = ServiceInventorySerializer(many=True)
    installed_apps = ApplicationInventorySerializer(many=True)
    ip_address = serializers.IPAddressField(required=False)
    os_version = serializers.CharField(required=False, max_length=255)
    current_user = serializers.CharField(required=False, max_length=255, allow_null=True)
    last_boot_time = serializers.DateTimeField(required=False, allow_null=True)
    uptime = serializers.CharField(required=False, max_length=100, allow_null=True)
    
    def create(self, validated_data):
        """Store inventory data"""
        from inventory.models import InventorySnapshot
        
        device = self.context.get('device')
        if not device or not isinstance(device, Device):
            # Fallback for manual hostname if not using device auth (shouldn't happen with new views)
            hostname = self.initial_data.get('hostname')
            device = Device.objects.get(hostname=hostname)
        
        # Create snapshot
        snapshot = InventorySnapshot.objects.create(device=device)
        
        # Create service records using bulk_create
        service_objs = [
            ServiceInventory(snapshot=snapshot, **service_data)
            for service_data in validated_data['services']
        ]
        ServiceInventory.objects.bulk_create(service_objs)
        
        # Create application records using bulk_create
        app_objs = [
            ApplicationInventory(snapshot=snapshot, **app_data)
            for app_data in validated_data['installed_apps']
        ]
        ApplicationInventory.objects.bulk_create(app_objs)
        
        return snapshot


class UpdateSerializer(serializers.ModelSerializer):
    """Serializer for Update model"""
    
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = Update
        fields = [
            'id', 'name', 'file', 'filename', 'version', 'description',
            'sha256_hash', 'signature', 'file_size', 'file_size_mb',
            'scan_status', 'scan_result', 'uploaded_at', 'uploaded_by',
            'uploaded_by_username'
        ]
        read_only_fields = [
            'id', 'filename', 'sha256_hash', 'signature', 'file_size',
            'scan_status', 'scan_result', 'uploaded_at'
        ]
    
    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)


class UpdateUploadSerializer(serializers.Serializer):
    """Serializer for update file upload"""
    
    file = serializers.FileField()
    name = serializers.CharField(max_length=100, required=False, default='Software')
    version = serializers.CharField(max_length=50)
    description = serializers.CharField()
    sha256_hash = serializers.CharField(max_length=64, required=False, allow_blank=True)
    signature = serializers.CharField(required=False, allow_blank=True)
    
    def validate_file(self, value):
        """Validate file extension and size"""
        from django.conf import settings
        import os
        
        # Check extension
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in settings.ALLOWED_UPDATE_EXTENSIONS:
            raise serializers.ValidationError(
                f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_UPDATE_EXTENSIONS)}"
            )
        
        # Check size
        max_size = settings.MAX_UPLOAD_SIZE
        if value.size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File too large. Maximum size: {max_mb}MB"
            )
        
        return value
    
    def create(self, validated_data):
        """Create update record. Automatic hashing/signing happens in model.save()"""
        file = validated_data['file']
        
        # Create update record
        # Note: Model.save() handles automatic hashing and signing if these are missing
        update = Update.objects.create(
            file=file,
            name=validated_data.get('name', 'Software'),
            filename=file.name,
            version=validated_data['version'],
            description=validated_data['description'],
            file_size=file.size,
            sha256_hash=validated_data.get('sha256_hash', '') or '',
            signature=validated_data.get('signature', '') or '',
            uploaded_by=self.context['request'].user
        )
        
        # The model's save() method will have triggered everything else
        return update


class PushUpdateSerializer(serializers.Serializer):
    """Serializer for pushing updates to devices"""
    
    update_id = serializers.UUIDField()
    target_hostnames = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        allow_empty=True,
        default=list
    )
    group_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        default=list
    )
    push_to_all = serializers.BooleanField(required=False, default=False)
    schedule = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate_update_id(self, value):
        """Ensure update exists and is verified"""
        try:
            update = Update.objects.get(id=value)
            if update.scan_status != 'clean':
                raise serializers.ValidationError(
                    "Update must pass malware scan before pushing"
                )
        except Update.DoesNotExist:
            raise serializers.ValidationError("Update not found")
        return value
    
    def validate_target_hostnames(self, value):
        """Ensure all devices exist if provided"""
        if not value:
            return value
        existing = Device.objects.filter(hostname__in=value).values_list('hostname', flat=True)
        missing = set(value) - set(existing)
        if missing:
            raise serializers.ValidationError(
                f"Devices not found: {', '.join(missing)}"
            )
        return value
    
    def validate(self, data):
        """Ensure at least one target is specified"""
        if not any([data.get('target_hostnames'), data.get('group_ids'), data.get('push_to_all')]):
            raise serializers.ValidationError(
                "At least one target (hostnames, groups, or 'push_to_all') must be specified."
            )
        return data

    def create(self, validated_data):
        """Create update push tasks"""
        from updates.tasks import push_update_to_device
        from django.utils import timezone
        
        update = Update.objects.get(id=validated_data['update_id'])
        schedule = validated_data.get('schedule')
        
        # Resolve target devices
        device_ids = set()
        
        if validated_data.get('push_to_all'):
            device_ids.update(Device.objects.values_list('id', flat=True))
        else:
            hostnames = validated_data.get('target_hostnames', [])
            if hostnames:
                device_ids.update(Device.objects.filter(
                    hostname__in=hostnames
                ).values_list('id', flat=True))
            
            group_ids = validated_data.get('group_ids', [])
            if group_ids:
                device_ids.update(Device.objects.filter(
                    group__id__in=group_ids
                ).values_list('id', flat=True))
        
        devices = Device.objects.filter(id__in=device_ids)
        
        push_records = []
        now = timezone.now()
        for device in devices:
            # Avoid duplicate pending pushes for the same update/device
            push, created = UpdatePush.objects.update_or_create(
                update=update,
                device=device,
                defaults={
                    'status': 'pending',
                    'scheduled_at': schedule or now,
                    'pushed_by': self.context['request'].user,
                    'pushed_at': None,
                    'completed_at': None,
                    'error_message': ''
                }
            )
            push_records.append(push)
            
            # Queue Celery task
            try:
                if schedule:
                    push_update_to_device.apply_async(
                        args=[str(push.id)],
                        eta=schedule
                    )
                else:
                    push_update_to_device.delay(str(push.id))
            except Exception as e:
                # Log error but don't fail the request since the DB record is already created
                # and will be picked up by the agent polling or manual retry
                import logging
                logging.getLogger(__name__).error(f"Failed to queue celery task for push {push.id}: {e}")
        
        return push_records


class UpdatePushSerializer(serializers.ModelSerializer):
    """Serializer for UpdatePush model"""
    update_filename = serializers.CharField(source='update.filename', read_only=True)
    device_hostname = serializers.CharField(source='device.hostname', read_only=True)
    pushed_by_username = serializers.CharField(source='pushed_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = UpdatePush
        fields = [
            'id', 'update', 'update_filename', 'device', 'device_hostname',
            'status', 'scheduled_at', 'pushed_at', 'completed_at',
            'error_message', 'retry_count', 'pushed_by', 'pushed_by_username'
        ]
        read_only_fields = ['id', 'pushed_at', 'completed_at', 'error_message', 'retry_count']


class DeviceGroupSerializer(serializers.ModelSerializer):
    """Serializer for device groups"""
    
    device_count = serializers.IntegerField(read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = DeviceGroup
        fields = ['id', 'name', 'description', 'device_count', 'created_at', 'created_by', 'created_by_username']
        read_only_fields = ['id', 'created_at']


class UpdateStatusSerializer(serializers.Serializer):
    """Serializer for reporting update status from agents"""
    push_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=['completed', 'failed'])
    error_message = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_push_id(self, value):
        """Ensure push record belongs to the authenticated device"""
        device = self.context.get('device')
        try:
            push = UpdatePush.objects.get(id=value)
            if device and isinstance(device, Device) and push.device != device:
                raise serializers.ValidationError("This update push does not belong to this device")
        except UpdatePush.DoesNotExist:
            raise serializers.ValidationError("Update push not found")
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model"""
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    device_hostname = serializers.CharField(source='device.hostname', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'timestamp', 'user', 'username', 'device', 'device_hostname',
            'ip_address', 'user_agent', 'action', 'severity', 'description',
            'resource_type', 'resource_id', 'metadata'
        ]
        read_only_fields = ['id', 'timestamp']

class RemoteCommandSerializer(serializers.ModelSerializer):
    """Serializer for RemoteCommand model"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = RemoteCommand
        fields = [
            'id', 'device', 'command_type', 'payload', 'status', 
            'result_message', 'created_at', 'executed_at', 
            'created_by', 'created_by_username'
        ]
        read_only_fields = ['id', 'created_at', 'executed_at']