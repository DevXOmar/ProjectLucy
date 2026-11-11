"""Developer-only API reset. Historical ML data is never regenerated."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    request = urllib.request.Request(
        os.getenv('LUCY_API_URL', 'http://127.0.0.1:8000') + '/reset-demo',
        method='POST', headers={'X-Reset-Token': os.getenv('LUCY_RESET_TOKEN', 'local-reset')})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(json.load(response))
    except urllib.error.URLError as exc:
        raise SystemExit(f'Demo reset failed: {exc}. Check the running API and local reset configuration.') from exc
