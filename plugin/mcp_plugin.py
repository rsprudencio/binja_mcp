import binaryninja as bn
import json
import socket
import struct
import threading
import traceback
import time
from typing import Optional

from . import tools

PLUGIN_NAME = "MCP Server"
PLUGIN_VERSION = "1.0"
PLUGIN_AUTHOR = "raph0x88"

# Default configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000


class BinjaSyncWrapper:
    """Wrapper class for getting return values from background tasks"""

    def __init__(self):
        self.result = None

    def __call__(self, func, *args, **kwargs):
        self.result = func(*args, **kwargs)
        return self.result


class BinjaMCPServer:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.thread = None
        self.client_counter = 0
        self.current_view: Optional[bn.BinaryView] = None

    def start(self):
        """Start Socket Server"""
        if self.running:
            print("MCP Server already running")
            return False

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(
                1.0
            )  # Set timeout to allow server to respond to stop requests

            self.running = True
            self.thread = threading.Thread(target=self.server_loop)
            self.thread.daemon = True
            self.thread.start()

            print(f"MCP Server started on {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to start MCP Server: {str(e)}")
            traceback.print_exc()
            return False

    def stop(self):
        """Stop Socket Server"""
        if not self.running:
            print("MCP Server is not running")
            return

        print("Stopping MCP Server...")
        self.running = False

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                print(f"Error closing server socket: {str(e)}")
            self.server_socket = None

        if self.thread:
            try:
                self.thread.join(2.0)  # Wait for thread to end, max 2 seconds
            except Exception as e:
                print(f"Error joining server thread: {str(e)}")
            self.thread = None

        print("MCP Server stopped")

    def send_message(self, client_socket, data: bytes) -> None:
        """Send message with length prefix"""
        length = len(data)
        length_bytes = struct.pack("!I", length)  # 4-byte length prefix
        client_socket.sendall(length_bytes + data)

    def receive_message(self, client_socket) -> bytes:
        """Receive message with length prefix"""
        # Receive 4-byte length prefix
        length_bytes = self.receive_exactly(client_socket, 4)
        if not length_bytes:
            raise ConnectionError("Connection closed")

        length = struct.unpack("!I", length_bytes)[0]

        # Receive message body
        data = self.receive_exactly(client_socket, length)
        return data

    def receive_exactly(self, client_socket, n: int) -> bytes:
        """Receive exactly n bytes of data"""
        data = b""
        while len(data) < n:
            chunk = client_socket.recv(min(n - len(data), 4096))
            if not chunk:  # Connection closed
                raise ConnectionError("Connection closed, cannot receive complete data")
            data += chunk
        return data

    def server_loop(self):
        """Server main loop"""
        bn.log_info("Server loop started", "TESTE")
        while self.running:
            try:
                # Use timeout receive to periodically check running flag
                try:
                    client_socket, client_address = self.server_socket.accept()
                    self.client_counter += 1
                    client_id = self.client_counter
                    print(f"Client #{client_id} connected from {client_address}")

                    # Handle client requests - use threads to support multiple clients
                    client_thread = threading.Thread(
                        target=self.handle_client, args=(client_socket, client_id)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    # Timeout is just for checking running flag periodically
                    continue
                except OSError as e:
                    if self.running:  # Only print error when server is running
                        if (
                            e.errno == 9
                        ):  # Bad file descriptor, usually means socket was closed
                            print("Server socket was closed")
                            break
                        print(f"Socket error: {str(e)}")
                except Exception as e:
                    if self.running:  # Only print error when server is running
                        print(f"Error accepting connection: {str(e)}")
                        traceback.print_exc()
            except Exception as e:
                if self.running:
                    print(f"Error in server loop: {str(e)}")
                    traceback.print_exc()
                time.sleep(1)  # Avoid high CPU usage

        print("Server loop ended")

    def handle_client(self, client_socket, client_id):
        """Handle client requests"""
        try:
            # Set timeout
            client_socket.settimeout(30)

            while self.running:
                try:
                    # Receive message
                    data = self.receive_message(client_socket)

                    # Parse request
                    request = json.loads(data.decode("utf-8"))
                    request_type = request.get("type")
                    request_data = request.get("data", {})
                    request_id = request.get("id", "unknown")
                    request_count = request.get("count", -1)

                    print(
                        f"Client #{client_id} request: {request_type}, ID: {request_id}, Count: {request_count}"
                    )

                    # Handle different request types
                    response = {
                        "id": request_id,  # Return same request ID
                        "count": request_count,  # Return same request count
                    }

                    tool = self.resolve(request_type)
                    if tool:
                        response.update(tool(self.current_view, **request_data))
                    else:
                        bn.log_error(f"Unknown request type: {request_type}")
                        response["error"] = f"Unknown request type: {request_type}"

                    # Verify response is valid
                    if not isinstance(response, dict):
                        bn.log_debug(
                            f"Response is not a dictionary: {type(response).__name__}"
                        )
                        response = {
                            "id": request_id,
                            "count": request_count,
                            "error": f"Internal server error: response is not a dictionary but {type(response).__name__}",
                        }

                    # Ensure all values in response are serializable
                    for key, value in list(response.items()):
                        if value is None:
                            response[key] = "null"
                        elif not isinstance(
                            value, (str, int, float, bool, list, dict, tuple)
                        ):
                            bn.log_error(
                                f"Response key '{key}' has non-serializable type: {type(value).__name__}"
                            )
                            response[key] = str(value)

                    # Send response
                    response_json = json.dumps(response).encode("utf-8")
                    self.send_message(client_socket, response_json)
                    bn.log_info(
                        f"Sent response to client #{client_id}, ID: {request_id}, Count: {request_count}"
                    )

                except ConnectionError as e:
                    bn.log_debug(f"Connection with client #{client_id} lost: {str(e)}")
                    return
                except socket.timeout:
                    bn.log_debug(f"Socket timeout with client #{client_id}")
                    continue
                except json.JSONDecodeError as e:
                    bn.log_error(f"Invalid JSON request from client #{client_id}: {str(e)}")
                    continue
                except Exception as e:
                    bn.log_error(f"Error handling client #{client_id} request: {str(e)}")
                    traceback.print_exc()
                    try:
                        error_response = {
                            "id": request_id,
                            "count": request_count,
                            "error": str(e),
                        }
                        self.send_message(
                            client_socket, json.dumps(error_response).encode("utf-8")
                        )
                    except:
                        pass
        finally:
            try:
                client_socket.close()
            except:
                pass
            bn.log_debug(f"Client #{client_id} connection closed")

    def resolve(self, function_name):
        """
        Validate if a function exists in the tools module and return it.
        
        Args:
            function_name: The name of the function to look for
            
        Returns:
            The function object if found
            
        Raises:
            ValueError: If the function doesn't exist or isn't callable
        """
        # Check if the attribute exists in the module
        if hasattr(tools, function_name):
            func = getattr(tools, function_name)
            
            # Verify it's actually a function
            if callable(func):
                return func
            else:
                raise ValueError(f"{function_name} exists but is not callable")
        else:
            raise ValueError(f"Function {function_name} not found in tools module")
