import hashlib
import base64
import requests

urls = [
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css",
    "https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css",
    "https://code.jquery.com/jquery-3.7.0.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js",
    "https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js",
    "https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js",
    "https://cdn.jsdelivr.net/npm/chart.js"
]

def get_sri_hash(url):
    response = requests.get(url)
    if response.status_code == 200:
        hash_val = hashlib.sha384(response.content).digest()
        hash_base64 = base64.b64encode(hash_val).decode('utf-8')
        return f"sha384-{hash_base64}"
    return "Error"

for url in urls:
    print(f"{url}: {get_sri_hash(url)}")
