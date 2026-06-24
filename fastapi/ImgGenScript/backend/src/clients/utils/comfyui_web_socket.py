import json
import threading
import time
import websocket

from typing import Callable, Optional

class ComfyUIWebSocket:
    """
    Listens to ComfyUI WebSocket events for a specific prompt.

    The class supports context-manager usage, optional callbacks,
    a configurable timeout, and graceful shutdown. It tracks node
    execution, progress, completion, and errors via the server’s
    WebSocket endpoint.
    """
    def __init__(
        self,
        server_address: str,
        client_id: str,
        prompt_id: str,
        on_node_change: Optional[Callable[[str, str], None]] = None,
        on_progress: Optional[Callable[[dict], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        timeout: float = 300.0
    ):
        """
        Initializes the WebSocket listener.

        Args:
            server_address: ComfyUI server address (host:port).
            client_id: Unique client identifier.
            prompt_id: ID of the prompt to monitor.
            on_node_change: Callback ``(prompt_id, node_id)`` when a new node starts.
            on_progress: Callback ``(data)`` for any progress message.
            on_complete: Callback called when the prompt finishes.
            on_error: Callback ``(message)`` on error or timeout.
            timeout: Maximum seconds to wait for completion (default 300).
        """
        self.server_address = server_address.rstrip("/")
        self.client_id = client_id
        self.prompt_id = prompt_id
        self.timeout = timeout

        self.on_node_change = on_node_change
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error

        self.ws: Optional[websocket.WebSocket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._completed = False
        self._error_msg: Optional[str] = None

    def __enter__(self) -> 'ComfyUIWebSocket':
        """
        Context-manager entry: opens the WebSocket connection.

        Returns:
            self
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context-manager exit: closes the connection and stops the listener thread.
        """
        self.close()

    def connect(self):
        """
        Establishes the WebSocket connection to the ComfyUI server.

        Raises:
            ConnectionError: If the connection cannot be opened.
        """
        url = f"ws://{self.server_address}/ws?clientId={self.client_id}"
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect(url, timeout=10)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to WebSocket at {url}: {e}")

    def close(self):
        """
        Closes the WebSocket and stops the background listener thread.
        """
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None

    def _listen(self):
        """
        Internal thread target that receives and processes WebSocket messages.

        Handles ``executing`` messages to detect node changes and completion,
        forwards progress messages, and respects the global timeout.
        """
        start_time = time.time()
        current_node = None

        try:
            while not self._stop_event.is_set():
                if self.timeout and (time.time() - start_time) > self.timeout:
                    self._error_msg = "Timeout waiting for workflow completion"
                    if self.on_error:
                        self.on_error(self._error_msg)
                    break

                try:
                    message = self.ws.recv()
                    if not message:
                        continue

                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "executing":
                        node_data = data.get("data", {})
                        node_id = node_data.get("node")
                        prompt_id = node_data.get("prompt_id")

                        if prompt_id == self.prompt_id:
                            if node_id is None:
                                self._completed = True
                                if self.on_complete:
                                    self.on_complete()
                                break
                            elif node_id != current_node and self.on_node_change:
                                current_node = node_id
                                self.on_node_change(self.prompt_id, node_id)

                    elif self.on_progress:
                        self.on_progress(data)

                except websocket.WebSocketTimeoutException:
                    continue
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    self._error_msg = f"Error processing WebSocket message: {e}"
                    if self.on_error:
                        self.on_error(self._error_msg)
                    break

        except Exception as e:
            self._error_msg = f"WebSocket listener crashed: {e}"
            if self.on_error:
                self.on_error(self._error_msg)

    def wait_for_completion(self) -> bool:
        """
        Starts the listener thread and blocks until the prompt finishes,
        an error occurs, or the timeout is reached.

        Returns:
            ``True`` if the prompt completed successfully, ``False`` otherwise.
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected. Use 'with' or call connect() first.")

        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
        self._thread.join(timeout=self.timeout + 10)

        if self._error_msg:
            return False
        return self._completed