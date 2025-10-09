#!/usr/bin/env python3
"""
LanguageTool MCP Server
Spell and grammar checking server using Model Context Protocol
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import language_tool_python
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


class LanguageToolServer:
    def __init__(self, config_path: Optional[str] = None):
        self.server = Server("languagetool-server")
        self.tools: Dict[str, language_tool_python.LanguageTool] = {}
        self.config = self._load_config(config_path)
        self.ignored_words = set(self.config.get("ignored_words", []))

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
            "ignored_words": [],
            "default_language": "auto"
        }

    def _get_tool(self, language: str) -> language_tool_python.LanguageTool:
        """Get or create LanguageTool instance for specified language"""
        if language not in self.tools:
            self.tools[language] = language_tool_python.LanguageTool(language)
        return self.tools[language]

    def _detect_language(self, text: str) -> str:
        """Detect language from text content"""
        # Simple heuristic: check for Polish characters
        polish_chars = set('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')
        if any(char in polish_chars for char in text):
            return 'pl-PL'
        return 'en-US'

    def _filter_matches(self, matches: List, text: str) -> List:
        """Filter out matches for ignored words"""
        filtered = []
        for match in matches:
            word = text[match.offset:match.offset + match.errorLength]
            if word.lower() not in self.ignored_words:
                filtered.append(match)
        return filtered

    async def check_text(
        self,
        text: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check spelling and grammar in text"""
        if not language or language == "auto":
            language = self._detect_language(text)

        tool = self._get_tool(language)
        matches = tool.check(text)
        matches = self._filter_matches(matches, text)

        errors = []
        for match in matches:
            errors.append({
                "message": match.message,
                "context": match.context,
                "offset": match.offset,
                "length": match.errorLength,
                "replacements": match.replacements[:5],  # Top 5 suggestions
                "rule_id": match.ruleId,
                "category": match.category
            })

        return {
            "language": language,
            "error_count": len(errors),
            "errors": errors
        }

    async def check_json_file(
        self,
        file_path: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check spelling in JSON file values"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return {"error": f"Failed to read JSON file: {str(e)}"}

        return await self.check_json_data(data, language)

    async def check_json_data(
        self,
        data: Any,
        language: Optional[str] = None,
        path: str = ""
    ) -> Dict[str, Any]:
        """Check spelling in JSON data structure"""
        results = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, str):
                    # Skip keys that look like IDs or technical terms
                    if key.startswith(("alarm!", "kod_", "zd_")):
                        continue

                    result = await self.check_text(value, language)
                    if result["error_count"] > 0:
                        results.append({
                            "key": current_path,
                            "value": value,
                            "check_result": result
                        })
                elif isinstance(value, (dict, list)):
                    nested = await self.check_json_data(value, language, current_path)
                    if nested.get("errors"):
                        results.extend(nested["errors"])

        elif isinstance(data, list):
            for idx, item in enumerate(data):
                current_path = f"{path}[{idx}]"
                if isinstance(item, str):
                    result = await self.check_text(item, language)
                    if result["error_count"] > 0:
                        results.append({
                            "index": idx,
                            "value": item,
                            "check_result": result
                        })
                elif isinstance(item, (dict, list)):
                    nested = await self.check_json_data(item, language, current_path)
                    if nested.get("errors"):
                        results.extend(nested["errors"])

        return {
            "total_errors": len(results),
            "errors": results
        }

    async def list_tools(self) -> List[Tool]:
        """List available MCP tools"""
        return [
            Tool(
                name="check_spelling",
                description="Check spelling and grammar in text. Supports multiple languages (auto-detection or specify: pl-PL, en-US, de-DE, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to check"
                        },
                        "language": {
                            "type": "string",
                            "description": "Language code (e.g., 'pl-PL', 'en-US', 'auto' for auto-detection)",
                            "default": "auto"
                        }
                    },
                    "required": ["text"]
                }
            ),
            Tool(
                name="check_json_file",
                description="Check spelling in JSON file values (not keys). Useful for translation files.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to JSON file"
                        },
                        "language": {
                            "type": "string",
                            "description": "Language code (e.g., 'pl-PL', 'en-US', 'auto' for auto-detection)",
                            "default": "auto"
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="check_json_values",
                description="Check spelling in JSON data values provided as string",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON data as string"
                        },
                        "language": {
                            "type": "string",
                            "description": "Language code",
                            "default": "auto"
                        }
                    },
                    "required": ["json_string"]
                }
            ),
            Tool(
                name="add_ignored_word",
                description="Add word to ignore list (technical terms, abbreviations, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "word": {
                            "type": "string",
                            "description": "Word to ignore in future checks"
                        }
                    },
                    "required": ["word"]
                }
            )
        ]

    async def call_tool(self, name: str, arguments: Any) -> List[TextContent]:
        """Handle tool calls"""
        try:
            if name == "check_spelling":
                text = arguments.get("text", "")
                language = arguments.get("language", "auto")
                result = await self.check_text(text, language)

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False)
                )]

            elif name == "check_json_file":
                file_path = arguments.get("file_path", "")
                language = arguments.get("language", "auto")
                result = await self.check_json_file(file_path, language)

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False)
                )]

            elif name == "check_json_values":
                json_string = arguments.get("json_string", "")
                language = arguments.get("language", "auto")

                try:
                    data = json.loads(json_string)
                    result = await self.check_json_data(data, language)
                except json.JSONDecodeError as e:
                    result = {"error": f"Invalid JSON: {str(e)}"}

                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False)
                )]

            elif name == "add_ignored_word":
                word = arguments.get("word", "").lower()
                self.ignored_words.add(word)

                # Save to config
                config_path = Path(__file__).parent / "config.json"
                config = self.config
                config["ignored_words"] = list(self.ignored_words)

                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "success",
                        "message": f"Added '{word}' to ignore list",
                        "ignored_words_count": len(self.ignored_words)
                    }, indent=2)
                )]

            else:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Unknown tool: {name}"})
                )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)})
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
    server = LanguageToolServer(config_path)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
