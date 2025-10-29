#!/usr/bin/env python3
"""
JSON Validator MCP Server
Comprehensive JSON validation, analysis and manipulation server using Model Context Protocol
"""

import asyncio
import json
import sys
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from urllib.parse import urlparse
from email.utils import parseaddr
from datetime import datetime

try:
    import jsonschema
except ImportError:
    jsonschema = None

try:
    import yaml
except ImportError:
    yaml = None

from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import mcp.server.stdio


class JSONValidatorServer:
    def __init__(self, config_path: Optional[str] = None):
        self.server = Server("json-validator-server")
        self.config = self._load_config(config_path)

        # Setup handlers
        self.server.list_tools()(self.list_tools)
        self.server.call_tool()(self.call_tool)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Default configuration
        script_dir = Path(__file__).parent
        default_config_path = script_dir / "config.json"
        if default_config_path.exists():
            with open(default_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        return {
            "default_language": "en",
            "indent": 2
        }

    def _get_error_position(self, json_string: str, error: json.JSONDecodeError) -> Dict[str, Any]:
        """Get detailed error position information"""
        lines = json_string.split('\n')
        line_num = error.lineno
        col_num = error.colno

        # Get the problematic line
        error_line = lines[line_num - 1] if line_num <= len(lines) else ""

        # Show context (line before and after if available)
        context_before = lines[line_num - 2] if line_num > 1 else None
        context_after = lines[line_num] if line_num < len(lines) else None

        return {
            "line": line_num,
            "column": col_num,
            "error_line": error_line,
            "context_before": context_before,
            "context_after": context_after,
            "message": error.msg,
            "position": error.pos
        }

    async def validate_json(self, json_string: str, return_data: bool = False) -> Dict[str, Any]:
        """Validate JSON syntax and return detailed error information"""
        try:
            data = json.loads(json_string)
            result = {
                "valid": True,
                "message": "JSON is valid",
                "size_bytes": len(json_string.encode('utf-8')),
                "size_chars": len(json_string)
            }

            # Only return data if explicitly requested and size is reasonable
            if return_data:
                result["data"] = data
            else:
                # Return basic info about the structure instead
                result["root_type"] = type(data).__name__
                if isinstance(data, dict):
                    result["root_keys"] = list(data.keys())
                    result["root_key_count"] = len(data)
                elif isinstance(data, list):
                    result["root_array_length"] = len(data)

            return result
        except json.JSONDecodeError as e:
            error_details = self._get_error_position(json_string, e)
            return {
                "valid": False,
                "error": error_details
            }
        except Exception as e:
            return {
                "valid": False,
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                }
            }

    async def validate_json_file(self, file_path: str, return_data: bool = False) -> Dict[str, Any]:
        """Validate JSON file"""
        try:
            # Get file size first
            file_size = os.path.getsize(file_path)

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            result = await self.validate_json(content, return_data=return_data)
            result["file_path"] = file_path
            result["file_size_bytes"] = file_size

            # Add warnings for large files
            if file_size > 10_000_000:  # 10MB
                result["warning"] = "Large file (>10MB). Consider using json_stats for analysis instead of returning full data."
            elif file_size > 1_000_000:  # 1MB
                result["info"] = "Medium-sized file (>1MB). Set return_data=false for better performance."

            return result
        except FileNotFoundError:
            return {
                "valid": False,
                "error": {
                    "message": f"File not found: {file_path}",
                    "type": "FileNotFoundError"
                }
            }
        except Exception as e:
            return {
                "valid": False,
                "error": {
                    "message": str(e),
                    "type": type(e).__name__
                }
            }

    async def validate_schema(
        self,
        json_string: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate JSON against JSON Schema"""
        if jsonschema is None:
            return {
                "error": "jsonschema library is not installed. Run: pip install jsonschema"
            }

        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            error_details = self._get_error_position(json_string, e)
            return {
                "valid": False,
                "error": "Invalid JSON syntax",
                "details": error_details
            }

        try:
            jsonschema.validate(instance=data, schema=schema)
            return {
                "valid": True,
                "message": "JSON is valid according to the schema"
            }
        except jsonschema.ValidationError as e:
            return {
                "valid": False,
                "error": "Schema validation failed",
                "message": e.message,
                "path": list(e.path),
                "schema_path": list(e.schema_path),
                "validator": e.validator,
                "validator_value": e.validator_value
            }
        except jsonschema.SchemaError as e:
            return {
                "valid": False,
                "error": "Invalid schema",
                "message": str(e)
            }

    def _calculate_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate maximum depth of nested structure"""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

    def _count_types(self, obj: Any) -> Dict[str, int]:
        """Count occurrences of each type in the structure"""
        type_counts = defaultdict(int)

        def count(item):
            if isinstance(item, dict):
                type_counts["object"] += 1
                for v in item.values():
                    count(v)
            elif isinstance(item, list):
                type_counts["array"] += 1
                for v in item:
                    count(v)
            elif isinstance(item, str):
                type_counts["string"] += 1
            elif isinstance(item, bool):
                type_counts["boolean"] += 1
            elif isinstance(item, int):
                type_counts["integer"] += 1
            elif isinstance(item, float):
                type_counts["number"] += 1
            elif item is None:
                type_counts["null"] += 1

        count(obj)
        return dict(type_counts)

    def _count_keys(self, obj: Any) -> int:
        """Count total number of keys in all objects"""
        count = 0
        if isinstance(obj, dict):
            count += len(obj)
            for v in obj.values():
                count += self._count_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                count += self._count_keys(item)
        return count

    async def json_stats(self, json_string: str) -> Dict[str, Any]:
        """Calculate statistics about JSON structure"""
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            error_details = self._get_error_position(json_string, e)
            return {
                "error": "Invalid JSON",
                "details": error_details
            }

        stats = {
            "size_bytes": len(json_string.encode('utf-8')),
            "size_chars": len(json_string),
            "max_depth": self._calculate_depth(data),
            "total_keys": self._count_keys(data),
            "type_counts": self._count_types(data),
            "root_type": type(data).__name__
        }

        # Add root-level information
        if isinstance(data, dict):
            stats["root_keys"] = list(data.keys())
            stats["root_key_count"] = len(data)
        elif isinstance(data, list):
            stats["root_array_length"] = len(data)

        return stats

    def _deep_diff(self, obj1: Any, obj2: Any, path: str = "") -> List[Dict[str, Any]]:
        """Find differences between two JSON objects"""
        differences = []

        if type(obj1) != type(obj2):
            differences.append({
                "path": path or "root",
                "type": "type_mismatch",
                "value1_type": type(obj1).__name__,
                "value2_type": type(obj2).__name__,
                "value1": obj1,
                "value2": obj2
            })
            return differences

        if isinstance(obj1, dict):
            # Keys only in obj1
            for key in obj1.keys() - obj2.keys():
                differences.append({
                    "path": f"{path}.{key}" if path else key,
                    "type": "missing_in_second",
                    "value": obj1[key]
                })

            # Keys only in obj2
            for key in obj2.keys() - obj1.keys():
                differences.append({
                    "path": f"{path}.{key}" if path else key,
                    "type": "missing_in_first",
                    "value": obj2[key]
                })

            # Keys in both - compare values
            for key in obj1.keys() & obj2.keys():
                current_path = f"{path}.{key}" if path else key
                differences.extend(self._deep_diff(obj1[key], obj2[key], current_path))

        elif isinstance(obj1, list):
            if len(obj1) != len(obj2):
                differences.append({
                    "path": path or "root",
                    "type": "array_length_mismatch",
                    "length1": len(obj1),
                    "length2": len(obj2)
                })

            # Compare elements up to the shorter length
            for i in range(min(len(obj1), len(obj2))):
                current_path = f"{path}[{i}]" if path else f"[{i}]"
                differences.extend(self._deep_diff(obj1[i], obj2[i], current_path))

        else:
            # Primitive types
            if obj1 != obj2:
                differences.append({
                    "path": path or "root",
                    "type": "value_mismatch",
                    "value1": obj1,
                    "value2": obj2
                })

        return differences

    async def compare_json(
        self,
        json_string1: str,
        json_string2: str
    ) -> Dict[str, Any]:
        """Compare two JSON objects and report differences"""
        try:
            data1 = json.loads(json_string1)
            data2 = json.loads(json_string2)
        except json.JSONDecodeError as e:
            return {
                "error": "Invalid JSON in one or both inputs",
                "details": str(e)
            }

        differences = self._deep_diff(data1, data2)

        return {
            "identical": len(differences) == 0,
            "difference_count": len(differences),
            "differences": differences
        }

    async def convert_json(
        self,
        json_string: str,
        output_format: str
    ) -> Dict[str, Any]:
        """Convert JSON to other formats (YAML, CSV, XML)"""
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            error_details = self._get_error_position(json_string, e)
            return {
                "error": "Invalid JSON",
                "details": error_details
            }

        output_format = output_format.lower()

        if output_format == "yaml":
            if yaml is None:
                return {
                    "error": "PyYAML library is not installed. Run: pip install pyyaml"
                }
            try:
                yaml_output = yaml.dump(data, allow_unicode=True, default_flow_style=False)
                return {
                    "format": "yaml",
                    "output": yaml_output
                }
            except Exception as e:
                return {"error": f"YAML conversion failed: {str(e)}"}

        elif output_format == "csv":
            # Only works for flat lists of objects
            if not isinstance(data, list):
                return {
                    "error": "CSV conversion requires root to be an array of objects"
                }

            if not data:
                return {"format": "csv", "output": ""}

            # Get all unique keys
            keys = set()
            for item in data:
                if isinstance(item, dict):
                    keys.update(item.keys())
                else:
                    return {
                        "error": "CSV conversion requires array of objects (not primitives)"
                    }

            keys = sorted(keys)

            # Build CSV
            csv_lines = [",".join(keys)]
            for item in data:
                values = [str(item.get(key, "")) for key in keys]
                csv_lines.append(",".join(f'"{v}"' for v in values))

            return {
                "format": "csv",
                "output": "\n".join(csv_lines)
            }

        elif output_format == "xml":
            # Simple XML conversion
            def dict_to_xml(obj, root_name="root"):
                if isinstance(obj, dict):
                    xml = f"<{root_name}>"
                    for key, value in obj.items():
                        xml += dict_to_xml(value, key)
                    xml += f"</{root_name}>"
                    return xml
                elif isinstance(obj, list):
                    xml = ""
                    for item in obj:
                        xml += dict_to_xml(item, "item")
                    return xml
                else:
                    return f"<{root_name}>{obj}</{root_name}>"

            xml_output = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_output += dict_to_xml(data)

            return {
                "format": "xml",
                "output": xml_output
            }

        else:
            return {
                "error": f"Unsupported format: {output_format}. Supported: yaml, csv, xml"
            }

    def _deep_merge(self, base: Any, update: Any) -> Any:
        """Deep merge two JSON objects"""
        if isinstance(base, dict) and isinstance(update, dict):
            result = base.copy()
            for key, value in update.items():
                if key in result:
                    result[key] = self._deep_merge(result[key], value)
                else:
                    result[key] = value
            return result
        elif isinstance(base, list) and isinstance(update, list):
            return base + update
        else:
            return update

    async def merge_json(self, json_strings: List[str]) -> Dict[str, Any]:
        """Merge multiple JSON objects"""
        if not json_strings:
            return {"error": "No JSON strings provided"}

        try:
            objects = [json.loads(s) for s in json_strings]
        except json.JSONDecodeError as e:
            return {
                "error": "Invalid JSON in one of the inputs",
                "details": str(e)
            }

        # Start with first object
        result = objects[0]

        # Merge remaining objects
        for obj in objects[1:]:
            result = self._deep_merge(result, obj)

        return {
            "merged": result,
            "merged_count": len(objects)
        }

    def _validate_url(self, value: str) -> bool:
        """Check if string is a valid URL"""
        try:
            result = urlparse(value)
            return all([result.scheme, result.netloc])
        except:
            return False

    def _validate_email(self, value: str) -> bool:
        """Check if string is a valid email"""
        _, email = parseaddr(value)
        return '@' in email and '.' in email.split('@')[1]

    def _validate_date(self, value: str, formats: List[str] = None) -> bool:
        """Check if string is a valid date"""
        if formats is None:
            formats = [
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%d.%m.%Y",
                "%d/%m/%Y"
            ]

        for fmt in formats:
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                continue
        return False

    def _scan_for_types(
        self,
        obj: Any,
        path: str = "",
        results: List = None
    ) -> List[Dict[str, Any]]:
        """Scan JSON for specific data types"""
        if results is None:
            results = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, str):
                    # Check for special types
                    type_info = {"path": current_path, "value": value, "types": []}

                    if self._validate_url(value):
                        type_info["types"].append("url")
                    if self._validate_email(value):
                        type_info["types"].append("email")
                    if self._validate_date(value):
                        type_info["types"].append("date")

                    if type_info["types"]:
                        results.append(type_info)
                else:
                    self._scan_for_types(value, current_path, results)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                current_path = f"{path}[{i}]" if path else f"[{i}]"
                self._scan_for_types(item, current_path, results)

        return results

    async def validate_types(self, json_string: str) -> Dict[str, Any]:
        """Validate and identify special types (URLs, emails, dates) in JSON"""
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            error_details = self._get_error_position(json_string, e)
            return {
                "error": "Invalid JSON",
                "details": error_details
            }

        type_validations = self._scan_for_types(data)

        # Group by type
        by_type = defaultdict(list)
        for item in type_validations:
            for t in item["types"]:
                by_type[t].append({
                    "path": item["path"],
                    "value": item["value"]
                })

        return {
            "total_found": len(type_validations),
            "by_type": dict(by_type),
            "all_validations": type_validations
        }

    async def suggest_json_fixes(
        self,
        json_string: str,
        show_context: bool = True
    ) -> Dict[str, Any]:
        """Analyze JSON and suggest fixes for common errors"""
        suggestions = []
        lines = json_string.split('\n')

        # First, try to parse to get the main error
        try:
            json.loads(json_string)
            # If successful, check for non-critical issues
            has_critical_error = False
        except json.JSONDecodeError as e:
            has_critical_error = True
            line_num = e.lineno
            col_num = e.colno
            error_line = lines[line_num - 1] if line_num <= len(lines) else ""

            # Analyze the specific error and suggest fix
            suggestion = {
                "line": line_num,
                "column": col_num,
                "type": "syntax_error",
                "severity": "error",
                "message": e.msg,
                "current": error_line.strip()
            }

            # Detect specific error types and suggest fixes
            if "Illegal trailing comma" in e.msg or "trailing comma" in e.msg.lower():
                # Trailing comma error
                suggestion["type"] = "trailing_comma"
                suggestion["fix_description"] = "Remove trailing comma before closing bracket"
                # Try to remove the trailing comma
                fixed_line = re.sub(r',(\s*[}\]])', r'\1', error_line)
                suggestion["suggested"] = fixed_line.strip()

            elif "Expecting property name" in e.msg:
                # Could be: missing quotes, invalid text, or trailing comma
                if re.search(r',\s*[^"\s]', error_line):
                    # Invalid text after comma
                    suggestion["type"] = "invalid_text"
                    # Find the invalid text
                    match = re.search(r',(\s*)([^"\s,}\]]+)', error_line)
                    if match:
                        invalid_text = match.group(2)
                        suggestion["invalid_text"] = invalid_text
                        suggestion["fix_description"] = f"Remove invalid text '{invalid_text}'"
                        fixed_line = error_line.replace(f',{match.group(1)}{invalid_text}', ',')
                        suggestion["suggested"] = fixed_line.strip()
                else:
                    suggestion["fix_description"] = "Add quotes around property name or check JSON structure"

            elif "Expecting ','" in e.msg:
                suggestion["type"] = "missing_comma"
                suggestion["fix_description"] = "Add missing comma or check for extra brackets"

            elif "Expecting value" in e.msg:
                suggestion["type"] = "missing_value"
                suggestion["fix_description"] = "Add value after colon or remove trailing comma"

            if show_context:
                suggestion["context_before"] = lines[line_num - 2].strip() if line_num > 1 else None
                suggestion["context_after"] = lines[line_num].strip() if line_num < len(lines) else None

            suggestions.append(suggestion)

        # Scan for other common issues even if JSON is valid or after finding main error
        for i, line in enumerate(lines):
            line_num = i + 1

            # Check for single quotes (should be double quotes)
            if "'" in line and not has_critical_error:
                if re.search(r"'[^']*'", line):
                    suggestions.append({
                        "line": line_num,
                        "type": "single_quotes",
                        "severity": "warning",
                        "message": "JSON requires double quotes, not single quotes",
                        "current": line.strip(),
                        "suggested": line.replace("'", '"').strip(),
                        "fix_description": "Replace single quotes with double quotes"
                    })

            # Check for comments (JSON doesn't support comments)
            if "//" in line or "/*" in line:
                suggestions.append({
                    "line": line_num,
                    "type": "comment",
                    "severity": "warning",
                    "message": "JSON does not support comments",
                    "current": line.strip(),
                    "fix_description": "Remove comment or move to external documentation"
                })

            # Check for unquoted keys (common JavaScript pattern)
            if not has_critical_error:
                match = re.search(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', line)
                if match and not re.search(r'^\s*"[^"]*"\s*:', line):
                    key = match.group(1)
                    suggestions.append({
                        "line": line_num,
                        "type": "unquoted_key",
                        "severity": "error",
                        "message": f"Property name '{key}' must be enclosed in double quotes",
                        "current": line.strip(),
                        "suggested": line.replace(f'{key}:', f'"{key}":').strip(),
                        "fix_description": f"Add double quotes around '{key}'"
                    })

        return {
            "valid": not has_critical_error and len(suggestions) == 0,
            "has_errors": len([s for s in suggestions if s.get("severity") == "error"]) > 0,
            "has_warnings": len([s for s in suggestions if s.get("severity") == "warning"]) > 0,
            "suggestion_count": len(suggestions),
            "suggestions": suggestions
        }

    async def list_tools(self) -> List[Tool]:
        """List available MCP tools"""
        return [
            Tool(
                name="validate_json",
                description="Validate JSON syntax and return detailed error information with line and column numbers. For large JSON, set return_data=false to avoid token limits.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string to validate"
                        },
                        "return_data": {
                            "type": "boolean",
                            "description": "Whether to return the parsed JSON data (default: false for large files)",
                            "default": False
                        }
                    },
                    "required": ["json_string"]
                }
            ),
            Tool(
                name="validate_json_file",
                description="Validate JSON file and return detailed error information. Automatically handles large files by not returning full data unless requested.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to JSON file"
                        },
                        "return_data": {
                            "type": "boolean",
                            "description": "Whether to return the parsed JSON data (default: false, recommended for files >1MB)",
                            "default": False
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="validate_schema",
                description="Validate JSON against a JSON Schema (requires jsonschema library)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string to validate"
                        },
                        "schema": {
                            "type": "object",
                            "description": "JSON Schema to validate against"
                        }
                    },
                    "required": ["json_string", "schema"]
                }
            ),
            Tool(
                name="json_stats",
                description="Calculate statistics about JSON structure (depth, keys, types, size)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string to analyze"
                        }
                    },
                    "required": ["json_string"]
                }
            ),
            Tool(
                name="compare_json",
                description="Compare two JSON objects and report all differences",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string1": {
                            "type": "string",
                            "description": "First JSON string"
                        },
                        "json_string2": {
                            "type": "string",
                            "description": "Second JSON string"
                        }
                    },
                    "required": ["json_string1", "json_string2"]
                }
            ),
            Tool(
                name="convert_json",
                description="Convert JSON to other formats (yaml, csv, xml)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string to convert"
                        },
                        "output_format": {
                            "type": "string",
                            "description": "Output format (yaml, csv, xml)",
                            "enum": ["yaml", "csv", "xml"]
                        }
                    },
                    "required": ["json_string", "output_format"]
                }
            ),
            Tool(
                name="merge_json",
                description="Deep merge multiple JSON objects into one",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_strings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Array of JSON strings to merge"
                        }
                    },
                    "required": ["json_strings"]
                }
            ),
            Tool(
                name="validate_types",
                description="Scan JSON and validate special types (URLs, emails, dates)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string to scan for special types"
                        }
                    },
                    "required": ["json_string"]
                }
            ),
            Tool(
                name="suggest_json_fixes",
                description="Analyze JSON and suggest fixes for common errors (trailing commas, invalid text, comments, quotes). Does NOT auto-fix - only shows suggestions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string to analyze"
                        },
                        "show_context": {
                            "type": "boolean",
                            "description": "Show context lines around errors",
                            "default": True
                        }
                    },
                    "required": ["json_string"]
                }
            )
        ]

    async def call_tool(self, name: str, arguments: Any) -> List[TextContent]:
        """Handle tool calls"""
        try:
            if name == "validate_json":
                json_string = arguments.get("json_string", "")
                return_data = arguments.get("return_data", False)
                result = await self.validate_json(json_string, return_data=return_data)

            elif name == "validate_json_file":
                file_path = arguments.get("file_path", "")
                return_data = arguments.get("return_data", False)
                result = await self.validate_json_file(file_path, return_data=return_data)

            elif name == "validate_schema":
                json_string = arguments.get("json_string", "")
                schema = arguments.get("schema", {})
                result = await self.validate_schema(json_string, schema)

            elif name == "json_stats":
                json_string = arguments.get("json_string", "")
                result = await self.json_stats(json_string)

            elif name == "compare_json":
                json_string1 = arguments.get("json_string1", "")
                json_string2 = arguments.get("json_string2", "")
                result = await self.compare_json(json_string1, json_string2)

            elif name == "convert_json":
                json_string = arguments.get("json_string", "")
                output_format = arguments.get("output_format", "yaml")
                result = await self.convert_json(json_string, output_format)

            elif name == "merge_json":
                json_strings = arguments.get("json_strings", [])
                result = await self.merge_json(json_strings)

            elif name == "validate_types":
                json_string = arguments.get("json_string", "")
                result = await self.validate_types(json_string)

            elif name == "suggest_json_fixes":
                json_string = arguments.get("json_string", "")
                show_context = arguments.get("show_context", True)
                result = await self.suggest_json_fixes(json_string, show_context=show_context)

            else:
                result = {"error": f"Unknown tool: {name}"}

            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e), "type": type(e).__name__}, indent=2)
            )]

    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    server = JSONValidatorServer(config_path)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
