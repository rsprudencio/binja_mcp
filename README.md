# Binary Ninja MCP Server

A Model Context Protocol server for Binary Ninja interaction and automation. This server provides tools to interact with Binary Ninja via Large Language Models.

## Overview

The Binary Ninja MCP Server is a plugin and server implementation that allows Large Language Models to interact with Binary Ninja through the Model Context Protocol (MCP). It provides functionalities such as:

- Get assembly code for functions
- Get decompiled code (HLIL) for functions
- Rename functions and variables
- Add comments

## Installation

### Using uv (recommended)

When using [`uv`](https://docs.astral.xsh/uv/) no specific installation is needed. We will
use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to directly run *binja_mcp*.

### Using PIP

Alternatively you can install `binja-mcp` via pip:

```bash
pip install binja-mcp
```

After installation, you can run it as a script using:

```bash
python -m binja_mcp
```

### Binary Ninja Plugin Installation

Clone this repository OR link the cloned repository into Binary Ninja's plugin directory:

- Linux: `~/.binaryninja/plugins/`
- macOS: `~/Library/Application Support/Binary Ninja/plugins/`
- Windows: `%APPDATA%\Binary Ninja\plugins\`

## Configuration

### Usage with Claude Desktop/Cursor

Add this to your `claude_desktop_config.json` or Cursor MCP servers:

<details>
<summary>Using uvx</summary>

```json
"mcpServers": {
  "binja": {
    "command": "uvx",
    "args": [
        "-n",
        "mcp-server-binja"
    ]
  }
}
```
</details>

<details>
<summary>Using pip installation</summary>

```json
"mcpServers": {
  "binja": {
    "command": "python",
    "args": [
        "-m", 
        "mcp_server_binja"
    ]
  }
}
```
</details>

## Usage

1. Open Binary Ninja and load a binary
2. Start the MCP Server from the Tools menu or using the keyboard shortcut
3. Use Claude Desktop, Cursor, or any MCP client of your preference to interact with the binary

## Available Commands

The following commands are available through the MCP interface:

- `binja_get_function_assembly`: Get assembly code for a named function
- `binja_get_function_decompiled`: Get decompiled code for a named function
- `binja_get_global_variable`: Get information about a global variable
- `binja_get_current_function_assembly`: Get assembly for the current function
- `binja_get_current_function_decompiled`: Get decompiled code for the current function

## Development

If you are doing local development, there are two ways to test your changes:

1. Run the MCP inspector to test your changes:
```bash
npx @modelcontextprotocol/inspector uvx binja_mcp
```

2. Test using the Claude desktop app by adding the following to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "binja": {
      "command": "uv",
      "args": [ 
        "--directory",
        "/<path to mcp-server-binja>/src",
        "run",
        "mcp-server-binja"
      ]
    }
  }
}
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
