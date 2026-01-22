from core.models import SystemConfig, Device

def system_config(request):
    """Add system config to template context"""
    config = SystemConfig.get_config()
    return {
        'system_config': config,
        'server_url': config.server_url,
    }

def device_stats(request):
    """Add device statistics to template context"""
    if not request.user.is_authenticated:
        return {}
    
    total_devices = Device.objects.count()
    online_devices = Device.objects.filter(status='active').count()
    
    return {
        'total_devices': total_devices,
        'online_devices': online_devices,
    }
