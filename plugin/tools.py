from typing import Dict, List
import binaryninja as bn
import base64
import json


def _get_function_blocks(function) -> List[Dict]:
    blocks = []
    for block in function.basic_blocks:
        for instruction in block.disassembly_text:
            blocks.append(
                {"address": instruction.address, "instruction": str(instruction)}
            )

    return blocks


def get_functions(bv, cursor=None, limit=100):
    """Get functions in the current binary with cursor-based pagination

    Args:
        bv: Binary view
        cursor: Opaque pagination cursor (default: None for first page)
        limit: Maximum number of functions to return (default: 100)
    """
    if not bv:
        return {"error": "No binary view available"}

    try:
        # Get all functions
        functions = list(bv.functions)
        if not functions:
            return {"error": "No functions found"}

        total_functions = len(functions)

        # Validate limit
        if limit <= 0:
            limit = 100

        # Determine starting offset from cursor
        offset = 0
        if cursor:
            try:
                # Decode cursor (base64-encoded JSON)
                cursor_data = json.loads(base64.b64decode(cursor).decode("utf-8"))
                offset = cursor_data.get("offset", 0)
            except Exception as e:
                return {"error": f"Invalid cursor: {str(e)}"}

        # Validate offset
        if offset < 0:
            offset = 0
        elif offset >= total_functions:
            offset = max(0, total_functions - 1)

        # Apply pagination
        end_offset = min(offset + limit, total_functions)
        paginated_functions = functions[offset:end_offset]

        # Create next cursor if there are more results
        next_cursor = None
        if end_offset < total_functions:
            cursor_data = {"offset": end_offset}
            next_cursor = base64.b64encode(
                json.dumps(cursor_data).encode("utf-8")
            ).decode("utf-8")

        functions_list = []
        for f in paginated_functions:
            functions_list.append(
                {
                    "name": f.name,
                    "address": f.start,
                    "size": f.total_bytes,
                    "address_ranges": str(f.address_ranges),
                }
            )

        result = {
            "functions": functions_list,
            "total": total_functions,
            "count": len(functions_list),
        }

        # Add pagination metadata
        if next_cursor:
            result["nextCursor"] = next_cursor

        return result
    except Exception as e:
        return {"error": str(e)}


def get_binary_info(bv):
    """Get binary information such as architecture, size, segments, etc."""
    if not bv:
        return {"error": "No binary view available"}

    try:
        # Basic binary information
        info = {
            "file": {
                "filename": bv.file.filename,
                "file_size": bv.file.raw.length,
                "modified": bv.file.modified,
            },
            "binary": {
                "view_type": bv.view_type,
                "arch": str(bv.arch),
                "platform": str(bv.platform),
                "entry_point": bv.entry_point,
                "start": bv.start,
                "end": bv.end,
                "length": bv.end - bv.start,
                "executable": bv.executable,
                "endianness": (
                    "little_endian"
                    if bv.arch.endianness == bn.Endianness.LittleEndian
                    else "big_endian"
                ),
                "address_size": bv.address_size,
                "function_count": len(list(bv.functions)),
            },
        }

        # Segments information
        segments = []
        for segment in bv.segments:
            segments.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "length": segment.length,
                    "data_length": segment.data_length,
                    "data_offset": segment.data_offset,
                    "readable": segment.readable,
                    "writable": segment.writable,
                    "executable": segment.executable,
                }
            )
        info["segments"] = segments

        # Sections information
        sections = []
        for section in bv.sections.values():
            sections.append(
                {
                    "name": section.name,
                    "start": section.start,
                    "end": section.end,
                    "length": section.length,
                    "type": str(section.type),
                    "align": section.align,
                    "entry_size": section.entry_size,
                    "linked_section": section.linked_section,
                    "info_section": section.info_section,
                    "semantics": str(section.semantics),
                }
            )
        info["sections"] = sections

        return info
    except Exception as e:
        return {"error": str(e)}


def get_function_assembly(bv, function_name):
    """Get function assembly code"""
    if not bv:
        return {"error": "No binary view available"}

    try:
        function = bv.get_functions_by_name(function_name)[0]
        if not function:
            return {"error": f"Function '{function_name}' not found"}

        blocks = _get_function_blocks(function)

        return {
            "function": function.name,
            "size": function.total_bytes,
            "start": function.start,
            "language_representation": "assembly",
            "blocks": blocks,
        }
    except Exception as e:
        return {"error": str(e)}


def get_function_decompiled(bv, function_name):
    """Get function decompiled code"""
    if not bv:
        return {"error": "No binary view available"}

    try:
        function = bv.get_functions_by_name(function_name)[0]
        if not function:
            return {"error": f"Function '{function_name}' not found"}

        hlil = function.hlil
        if not hlil:
            return {"error": "Failed to get HLIL for function"}

        return {
            "function": function.name,
            "size": function.total_bytes,
            "start": function.start,
            "language_representation": "High Level Intermediate Language",
            "blocks": _get_function_blocks(hlil),
        }
    except Exception as e:
        return {"error": str(e)}


def get_symbols_by_name(bv, symbol_name):
    if not bv:
        return {"error": "No binary view available"}

    try:
        symbols = bv.get_symbols_by_name(symbol_name)
        if not symbols:
            return {"error": f"Global variable '{symbol_name}' not found"}
        bn.log_error(f"dunha got: {symbols}")
        symbols_info = []
        for symbol in symbols:
            bn.log_error(f"dunhersss - {symbol}")
            symbols_info.append(
                {
                    "name": symbol.name,
                    "address": f"{symbol.address:#x}",
                    "type": str(symbol.type) if hasattr(symbol, "type") else "unknown",
                }
            )

        return {"symbols": symbols_info}
    except Exception as e:
        return {"error": str(e)}


def get_current_function_assembly(bv):
    if not bv:
        return {"error": "No binary view available"}

    try:
        # Get current function
        current_function = bv.get_functions_containing(bv.offset)[0]
        bn.log_error(f"dunha got: {current_function}")
        if not current_function:
            return {"error": "No function at current position"}

        blocks = _get_function_blocks(current_function)

        return {
            "function": current_function.name,
            "size": current_function.total_bytes,
            "start": current_function.start,
            "language_representation": "assembly",
            "blocks": blocks,
        }
    except Exception as e:
        return {"error": str(e)}


def get_current_function_decompiled(bv):
    """Get decompiled code of current function"""
    if not bv:
        return {"error": "No binary view available"}

    try:
        # Get current function
        current_function = bv.get_functions_containing(bv.offset)[0]
        if not current_function:
            return {"error": "No function at current position"}

        # Get decompiled code (HLIL)
        hlil = current_function.hlil
        if not hlil:
            return {"error": "Failed to get HLIL for function"}

        return {
            "function": current_function.name,
            "size": current_function.total_bytes,
            "start": current_function.start,
            "language_representation": "High Level Intermediate Language",
            "blocks": _get_function_blocks(hlil),
        }
    except Exception as e:
        return {"error": str(e)}


def rename_function(bv, function_name, new_name):
    """Rename a function"""
    if not bv:
        return {"error": "No binary view available"}

    try:
        function = bv.get_functions_by_name(function_name)[0]
        if not function:
            return {"error": f"Function '{function_name}' not found"}
    except Exception as e:
        return {"error": str(e)}

    bv.navigate(bv.view, function.start)

    function.name = new_name
    return {"success": f"Function '{function_name}' renamed to '{new_name}'"}


def rename_current_function(bv, new_name):
    """Rename the current function"""
    if not bv:
        return {"error": "No binary view available"}

    function = bv.get_functions_containing(bv.offset)[0]
    if not function:
        return {"error": "No function at current position"}

    function.name = new_name
    return {"success": f"Function '{function.name}' renamed to '{new_name}'"}


def rename_function_variable(bv, function_name, variable_name, new_name):
    """Rename a variable in specified function"""
    if not bv:
        return {"error": "No binary view available"}

    function = bv.get_functions_by_name(function_name)[0]
    if not function:
        return {"error": f"Function '{function_name}' not found"}

    bv.navigate(bv.view, function.start)

    variable = function.get_variable_by_name(variable_name)
    if not variable:
        return {
            "error": f"Variable '{variable_name}' not found in function '{function_name}'"
        }

    variable.name = new_name
    return {
        "success": f"Variable '{variable_name}' in function '{function_name}' renamed to '{new_name}'"
    }


def set_function_variable_type(bv, function_name, variable_name, new_type):
    """Set the type of a variable in specified function"""
    if not bv:
        return {"error": "No binary view available"}

    function = bv.get_functions_by_name(function_name)[0]
    if not function:
        return {"error": f"Function '{function_name}' not found"}

    bv.navigate(bv.view, function.start)

    variable = function.get_variable_by_name(variable_name)
    if not variable:
        return {
            "error": f"Variable '{variable_name}' not found in function '{function_name}'"
        }

    variable.set_type_async(new_type)
    function.reanalyze()

    return {
        "success": f"Variable '{variable_name}' in function '{function_name}' type set to '{new_type}'"
    }


def set_comment_at(bv, address, comment):
    """Set a comment at a specific address"""
    if not bv:
        return {"error": "No binary view available"}

    if isinstance(address, str):
        if address.startswith("0x"):
            address = int(address, 16)
        else:
            address = int(address)

    bv.navigate(bv.view, address)

    try:
        bv.set_comment_at(address, comment)
        return {"success": f"Comment set at address {address:#x}"}
    except Exception as e:
        return {"error": str(e)}
