import time
import uuid
import logging
import requests
from typing import Dict, Any, Optional

from backend.src.config.settings import Settings, get_settings

SETTINGS: Settings = get_settings()

class HTTPClient:
    """
    A wrapper around the `requests` library to standardize API interactions.

    This client provides a consistent interface for making HTTP requests to different
    backend services (like ComfyUI or a custom FastAPI server). It handles session
    management, timeouts, and unified error handling, ensuring that all responses
    are parsed into a predictable dictionary format.

    Key features:
    - Manages a persistent `requests.Session` for connection pooling.
    - Standardizes responses into a `{"status": "success" | "error", "data": ..., "message": ...}` format.
    - Centralizes timeout configuration.
    - Automatically handles JSON and multipart/form-data POST requests.
    """
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
        """Initializes the HTTPClient.

        Args:
            base_url (str): The base URL for all API requests (e.g., "http://127.0.0.1:8000").
            timeout (int, optional): The default timeout in seconds for all requests.
            client_id (str, optional): A unique identifier for the client session. Auto-generated if None.
            default_headers (Dict[str, str], optional): A dictionary of headers to be included in all requests.
            max_retries (int, optional): Maximum number of retries for failed requests.
            retry_delay (float, optional): Base exponential delay between retries in seconds.
            session (requests.Session, optional):
            logger (logging.Logger, optional): 
        """
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
        """
        Constructs full URL from base and endpoint.

        Args:
            endpoint (str): API endpoint path (e.g., "/health").

        Returns:
            Full URL string.
        """
        return f"{self.base_url}{endpoint}"

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Processes HTTP response into unified dictionary format.

        Args:
            response (requests.Response): Raw requests.Response object.

        Returns:
            Dict with "status", "data", "message", and "detail" keys.
        """
        try:
            response.raise_for_status()
            return {
                "status": "success",
                "data": response.json() if response.content else None
            }
        except requests.exceptions.HTTPError as e:
            try:
                detail = e.response.text
                data = e.response.json() if detail else {}
            except:
                data, detail = {}, detail or "No detail"
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
        """
        Sends an HTTP request with exponential backoff retry logic.

        This private method wraps ``requests.Session.request`` and automatically retries
        on transient failures including:
        - Connection errors
        - Timeouts
        - HTTP 5xx server errors
        - HTTP 429 (Too Many Requests)

        Retries use a simple exponential backoff strategy (delay × 2 after each attempt).

        Args:
            method (str): HTTP method to use ("GET", "POST", "PUT", etc.).
            url (str): Full URL for the request.
            timeout (int, optional): Request timeout in seconds. Falls back to ``self.timeout`` if not provided.
            **kwargs: Additional arguments passed directly to ``requests.Session.request``
                    (e.g., ``json``, ``data``, ``headers``, ``params``, etc.).

        Returns:
            Dict[str, Any]: Unified response dictionary as produced by :meth:`_handle_response`.
            On final failure after exhausting retries, returns an error dictionary with
            ``status="error"`` and a descriptive message.
        """
        retries = 0
        delay = self.retry_delay
        kwargs.setdefault("timeout", timeout or self.timeout)

        while True:
            try:
                response = self.session.request(method, url, **kwargs)
                # Treat 5xx and 429 as retryable errors
                if response.status_code >= 500 or response.status_code == 429:
                    raise requests.exceptions.HTTPError(response=response)
                return self._handle_response(response)

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError) as e:
                
                has_response = hasattr(e, 'response') and e.response is not None
                status_code = e.response.status_code if has_response else 0

                # Max retries exceeded → return error
                if retries >= self.max_retries:
                    msg = f"Max retries exceeded ({self.max_retries})"
                    return {"status": "error", "message": msg, "detail": str(e)}

                retries += 1

                if self.logger:
                    self.logger.warning(f"Retry {retries}/{self.max_retries} for {url} (error: {status_code or type(e).__name__})")

                time.sleep(delay)

                delay *= 2

    def request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Sends an HTTP request with unified handling.

        Args:
            method (str): HTTP method ("GET", "POST", etc.).
            endpoint (str): API endpoint path.
            **kwargs: Additional requests.request() arguments.

        Returns:
            Unified response dictionary.
        """
        url = self._build_url(endpoint)
        timeout = kwargs.pop("timeout", self.timeout)
        return self._request_with_retry(method, url, timeout, **kwargs)

    def get(self, endpoint: str, params: Optional[Dict] = None, **kwargs):
        """
        Sends a GET request.

        Args:
            endpoint (str): API endpoint.
            params (Dict, optional): Query parameters.
            **kwargs: Additional request args.

        Returns:
            Unified response.
        """
        return self.request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[Dict] = None, files: Optional[Dict] = None, **kwargs):
        """
        Sends a POST request. Supports JSON or multipart/form-data.

        Args:
            endpoint (str): API endpoint.
            data (Dict, optional): JSON data or form fields.
            files (Dict, optional): File dictionary for multipart.
            **kwargs: Additional args.

        Returns:
            Unified response.
        """
        if files:
            self.session.headers.pop("Content-Type", None)
            return self.request("POST", endpoint, data=data, files=files, **kwargs)

        if data is not None:
            self.session.headers["Content-Type"] = "application/json"
            kwargs.setdefault("json", data)

        return self.request("POST", endpoint, **kwargs)

    def close(self):
        """
        Closes the underlying HTTP session.
        """
        self.session.close()