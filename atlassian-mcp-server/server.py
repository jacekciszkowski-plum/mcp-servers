#!/usr/bin/env python3
"""Atlassian MCP Server - Jira and Confluence integration for Claude Code"""

import asyncio
import json
import sys
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import mcp.types as types
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio
import requests
from dateutil import parser as date_parser


class AtlassianMCPServer:
    """MCP Server for Atlassian Jira and Confluence"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize Atlassian MCP Server"""
        self.server = Server("atlassian-mcp-server")
        self.config = self._load_config(config_path)

        # Extract config values
        self.atlassian_url = self.config.get("atlassian_url", "https://plummichals.atlassian.net")
        self.email = self.config.get("email", "")
        self.api_token = self.config.get("api_token", "")
        self.timeout = self.config.get("timeout", 30)
        self.per_page = self.config.get("per_page", 100)

        # Setup auth
        self.auth = (self.email, self.api_token)

        # Register handlers
        self.server.list_tools()(self.list_tools)
        self.server.call_tool()(self.call_tool)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        script_dir = Path(__file__).parent
        config = {}

        # Load main config
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            # Fall back to default config in script directory
            default_config_path = script_dir / "config.json"
            if default_config_path.exists():
                with open(default_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {
                    "atlassian_url": "https://plummichals.atlassian.net",
                    "email": "",
                    "api_token": "",
                    "default_project": "VSNC",
                    "confluence_space": "GATEWAY",
                    "changelog_parent_id": "1673560113",
                    "timeout": 30,
                    "per_page": 100
                }

        # Load secrets (overrides config values)
        secrets_path = script_dir / "secrets.json"
        if secrets_path.exists():
            try:
                with open(secrets_path, 'r', encoding='utf-8') as f:
                    secrets = json.load(f)
                    config.update(secrets)
            except json.JSONDecodeError as e:
                print(f"Błąd parsowania secrets.json: {e}", file=sys.stderr)
        else:
            print(f"Ostrzeżenie: Nie znaleziono {secrets_path}. Utwórz ten plik z email i api_token.", file=sys.stderr)

        return config

    def _make_jira_request(self, endpoint: str, params: Dict = None, method: str = "GET") -> Dict[str, Any]:
        """Make Jira API request with error handling"""
        try:
            url = f"{self.atlassian_url}/rest/api/2{endpoint}"

            if method == "GET":
                response = requests.get(
                    url,
                    auth=self.auth,
                    params=params,
                    timeout=self.timeout,
                    headers={"Accept": "application/json"}
                )
            else:
                response = requests.request(
                    method,
                    url,
                    auth=self.auth,
                    json=params,
                    timeout=self.timeout,
                    headers={"Accept": "application/json", "Content-Type": "application/json"}
                )

            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Unauthorized",
                    "message": "Invalid API token or email"
                }

            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "Not found",
                    "message": f"Resource not found: {endpoint}"
                }

            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

    def _make_confluence_request(self, endpoint: str, params: Dict = None, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
        """Make Confluence API request with error handling"""
        try:
            url = f"{self.atlassian_url}/wiki/rest/api{endpoint}"

            headers = {"Accept": "application/json"}
            if method != "GET":
                headers["Content-Type"] = "application/json"

            if method == "GET":
                response = requests.get(
                    url,
                    auth=self.auth,
                    params=params,
                    timeout=self.timeout,
                    headers=headers
                )
            else:
                response = requests.request(
                    method,
                    url,
                    auth=self.auth,
                    json=data,
                    params=params,
                    timeout=self.timeout,
                    headers=headers
                )

            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Unauthorized",
                    "message": "Invalid API token or email"
                }

            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "Not found",
                    "message": f"Resource not found: {endpoint}"
                }

            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

    async def list_tools(self) -> List[Tool]:
        """List available MCP tools"""
        return [
            # Jira Tools
            Tool(
                name="search_jira_issues",
                description="Search for Jira issues using JQL query. Supports filtering by project, status, dates, and custom JQL.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jql": {
                            "type": "string",
                            "description": "JQL query string (e.g., 'project = VSNC AND status = Done')"
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of results to return",
                            "default": 100
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Fields to include in response (default: summary, description, issuetype, status, key, updated, priority)",
                            "default": ["summary", "description", "issuetype", "status", "key", "updated", "priority"]
                        }
                    },
                    "required": ["jql"]
                }
            ),
            Tool(
                name="get_issue_details",
                description="Get detailed information about a specific Jira issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "issue_key": {
                            "type": "string",
                            "description": "Issue key (e.g., 'VSNC-123')"
                        }
                    },
                    "required": ["issue_key"]
                }
            ),
            Tool(
                name="list_sprints",
                description="List sprints for a Jira board",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "board_id": {
                            "type": "number",
                            "description": "Board ID"
                        },
                        "state": {
                            "type": "string",
                            "description": "Sprint state filter",
                            "enum": ["active", "closed", "future"],
                            "default": "active"
                        }
                    },
                    "required": ["board_id"]
                }
            ),
            Tool(
                name="get_sprint_details",
                description="Get detailed information about a specific sprint including start and end dates",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sprint_id": {
                            "type": "number",
                            "description": "Sprint ID"
                        }
                    },
                    "required": ["sprint_id"]
                }
            ),

            # Confluence Tools
            Tool(
                name="get_confluence_page",
                description="Get Confluence page content by page ID or URL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Confluence page ID or URL"
                        },
                        "expand": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional data to expand (body.storage, version, space, etc.)",
                            "default": ["body.storage", "version", "space"]
                        }
                    },
                    "required": ["page_id"]
                }
            ),
            Tool(
                name="create_confluence_page",
                description="Create a new Confluence page in a specified space and parent location",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "space_key": {
                            "type": "string",
                            "description": "Confluence space key (e.g., 'GATEWAY')"
                        },
                        "title": {
                            "type": "string",
                            "description": "Page title"
                        },
                        "content": {
                            "type": "string",
                            "description": "Page content in Confluence storage format (HTML/Wiki markup)"
                        },
                        "parent_id": {
                            "type": "string",
                            "description": "Parent page ID (optional)"
                        }
                    },
                    "required": ["space_key", "title", "content"]
                }
            ),
            Tool(
                name="search_confluence_pages",
                description="Search for Confluence pages by text or CQL query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or CQL"
                        },
                        "space_key": {
                            "type": "string",
                            "description": "Limit search to specific space (optional)"
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of results",
                            "default": 25
                        }
                    },
                    "required": ["query"]
                }
            ),

            # Changelog Tool
            Tool(
                name="generate_changelog",
                description="Generate changelog from Jira issues based on sprint or issue list. Creates markdown file or Confluence page. Automatically classifies changes (Dodano/Zmieniono/Naprawiono/Usunięto), extracts documentation links, and separates analytical tasks into 'Inne osiągnięcia' section.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "description": "Generation mode: 'sprint' (uses sprint dates) or 'issues' (requires date range)",
                            "enum": ["sprint", "issues"]
                        },
                        "sprint_id": {
                            "type": "number",
                            "description": "Sprint ID (required for mode='sprint')"
                        },
                        "issue_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of issue keys (required for mode='issues', e.g., ['VSNC-123', 'VSNC-456'])"
                        },
                        "from_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format (required for mode='issues')"
                        },
                        "to_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format (required for mode='issues')"
                        },
                        "version": {
                            "type": "string",
                            "description": "Version string for the header (e.g., 'v1.2.3'). If not provided, shows [nazwa_wersji]"
                        },
                        "output_type": {
                            "type": "string",
                            "description": "Output type: 'markdown' (local file) or 'confluence' (page)",
                            "enum": ["markdown", "confluence"]
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path to output markdown file (required for output_type='markdown')"
                        },
                        "confluence_parent_url": {
                            "type": "string",
                            "description": "Parent page URL or ID for Confluence (required for output_type='confluence')"
                        },
                        "confluence_title": {
                            "type": "string",
                            "description": "Custom title for Confluence page (optional, defaults to 'Lista zmian w evoSYNC - [period]')"
                        }
                    },
                    "required": ["mode", "output_type"]
                }
            )
        ]

    async def call_tool(self, name: str, arguments: Any) -> List[TextContent]:
        """Handle tool calls"""
        try:
            if name == "search_jira_issues":
                result = await self._search_jira_issues(arguments)

            elif name == "get_issue_details":
                result = await self._get_issue_details(arguments)

            elif name == "list_sprints":
                result = await self._list_sprints(arguments)

            elif name == "get_sprint_details":
                result = await self._get_sprint_details(arguments)

            elif name == "get_confluence_page":
                result = await self._get_confluence_page(arguments)

            elif name == "create_confluence_page":
                result = await self._create_confluence_page(arguments)

            elif name == "search_confluence_pages":
                result = await self._search_confluence_pages(arguments)

            elif name == "generate_changelog":
                result = await self._generate_changelog(arguments)

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

    # Jira Tool Implementations

    async def _search_jira_issues(self, arguments: Dict) -> Dict[str, Any]:
        """Search for Jira issues using JQL"""
        jql = arguments.get("jql", "")
        max_results = arguments.get("max_results", 100)
        fields = arguments.get("fields", ["summary", "description", "issuetype", "status", "key", "updated", "priority"])

        # Use new Jira Cloud search endpoint (search/jql)
        url = f"{self.atlassian_url}/rest/api/3/search/jql"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ",".join(fields) if isinstance(fields, list) else fields
        }

        try:
            response = requests.get(
                url,
                auth=self.auth,
                params=params,
                timeout=self.timeout,
                headers=headers
            )

            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Unauthorized",
                    "message": "Invalid API token or email"
                }

            if response.status_code == 400:
                error_data = response.json()
                return {
                    "success": False,
                    "error": "Bad request",
                    "message": error_data.get("errorMessages", [str(response.text)])
                }

            response.raise_for_status()
            data = response.json()

            issues = data.get("issues", [])
            return {
                "success": True,
                "count": len(issues),
                "total": data.get("total", 0),
                "issues": issues
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

    async def _get_issue_details(self, arguments: Dict) -> Dict[str, Any]:
        """Get detailed information about a specific issue"""
        issue_key = arguments.get("issue_key", "")

        response = self._make_jira_request(f"/issue/{issue_key}")

        if not response.get("success"):
            return response

        return {
            "success": True,
            "issue": response["data"]
        }

    async def _list_sprints(self, arguments: Dict) -> Dict[str, Any]:
        """List sprints for a board"""
        board_id = arguments.get("board_id", 0)
        state = arguments.get("state", "active")

        # Use Agile API for sprints - use direct URL construction
        url = f"{self.atlassian_url}/rest/agile/1.0/board/{board_id}/sprint"
        headers = {
            "Accept": "application/json"
        }

        try:
            import requests
            response = requests.get(
                url,
                auth=self.auth,
                params={"state": state},
                timeout=self.timeout,
                headers=headers
            )

            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "Not found",
                    "message": f"Board {board_id} not found or you don't have access"
                }

            response.raise_for_status()
            response = {
                "success": True,
                "data": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

        if not response.get("success"):
            return response

        sprints = response["data"].get("values", [])
        return {
            "success": True,
            "count": len(sprints),
            "sprints": sprints
        }

    async def _get_sprint_details(self, arguments: Dict) -> Dict[str, Any]:
        """Get detailed information about a sprint"""
        sprint_id = arguments.get("sprint_id", 0)

        # Use Agile API for sprint details - direct URL construction
        url = f"{self.atlassian_url}/rest/agile/1.0/sprint/{sprint_id}"
        headers = {
            "Accept": "application/json"
        }

        try:
            import requests
            response = requests.get(
                url,
                auth=self.auth,
                timeout=self.timeout,
                headers=headers
            )

            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "Not found",
                    "message": f"Sprint {sprint_id} not found"
                }

            response.raise_for_status()
            return {
                "success": True,
                "sprint": response.json()
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

    # Confluence Tool Implementations

    async def _get_confluence_page(self, arguments: Dict) -> Dict[str, Any]:
        """Get Confluence page content"""
        page_id = arguments.get("page_id", "")
        expand = arguments.get("expand", ["body.storage", "version", "space"])

        # Extract page ID from URL if provided
        if "atlassian.net" in page_id:
            match = re.search(r'/pages/(\d+)', page_id)
            if match:
                page_id = match.group(1)

        response = self._make_confluence_request(f"/content/{page_id}", params={
            "expand": ",".join(expand)
        })

        if not response.get("success"):
            return response

        return {
            "success": True,
            "page": response["data"]
        }

    async def _create_confluence_page(self, arguments: Dict) -> Dict[str, Any]:
        """Create a new Confluence page"""
        space_key = arguments.get("space_key", "")
        title = arguments.get("title", "")
        content = arguments.get("content", "")
        parent_id = arguments.get("parent_id", None)

        # Use Confluence Cloud v2 API
        url = f"{self.atlassian_url}/wiki/api/v2/pages"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # First, get space ID from space key
        space_url = f"{self.atlassian_url}/wiki/api/v2/spaces"
        try:
            space_response = requests.get(
                space_url,
                auth=self.auth,
                params={"keys": space_key},
                timeout=self.timeout,
                headers={"Accept": "application/json"}
            )
            space_response.raise_for_status()
            spaces = space_response.json().get("results", [])
            if not spaces:
                return {"success": False, "error": f"Space '{space_key}' not found"}
            space_id = spaces[0]["id"]
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": "Failed to get space", "message": str(e)}

        # Create page payload for v2 API
        page_data = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "body": {
                "representation": "storage",
                "value": content
            }
        }

        if parent_id:
            page_data["parentId"] = str(parent_id)

        try:
            response = requests.post(
                url,
                auth=self.auth,
                json=page_data,
                timeout=self.timeout,
                headers=headers
            )

            if response.status_code == 400:
                error_data = response.json()
                return {
                    "success": False,
                    "error": "Bad request",
                    "message": error_data.get("message", str(response.text))
                }

            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "page": data,
                "url": f"{self.atlassian_url}/wiki{data['_links']['webui']}"
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

    async def _search_confluence_pages(self, arguments: Dict) -> Dict[str, Any]:
        """Search for Confluence pages"""
        query = arguments.get("query", "")
        space_key = arguments.get("space_key", None)
        limit = arguments.get("limit", 25)

        cql = f"text ~ \"{query}\""
        if space_key:
            cql += f" and space = {space_key}"

        response = self._make_confluence_request("/content/search", params={
            "cql": cql,
            "limit": limit
        })

        if not response.get("success"):
            return response

        results = response["data"].get("results", [])
        return {
            "success": True,
            "count": len(results),
            "total": response["data"].get("totalSize", 0),
            "pages": results
        }

    # Changelog Implementation

    async def _generate_changelog(self, arguments: Dict) -> Dict[str, Any]:
        """Generate changelog from Jira issues"""
        mode = arguments.get("mode", "sprint")
        output_type = arguments.get("output_type", "markdown")

        # Validate mode-specific parameters
        if mode == "sprint":
            sprint_id = arguments.get("sprint_id")
            if not sprint_id:
                return {"success": False, "error": "sprint_id is required for mode='sprint'"}

            # Get sprint details to extract dates
            sprint_response = await self._get_sprint_details({"sprint_id": sprint_id})
            if not sprint_response.get("success"):
                return sprint_response

            sprint = sprint_response["sprint"]
            from_date_str = sprint.get("startDate", "")
            to_date_str = sprint.get("endDate", "")

            if not from_date_str or not to_date_str:
                return {"success": False, "error": "Sprint does not have start/end dates"}

            # Parse dates
            from_date = date_parser.parse(from_date_str)
            to_date = date_parser.parse(to_date_str)

            # Get issues from sprint using Agile API (more reliable than JQL search)
            url = f"{self.atlassian_url}/rest/agile/1.0/sprint/{sprint_id}/issue"
            headers = {"Accept": "application/json"}

            try:
                response = requests.get(
                    url,
                    auth=self.auth,
                    params={
                        "maxResults": 500,
                        "fields": "summary,description,issuetype,status,key,updated,priority,parent,labels"
                    },
                    timeout=self.timeout,
                    headers=headers
                )

                if response.status_code == 404:
                    return {"success": False, "error": f"Sprint {sprint_id} not found"}

                response.raise_for_status()
                data = response.json()
                all_issues = data.get("issues", [])

                # Filter to only Done/Closed/Merged statuses
                done_statuses = ["done", "closed", "merged", "zakończone", "zamknięte"]
                issues = [
                    issue for issue in all_issues
                    if issue["fields"]["status"]["name"].lower() in done_statuses
                ]

            except requests.exceptions.RequestException as e:
                return {"success": False, "error": "Request failed", "message": str(e)}

        elif mode == "issues":
            issue_keys = arguments.get("issue_keys", [])
            from_date_str = arguments.get("from_date")
            to_date_str = arguments.get("to_date")

            if not issue_keys:
                return {"success": False, "error": "issue_keys is required for mode='issues'"}
            if not from_date_str or not to_date_str:
                return {"success": False, "error": "from_date and to_date are required for mode='issues'"}

            # Parse dates
            try:
                from_date = datetime.strptime(from_date_str, "%Y-%m-%d")
                to_date = datetime.strptime(to_date_str, "%Y-%m-%d")
            except ValueError:
                return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}

            # Get specified issues
            jql = f"key in ({','.join(issue_keys)}) ORDER BY priority DESC, updated DESC"
            issues_response = await self._search_jira_issues({
                "jql": jql,
                "max_results": 500,
                "fields": ["summary", "description", "issuetype", "status", "key", "updated", "priority", "parent", "labels"]
            })

            if not issues_response.get("success"):
                return issues_response

            issues = issues_response["issues"]

        else:
            return {"success": False, "error": f"Invalid mode: {mode}"}

        # Include all issues - sub-tasks are valid changelog entries
        # (Previously filtered out sub-tasks unless parent was included,
        # but this removed too many valid entries)
        filtered_issues = issues

        # Get version parameter
        version = arguments.get("version")

        # Generate changelog content
        changelog_content = self._format_changelog(filtered_issues, from_date, to_date, version=version)

        # Output handling
        if output_type == "markdown":
            output_path = arguments.get("output_path")
            if not output_path:
                return {"success": False, "error": "output_path is required for output_type='markdown'"}

            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(changelog_content)

                return {
                    "success": True,
                    "message": f"Changelog saved to {output_path}",
                    "path": output_path,
                    "issues_count": len(filtered_issues)
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to write file: {str(e)}"}

        elif output_type == "confluence":
            confluence_parent_url = arguments.get("confluence_parent_url")
            if not confluence_parent_url:
                return {"success": False, "error": "confluence_parent_url is required for output_type='confluence'"}

            # Extract parent ID from URL
            parent_id = confluence_parent_url
            if "atlassian.net" in confluence_parent_url:
                match = re.search(r'/pages/(\d+)', confluence_parent_url)
                if match:
                    parent_id = match.group(1)

            # Generate title
            title = arguments.get("confluence_title")
            if not title:
                from_str = from_date.strftime("%d.%m.%Y")
                to_str = to_date.strftime("%d.%m.%Y")
                title = f"Lista zmian w evoSYNC - {from_str} - {to_str}"

            # Convert markdown to Confluence storage format
            confluence_content = self._markdown_to_confluence(changelog_content)

            # Create page
            create_response = await self._create_confluence_page({
                "space_key": self.config.get("confluence_space", "GATEWAY"),
                "title": title,
                "content": confluence_content,
                "parent_id": parent_id
            })

            if not create_response.get("success"):
                return create_response

            return {
                "success": True,
                "message": f"Changelog page created: {create_response['url']}",
                "url": create_response["url"],
                "page_id": create_response["page"]["id"],
                "issues_count": len(filtered_issues)
            }

        else:
            return {"success": False, "error": f"Invalid output_type: {output_type}"}

    def _classify_change_type(self, issue: Dict) -> str:
        """Classify change type based on issue type and description"""
        issue_type = issue["fields"].get("issuetype", {}).get("name", "")
        description_raw = issue["fields"].get("description", "")
        description = self._get_description_text(description_raw) or ""

        # Bug -> Naprawiono
        if issue_type.lower() == "bug":
            return "🔧 Naprawiono"

        # Check keywords in description (case-insensitive)
        description_lower = description.lower()

        # Usunięto patterns
        if re.search(r'\b(usuni[ęe]to|usun[ąa][ćc]|pozbycie si[ęe])\b', description_lower):
            return "➖ Usunięto"

        # Zmieniono patterns
        if re.search(r'\b(zmian[aęe]|zmieniono|modyfikacj[aęe]|poprawka w interfejsie)\b', description_lower):
            return "✏️ Zmieniono"

        # Dodano patterns
        if re.search(r'\b(dodan[oae]|doda[ćc]|now[yae]|now[aąe])\b', description_lower):
            return "➕ Dodano"

        # Default for Task
        if issue_type.lower() in ["zadanie", "task", "story"]:
            return "➕ Dodano"

        return "✏️ Zmieniono"

    def _extract_confluence_links(self, description: str) -> List[Tuple[str, str]]:
        """Extract Confluence links from description with type classification

        Returns list of tuples: (url, type) where type is:
        - 'instrukcja' - user documentation
        - 'techniczna' - technical documentation
        - 'info' - other information
        """
        if not description:
            return []

        # Find all atlassian.net/wiki URLs
        pattern = r'https?://[^/]*atlassian\.net/wiki/[^\s)\]]*'
        links = re.findall(pattern, description)

        classified_links = []
        description_lower = description.lower()

        for link in links:
            link_lower = link.lower()
            # Classify based on URL path or surrounding context
            if any(kw in link_lower for kw in ['instrukcja', 'manual', 'user-guide', 'podrecznik']):
                classified_links.append((link, 'instrukcja'))
            elif any(kw in link_lower for kw in ['tech', 'api', 'developer', 'architektura', 'specyfikacja']):
                classified_links.append((link, 'techniczna'))
            elif 'instrukcj' in description_lower or 'użytkown' in description_lower:
                classified_links.append((link, 'instrukcja'))
            elif 'techniczn' in description_lower or 'implementacj' in description_lower:
                classified_links.append((link, 'techniczna'))
            else:
                classified_links.append((link, 'info'))

        return classified_links

    def _format_doc_links(self, links: List[Tuple[str, str]]) -> str:
        """Format documentation links with appropriate emoji"""
        if not links:
            return ""

        type_emoji = {
            'instrukcja': '📋',
            'techniczna': '🛠️',
            'info': 'ℹ️'
        }

        type_labels = {
            'instrukcja': 'Instrukcja',
            'techniczna': 'Techniczna',
            'info': 'Info'
        }

        formatted = []
        for url, link_type in links:
            emoji = type_emoji.get(link_type, 'ℹ️')
            label = type_labels.get(link_type, 'Info')
            formatted.append(f"[{emoji} {label}]({url})")

        return " ".join(formatted)

    def _get_change_type_order(self, change_type: str) -> int:
        """Get sorting order for change type (lower = first)"""
        order = {
            "➕ Dodano": 0,
            "✏️ Zmieniono": 1,
            "🔧 Naprawiono": 2,
            "➖ Usunięto": 3
        }
        return order.get(change_type, 4)

    def _is_analytical_task(self, issue: Dict) -> bool:
        """Check if issue is analytical/research task for 'Inne osiągnięcia' section"""
        issue_type = issue["fields"].get("issuetype", {}).get("name", "").lower()
        labels = [l.lower() for l in issue["fields"].get("labels", [])]

        # Check issue type
        if issue_type in ["epic", "epik"]:
            return True

        # Check labels
        analytical_labels = ["analiza", "badania", "dokumentacja", "research", "poc"]
        if any(label in labels for label in analytical_labels):
            return True

        return False

    def _format_changelog(self, issues: List[Dict], from_date: datetime, to_date: datetime,
                          version: str = None) -> str:
        """Format issues into changelog markdown table

        Args:
            issues: List of Jira issues
            from_date: Start date of changelog period
            to_date: End date of changelog period
            version: Optional version string for the header
        """
        from_str = from_date.strftime("%d.%m.%Y")
        to_str = to_date.strftime("%d.%m.%Y")

        # Separate regular issues from analytical tasks
        regular_issues = []
        analytical_issues = []

        for issue in issues:
            if self._is_analytical_task(issue):
                analytical_issues.append(issue)
            else:
                regular_issues.append(issue)

        # Sort regular issues by: 1) priority, 2) change type
        priority_order = {"Critical": 0, "Blocker": 0, "High": 1, "Highest": 1, "Medium": 2, "Low": 3, "Lowest": 3}

        def sort_key(issue):
            priority = priority_order.get(
                issue["fields"].get("priority", {}).get("name", "Medium"), 2
            )
            change_type = self._classify_change_type(issue)
            type_order = self._get_change_type_order(change_type)
            return (priority, type_order)

        sorted_issues = sorted(regular_issues, key=sort_key)

        # Header
        version_str = version if version else "[nazwa_wersji]"
        markdown = f"# Zmiany z okresu {from_str} - {to_str}\n\n"
        markdown += f"**Program evoSYNC G0:** {version_str}\n\n"

        # Main table header
        markdown += "| **Zmiana / Opis** | **Typ zmiany** | **Zadanie** | **Dokumentacja** |\n"
        markdown += "|-------------------|----------------|-------------|------------------|\n"

        # Format each regular issue
        for issue in sorted_issues:
            key = issue["key"]
            summary = issue["fields"].get("summary", "")
            description = self._get_description_text(issue["fields"].get("description", ""))

            # Classify change type
            change_type = self._classify_change_type(issue)

            # Extract and format Confluence links with classification
            conf_links = self._extract_confluence_links(description)
            doc_column = self._format_doc_links(conf_links)

            # Format task link
            task_link = f"[{key}]({self.atlassian_url}/browse/{key})"

            # Escape pipe characters in summary
            summary_escaped = summary.replace("|", "\\|")

            # Add row
            markdown += f"| {summary_escaped} | {change_type} | {task_link} | {doc_column} |\n"

        # Add "Inne osiągnięcia" section if there are analytical tasks
        if analytical_issues:
            markdown += "\n## Inne osiągnięcia\n\n"
            markdown += "| **Opis** | **Typ** | **Zadanie** |\n"
            markdown += "|----------|---------|-------------|\n"

            for issue in analytical_issues:
                key = issue["key"]
                summary = issue["fields"].get("summary", "").replace("|", "\\|")
                issue_type = issue["fields"].get("issuetype", {}).get("name", "")
                task_link = f"[{key}]({self.atlassian_url}/browse/{key})"

                markdown += f"| {summary} | {issue_type} | {task_link} |\n"

        return markdown

    def _get_description_text(self, description) -> str:
        """Extract plain text from Jira description (handles ADF format)"""
        if not description:
            return ""

        # If description is a string, return it
        if isinstance(description, str):
            return description

        # If description is ADF (Atlassian Document Format), extract text
        if isinstance(description, dict):
            return self._extract_text_from_adf(description)

        return str(description)

    def _extract_text_from_adf(self, adf: Dict) -> str:
        """Recursively extract text from Atlassian Document Format"""
        text_parts = []

        if isinstance(adf, dict):
            if adf.get("type") == "text":
                text_parts.append(adf.get("text", ""))
            if "content" in adf:
                for item in adf["content"]:
                    text_parts.append(self._extract_text_from_adf(item))

        elif isinstance(adf, list):
            for item in adf:
                text_parts.append(self._extract_text_from_adf(item))

        return " ".join(text_parts)

    def _markdown_to_confluence(self, markdown: str) -> str:
        """Convert markdown to Confluence storage format (HTML)"""
        # Simple conversion for table and headers
        html = markdown

        # Convert headers
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^\*\*(.+?)\*\*', r'<strong>\1</strong>', html, flags=re.MULTILINE)

        # Convert markdown table to HTML table
        lines = html.split('\n')
        in_table = False
        table_html = []

        for line in lines:
            if line.startswith('|'):
                if not in_table:
                    table_html.append('<table><tbody>')
                    in_table = True

                # Skip separator line
                if '---' in line:
                    continue

                # Parse table row
                cells = [cell.strip() for cell in line.split('|')[1:-1]]

                # First row is header
                if len(table_html) == 1:
                    table_html.append('<tr>')
                    for cell in cells:
                        # Convert markdown links and bold
                        cell = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', cell)
                        cell = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', cell)
                        table_html.append(f'<th>{cell}</th>')
                    table_html.append('</tr>')
                else:
                    table_html.append('<tr>')
                    for cell in cells:
                        # Convert markdown links and bold
                        cell = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', cell)
                        cell = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', cell)
                        table_html.append(f'<td>{cell}</td>')
                    table_html.append('</tr>')
            else:
                if in_table:
                    table_html.append('</tbody></table>')
                    in_table = False
                if line.strip():
                    table_html.append(line)

        if in_table:
            table_html.append('</tbody></table>')

        return '\n'.join(table_html)

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
    server = AtlassianMCPServer(config_path)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
