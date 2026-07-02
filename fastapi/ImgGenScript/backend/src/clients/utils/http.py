import time
import uuid
import logging
import requests
from typing import Dict, Any, Optional

from backend.src.config.settings import Settings, get_settings

SETTINGS: Settings = get_settings()

class HTTPClient:
    def __init__(
        self,
        base_url: str,
        timeout: int = 15,
        client_id: Optional[str] = None,
        default_headers: Optional[Dict[str, str]] = None,
        max_retries: Optional[int] = 3,
        retry_delay: Optional[float] = 1.0,
        session: Optional[requests.Session] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id or str(uuid.uuid4())
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = session or requests.Session()
        headers = {}
        if default_headers:
            headers.update(default_headers)
        self.session.headers.update(headers)
        self.logger = logger

    def _build_url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            response.raise_for_status()
            return {
                "status": "success",
                "data": response.json() if response.content else None
            }
        except requests.exceptions.HTTPError as e:
            try:
                detail = e.response.text
                print(f"[HTTP ERROR] Status: {e.response.status_code} | Body: {detail}")
                data = e.response.json() if detail else {}
            except Exception as parse_err:
                detail = str(parse_err)
                data = {}
            return {
                "status": "error",
                "message": f"HTTP {e.response.status_code}",
                "detail": detail,
                "data": data
            }
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Connection failed"}
        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Request timed out"}
        except Exception as e:
            return {"status": "error", "message": "Unexpected error", "detail": str(e)}

    def _request_with_retry(self, method: str, url: str, timeout: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        retries = 0
        delay = self.retry_delay
        kwargs.setdefault("timeout", timeout or self.timeout)

        while True:
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code >= 500 or response.status_code == 429:
                    raise requests.exceptions.HTTPError(response=response)
                return self._handle_response(response)

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError) as e:
                
                has_response = hasattr(e, 'response') and e.response is not None
                status_code = e.response.status_code if has_response else 0

                if retries >= self.max_retries:
                    msg = f"Max retries exceeded ({self.max_retries})"
                    return {"status": "error", "message": msg, "detail": str(e)}

                retries += 1

                if self.logger:
                    self.logger.warning(f"Retry {retries}/{self.max_retries} for {url} (error: {status_code or type(e).__name__})")

                time.sleep(delay)
                delay *= 2

    def request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        timeout = kwargs.pop("timeout", self.timeout)
        return self._request_with_retry(method, url, timeout, **kwargs)

    def get(self, endpoint: str, params: Optional[Dict] = None, **kwargs):
        return self.request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[Dict] = None, files: Optional[Dict] = None, **kwargs):
        if files:
            self.session.headers.pop("Content-Type", None)
            return self.request("POST", endpoint, data=data, files=files, **kwargs)

        if data is not None:
            self.session.headers["Content-Type"] = "application/json"
            kwargs.setdefault("json", data)

        return self.request("POST", endpoint, **kwargs)

    def close(self):
        self.session.close()
