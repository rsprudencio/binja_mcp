import binaryninja as bn
from .plugin.mcp_plugin import BinjaMCPServer, PLUGIN_NAME, PLUGIN_VERSION

PLUGIN_GROUP = "MCP Server"
server_instance = None


def update_view(_bv: bn.BinaryView):
    global server_instance
    if not server_instance:
        bn.log_debug(f"{PLUGIN_NAME} is not running")
        return
    server_instance.current_view = _bv
    bn.log_debug(f"{PLUGIN_NAME} - updated current view: {_bv.file.filename}")


bn.BinaryViewEvent.register(
    bn.BinaryViewEventType.BinaryViewInitialAnalysisCompletionEvent, update_view
)


def init_plugin(bv: bn.BinaryView):
    """Initialize the plugin"""
    global server_instance
    if not server_instance:
        server_instance = BinjaMCPServer()
        server_instance.current_view = bv
        if server_instance.start():
            bn.log_info(f"{PLUGIN_NAME} v{PLUGIN_VERSION} started successfully")
        else:
            bn.log_error(f"Failed to start {PLUGIN_NAME}")


def stop_plugin(bv: bn.BinaryView):
    """Stop the plugin"""
    global server_instance
    if server_instance:
        server_instance.stop()
        server_instance = None
        bn.log_info(f"{PLUGIN_NAME} stopped")


bn.PluginCommand.register(
    f"{PLUGIN_GROUP}\Start {PLUGIN_NAME}",
    "Start the MCP Server for Binary Ninja",
    init_plugin,
)


bn.PluginCommand.register(
    f"{PLUGIN_GROUP}\Stop {PLUGIN_NAME}",
    "Stop the MCP Server for Binary Ninja",
    stop_plugin,
)
