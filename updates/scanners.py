"""
Malware scanners: VirusTotal and ClamAV integration
"""

import logging
import hashlib
import time
import requests
import pyclamd
from django.conf import settings

logger = logging.getLogger(__name__)


class VirusTotalScanner:
    """
    VirusTotal API v3 scanner.
    Requires API key in settings.VIRUSTOTAL_API_KEY
    """
    
    API_URL = "https://www.virustotal.com/api/v3"
    
    def __init__(self):
        self.api_key = settings.VIRUSTOTAL_API_KEY
        if not self.api_key:
            raise ValueError("VirusTotal API key not configured")
    
    def scan_file(self, file_path):
        """
        Scan file using VirusTotal API.
        
        Args:
            file_path: Path to file to scan
        
        Returns:
            dict: Scan result with keys: is_clean, threats, detection_ratio, raw_response
        """
        try:
            # Compute file hash
            file_hash = self._compute_hash(file_path)
            
            # Check if file was already scanned
            existing_report = self._get_report(file_hash)
            
            if existing_report:
                return self._parse_report(existing_report)
            
            # Upload and scan file
            scan_id = self._upload_file(file_path)
            
            if not scan_id:
                return None
            
            # Wait for scan to complete (poll every 15 seconds, max 5 minutes)
            for _ in range(20):
                time.sleep(15)
                report = self._get_analysis(scan_id)
                
                if report and report.get('data', {}).get('attributes', {}).get('status') == 'completed':
                    return self._parse_report(report)
            
            logger.warning(f"VirusTotal scan timeout for: {file_path}")
            return None
        
        except Exception as e:
            logger.error(f"VirusTotal scan error: {e}")
            return None
    
    def _compute_hash(self, file_path):
        """Compute SHA256 hash of file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _get_report(self, file_hash):
        """Get existing scan report by hash"""
        try:
            headers = {'x-apikey': self.api_key}
            url = f"{self.API_URL}/files/{file_hash}"
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting VirusTotal report: {e}")
            return None
    
    def _upload_file(self, file_path):
        """Upload file for scanning"""
        try:
            headers = {'x-apikey': self.api_key}
            url = f"{self.API_URL}/files"
            
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(url, headers=headers, files=files, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('id')
            
            logger.error(f"VirusTotal upload failed: {response.status_code}")
            return None
        
        except Exception as e:
            logger.error(f"Error uploading to VirusTotal: {e}")
            return None
    
    def _get_analysis(self, analysis_id):
        """Get analysis results"""
        try:
            headers = {'x-apikey': self.api_key}
            url = f"{self.API_URL}/analyses/{analysis_id}"
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting VirusTotal analysis: {e}")
            return None
    
    def _parse_report(self, report):
        """Parse VirusTotal report"""
        try:
            attributes = report.get('data', {}).get('attributes', {})
            stats = attributes.get('last_analysis_stats', {})
            results = attributes.get('last_analysis_results', {})
            
            malicious = stats.get('malicious', 0)
            suspicious = stats.get('suspicious', 0)
            total = sum(stats.values())
            
            is_clean = (malicious + suspicious) == 0
            
            # Extract threat names
            threats = []
            for engine, result in results.items():
                if result.get('category') in ['malicious', 'suspicious']:
                    threat_name = result.get('result', 'Unknown')
                    threats.append(f"{engine}: {threat_name}")
            
            return {
                'is_clean': is_clean,
                'threats': threats,
                'detection_ratio': f"{malicious + suspicious}/{total}",
                'scanner_version': 'VirusTotal API v3',
                'raw_response': report
            }
        
        except Exception as e:
            logger.error(f"Error parsing VirusTotal report: {e}")
            return None


class ClamAVScanner:
    """
    ClamAV local scanner.
    Requires ClamAV daemon running.
    """
    
    def __init__(self):
        self.host = settings.CLAMAV_HOST
        self.port = settings.CLAMAV_PORT
    
    def scan_file(self, file_path):
        """
        Scan file using ClamAV.
        
        Args:
            file_path: Path to file to scan
        
        Returns:
            dict: Scan result with keys: is_clean, threats, raw_response
        """
        try:
            # Connect to ClamAV daemon
            cd = pyclamd.ClamdNetworkSocket(host=self.host, port=self.port)
            
            # Check if ClamAV is available
            if not cd.ping():
                logger.error("ClamAV daemon not responding")
                return None
            
            # Scan file
            result = cd.scan_file(file_path)
            
            if result is None:
                # File is clean
                return {
                    'is_clean': True,
                    'threats': [],
                    'scanner_version': cd.version(),
                    'raw_response': {}
                }
            
            # File is infected
            threats = []
            for file, (status, virus_name) in result.items():
                if status == 'FOUND':
                    threats.append(virus_name)
            
            return {
                'is_clean': False,
                'threats': threats,
                'scanner_version': cd.version(),
                'raw_response': result
            }
        
        except Exception as e:
            logger.error(f"ClamAV scan error: {e}")
            return None
