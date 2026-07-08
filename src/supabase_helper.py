import os
from pathlib import Path
from dotenv import load_dotenv
import httpx
from urllib.parse import urlparse

load_dotenv()

URL: str = os.getenv("SUPABASE_URL")
KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET")

def upload_to_supabase(local_file_path, remote_destination_path):
    """Streams a local binary payload file directly to the Supabase Storage cluster."""
    if not URL or not KEY or not BUCKET:
        print("Supabase configuration missing from environment.")
        return False

    local_path = Path(local_file_path).resolve()
    if not local_path.exists():
        return False

    # Normalize remote paths to standard web forward slashes
    clean_remote_path = str(remote_destination_path).replace("\\", "/").lstrip("/")
    
    # Isolate root scheme and domain to ensure proper routing proxy bypass
    parsed_url = urlparse(URL)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    endpoint = f"{base_url}/storage/v1/object/{BUCKET}/{clean_remote_path}"

    headers = {
        "Authorization": f"Bearer {KEY}",
        "apiKey": KEY,
        "x-upsert": "true",
        "Content-Type": "application/json"
    }

    try:
        with open(local_path, 'rb') as f:
            file_data = f.read()

        response = httpx.post(endpoint, headers=headers, content=file_data)
        if response.status_code in [200, 201]:
            print(f"Cloud Upload Successful: {clean_remote_path}")
            return True
        
        print(f"Cloud Upload Rejected (HTTP {response.status_code}): {response.text}")
        return False
    except Exception as e:
        print(f"Network error streaming to Supabase: {e}")
        return False