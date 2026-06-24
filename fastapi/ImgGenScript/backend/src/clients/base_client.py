import uuid
import logging
from abc import ABC
from typing import Optional
from backend.src.clients.utils.http import HTTPClient

class BaseAPIClient(ABC):
    """
    Abstract base client for API interactions.

    Provides shared HTTP client and configuration for FastAPI and ComfyUI clients.
    """
    def __init__(
        self,
        server_address: str,
        timeout: Optional[int] = 15,
        client_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initializes the base client with server address and HTTP client.

        Args:
            server_address (str): Host and port (e.g., "127.0.0.1:8000").
            timeout (int, optional): Default request timeout in seconds.
            client_id (str, optional): Optional client identifier.
            logger (logging.Logger, optional): Logger for recording events.
        """
        self.server_address = server_address.rstrip("/")
        self.client_id = client_id or str(uuid.uuid4())
        self.timeout = timeout
        self.http = HTTPClient(
            base_url=f"http://{self.server_address}",
            timeout=timeout,
            client_id=self.client_id,
            logger=logger
        )

    def close(self):
        """
        Closes the HTTP session.
        """
        self.http.close()