"""
Binary Ninja MCP Server implementation
"""
import asyncio
import json
import socket
import struct
import logging
import re
from typing import Dict, Any, List, Optional, ClassVar

from mcp.server import Server
from mcp.types import TextContent, Tool
from mcp.server.stdio import stdio_server
from pydantic import BaseModel

# Default configuration - must match plugin's configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000

TOOLS = []
logger = logging.getLogger(__name__)


class ToolModel(BaseModel):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "Config"):
            cls.Config = type("Config", (), {})
        
        cls.Config.name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        cls.Config.description = getattr(cls, "description")
        TOOLS.append(cls)

class GetFunctions(ToolModel):
    description: ClassVar[str] = "Get all functions in the current binary"
    limit: int = 100
    cursor: Optional[str] = None

class GetBinaryInfo(ToolModel):
    description: ClassVar[str] = "Get binary information such as architecture, size, segments, etc."

class GetFunctionAssembly(ToolModel):
    description: ClassVar[str] = "Get assembly code for a function by name"
    function_name: str

class GetFunctionDecompiled(ToolModel):
    description: ClassVar[str] = "Get decompiled code for a function by name"
    function_name: str

class GetSymbolsByName(ToolModel):
    description: ClassVar[str] = "Get information about a symbol by name"
    symbol_name: str

class GetCurrentFunctionAssembly(ToolModel):
    description: ClassVar[str] = (
        "Get assembly code for the function at the current cursor position"
    )

class GetCurrentFunctionDecompiled(ToolModel):
    description: ClassVar[str] = (
        "Get decompiled code for the function at the current cursor position"
    )

class RenameFunction(ToolModel):
    description: ClassVar[str] = "Rename a function"
    function_name: str
    new_name: str

class RenameCurrentFunction(ToolModel):
    description: ClassVar[str] = "Rename the current function"
    new_name: str
    
class RenameFunctionVariable(ToolModel):
    description: ClassVar[str] = "Rename a variable in a function"
    function_name: str
    variable_name: str
    new_name: str

class SetFunctionVariableType(ToolModel):
    description: ClassVar[str] = "Set the type of a variable in a function"
    function_name: str
    variable_name: str
    new_type: str

class SetCommentAt(ToolModel):
    description: ClassVar[str] = "Set a comment at an address"
    address: int
    comment: str


class BinjaPluginClient:
    """Client for communicating with the Binary Ninja plugin"""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.socket = None
        self.request_counter = 0
        self.connected = False
        self.timeout = 5  # 5 second timeout

    def connect(self) -> bool:
        """Connect to the Binary Ninja plugin"""
        try:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.connected = True
            return True
        except Exception as e:
            print(f"Failed to connect to Binary Ninja plugin: {str(e)}")
            self.connected = False
            self.socket = None
            return False

    def ensure_connection(self) -> bool:
        """Ensure there is a connection to the plugin"""
        if not self.connected:
            return self.connect()
        try:
            # Test if connection is still alive
            self.socket.settimeout(1)
            self.socket.send(b"")
            return True
        except:
            self.connected = False
            return self.connect()

    def disconnect(self):
        """Disconnect from the Binary Ninja plugin"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            self.connected = False

    def send_message(self, data: bytes) -> None:
        """Send message with length prefix"""
        if not self.ensure_connection():
            raise ConnectionError("Cannot connect to Binary Ninja plugin")

        try:
            length = len(data)
            length_bytes = struct.pack("!I", length)  # 4-byte length prefix
            self.socket.settimeout(self.timeout)
            self.socket.sendall(length_bytes + data)
        except socket.timeout:
            self.disconnect()
            raise ConnectionError(
                "Timeout while sending message to Binary Ninja plugin"
            )
        except Exception as e:
            self.disconnect()
            raise ConnectionError(f"Error sending message: {str(e)}")

    def receive_message(self) -> bytes:
        """Receive message with length prefix"""
        if not self.ensure_connection():
            raise ConnectionError("Cannot connect to Binary Ninja plugin")

        try:
            # Receive 4-byte length prefix
            length_bytes = self.receive_exactly(4)
            if not length_bytes:
                raise ConnectionError("Connection closed")

            length = struct.unpack("!I", length_bytes)[0]

            # Receive message body
            data = self.receive_exactly(length)
            return data
        except socket.timeout:
            self.disconnect()
            raise ConnectionError(
                "Timeout while receiving message from Binary Ninja plugin"
            )
        except Exception as e:
            self.disconnect()
            raise ConnectionError(f"Error receiving message: {str(e)}")

    def receive_exactly(self, n: int) -> bytes:
        """Receive exactly n bytes of data"""
        if not self.ensure_connection():
            raise ConnectionError("Cannot connect to Binary Ninja plugin")

        data = b""
        try:
            self.socket.settimeout(self.timeout)
            while len(data) < n:
                chunk = self.socket.recv(min(n - len(data), 4096))
                if not chunk:  # Connection closed
                    raise ConnectionError(
                        "Connection closed, cannot receive complete data"
                    )
                data += chunk
            return data
        except socket.timeout:
            self.disconnect()
            raise ConnectionError(
                "Timeout while receiving data from Binary Ninja plugin"
            )
        except Exception as e:
            self.disconnect()
            raise ConnectionError(f"Error receiving data: {str(e)}")

    def send_request(
        self, request_type: str, request_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Send a request to the Binary Ninja plugin and get the response"""
        try:
            if not self.ensure_connection():
                return {"error": "Cannot connect to Binary Ninja plugin"}

            self.request_counter += 1
            request = {
                "type": request_type,
                "data": request_data or {},
                "id": f"mcp-{self.request_counter}",
                "count": self.request_counter,
            }

            # Send request
            request_json = json.dumps(request).encode("utf-8")
            self.send_message(request_json)

            # Receive response
            response_data = self.receive_message()
            response = json.loads(response_data.decode("utf-8"))

            return response
        except Exception as e:
            print(f"Error communicating with Binary Ninja plugin: {str(e)}")
            self.disconnect()  # Reset connection on error
            return {"error": str(e)}


class BinjaTools:
    """MCP Tools for interacting with Binary Ninja"""
    def __init__(self, client: BinjaPluginClient):
        self.client = client

    def dispatch(self, tool: str, arguments: Dict[str, Any]) -> str:
        """Dispatch a tool call to the Binary Ninja plugin"""
        response = self.client.send_request(tool, arguments)
        return json.dumps(response, indent=4)


async def serve() -> None:
    """MCP server main entry point"""
    # logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    server = Server("Binary Ninja MCP Server")

    # Create communicator and try to connect
    binja_communicator = BinjaPluginClient()
    logger.info("Attempting to connect to Binary Ninja plugin...")

    if binja_communicator.connect():
        logger.info("Successfully connected to Binary Ninja plugin")
    else:
        logger.warning(
            "Initial connection to Binary Ninja plugin failed, will retry on request"
        )

    # Create functions instance with persistent connection
    binja_tools = BinjaTools(binja_communicator)
    
    tools = []
    for tool in TOOLS:
        tools.append(
            Tool(
                name=tool.Config.name,
                description=tool.Config.description,
                inputSchema=tool.model_json_schema(),
                returns=TextContent.model_json_schema(),
            )
    )

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List supported tools"""
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> List[TextContent]:
        """Call tool and handle results"""
        # Ensure connection
        if (
            not binja_communicator.connected
            and not binja_communicator.ensure_connection()
        ):
            return [
                TextContent(
                    type="text",
                    text=f"Error: Cannot connect to Binary Ninja plugin. Please ensure the plugin is running.",
                )
            ]

        try:
            response = binja_tools.dispatch(name, arguments)

            if response:
                return [TextContent(type="text", text=response)]
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            logger.error(f"Error executing tool: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)


def main():
    print(f"Starting MCP server at {DEFAULT_HOST}:{DEFAULT_PORT}")
    asyncio.run(serve())

if __name__ == "__main__":
    main()
