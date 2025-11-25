#!/usr/bin/env python3
"""
GitLab MCP Server
Serwer MCP do integracji z GitLab API - pobieranie merge requests i informacji o projektach.
"""

import json
import os
import sys
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
import requests
from urllib.parse import quote

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio


class CCodeReviewer:
    """Analizator kodu C do code review"""

    def __init__(self, config_path: str):
        self.config = self._load_review_config(config_path)
        self.cppcheck_enabled = self._check_cppcheck_available()

    def _load_review_config(self, config_path: str) -> Dict[str, Any]:
        """Ładuje konfigurację code review"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Zwraca domyślną konfigurację"""
        return {
            "formatting": {"max_line_length": 80},
            "unsafe_functions": {"functions": []},
            "code_patterns": {"patterns": []},
            "naming_conventions": {},
            "cppcheck": {
                "enabled": True,
                "checks": ["error", "warning", "performance", "portability"]
            }
        }

    def _check_cppcheck_available(self) -> bool:
        """Sprawdza czy cppcheck jest dostępny"""
        try:
            result = subprocess.run(
                ['cppcheck', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _analyze_with_cppcheck(self, file_content: str, file_path: str) -> List[Dict[str, Any]]:
        """Analizuje kod używając cppcheck"""
        if not self.cppcheck_enabled:
            return []

        if not self.config.get("cppcheck", {}).get("enabled", True):
            return []

        issues = []

        try:
            # Utwórz tymczasowy plik
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name

            # Uruchom cppcheck
            enabled_checks = self.config.get("cppcheck", {}).get("checks", ["error", "warning"])
            enable_param = ','.join(enabled_checks)

            result = subprocess.run(
                ['cppcheck', '--enable=' + enable_param, '--xml', tmp_file_path],
                capture_output=True,
                timeout=30,
                text=True
            )

            # Parsuj wyniki XML
            if result.stderr:
                try:
                    root = ET.fromstring(result.stderr)
                    for error in root.findall('.//error'):
                        severity = error.get('severity', 'warning')
                        msg = error.get('msg', '')
                        verbose_msg = error.get('verbose', msg)
                        error_id = error.get('id', '')

                        # Mapuj severity cppcheck na nasze poziomy
                        severity_map = {
                            'error': 'critical',
                            'warning': 'warning',
                            'style': 'info',
                            'performance': 'warning',
                            'portability': 'info',
                            'information': 'info'
                        }
                        mapped_severity = severity_map.get(severity, 'warning')

                        location = error.find('location')
                        if location is not None:
                            line = int(location.get('line', 0))
                            issues.append({
                                'severity': mapped_severity,
                                'line': line,
                                'type': 'cppcheck_' + error_id,
                                'message': f"[cppcheck] {verbose_msg}",
                                'suggestion': f"cppcheck wykrył potencjalny problem (ID: {error_id})"
                            })
                except ET.ParseError:
                    pass

            # Usuń tymczasowy plik
            os.unlink(tmp_file_path)

        except (subprocess.TimeoutExpired, OSError) as e:
            # Jeśli cppcheck zawiedzie, nie przerywaj analizy
            pass

        return issues

    def review_diff(self, diff_text: str, file_path: str) -> Dict[str, Any]:
        """Analizuje diff i zwraca znalezione problemy"""
        issues = {
            "critical": [],
            "error": [],
            "warning": [],
            "info": []
        }

        if not (file_path.endswith('.c') or file_path.endswith('.h')):
            return issues

        lines = diff_text.split('\n')
        line_number = 0

        for line in lines:
            # Parsuj numer linii z diffa
            if line.startswith('@@'):
                match = re.search(r'\+(\d+)', line)
                if match:
                    line_number = int(match.group(1))
                continue

            # Analizuj tylko dodane linie
            if not line.startswith('+') or line.startswith('+++'):
                if not line.startswith('-'):
                    line_number += 1
                continue

            code_line = line[1:]  # Usuń '+'

            # Sprawdzanie długości linii
            if len(code_line) > self.config["formatting"]["max_line_length"]:
                issues["warning"].append({
                    "file": file_path,
                    "line": line_number,
                    "type": "line_length",
                    "message": f"Linia przekracza {self.config['formatting']['max_line_length']} znaków (długość: {len(code_line)})",
                    "code": code_line.strip()
                })

            # Sprawdzanie niebezpiecznych funkcji
            for func in self.config.get("unsafe_functions", {}).get("functions", []):
                if re.search(rf'\b{func["name"]}\s*\(', code_line):
                    issues[func["severity"]].append({
                        "file": file_path,
                        "line": line_number,
                        "type": "unsafe_function",
                        "message": func["message"],
                        "suggestion": func.get("suggestion", ""),
                        "code": code_line.strip()
                    })

            # Sprawdzanie wzorców kodu
            for pattern in self.config.get("code_patterns", {}).get("patterns", []):
                if re.search(pattern["pattern"], code_line):
                    issues[pattern["severity"]].append({
                        "file": file_path,
                        "line": line_number,
                        "type": pattern["name"],
                        "message": pattern["message"],
                        "suggestion": pattern.get("suggestion", ""),
                        "code": code_line.strip()
                    })

            # Sprawdzanie nazewnictwa dla deklaracji funkcji
            if re.match(r'^\s*\w+\s+\w+\s*\([^)]*\)\s*\{?\s*$', code_line):
                self._check_function_naming(code_line, file_path, line_number, issues)

            # Sprawdzanie nazewnictwa dla struktur
            if re.search(r'typedef\s+struct', code_line):
                self._check_struct_naming(code_line, file_path, line_number, issues)

            # Sprawdzanie nazewnictwa dla enumów
            if re.search(r'typedef\s+enum', code_line):
                self._check_enum_naming(code_line, file_path, line_number, issues)

            line_number += 1

        # Analiza z cppcheck - rekonstruuj cały plik z dodanymi liniami
        if self.cppcheck_enabled:
            full_code = self._reconstruct_code_from_diff(diff_text)
            if full_code:
                cppcheck_issues = self._analyze_with_cppcheck(full_code, file_path)
                for issue in cppcheck_issues:
                    severity = issue.pop('severity')
                    issue['file'] = file_path
                    # Dodaj tylko jeśli linia była zmodyfikowana w diff
                    issues[severity].append(issue)

        return issues

    def _reconstruct_code_from_diff(self, diff_text: str) -> str:
        """Rekonstruuje kod z dodanymi liniami z diffa"""
        code_lines = []
        for line in diff_text.split('\n'):
            if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
                continue
            if line.startswith('+'):
                code_lines.append(line[1:])  # Dodaj nowe linie
            elif not line.startswith('-'):
                code_lines.append(line)  # Dodaj kontekst
        return '\n'.join(code_lines)

    def _check_function_naming(self, code_line: str, file_path: str, line_number: int, issues: Dict):
        """Sprawdza nazewnictwo funkcji"""
        # Prosta heurystyka - sprawdź czy funkcja zaczyna się od 'static'
        is_static = 'static' in code_line
        func_match = re.search(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', code_line)

        if func_match:
            func_name = func_match.group(1)

            if is_static:
                # Funkcje static powinny być snake_case
                pattern = self.config.get("naming_conventions", {}).get("static_functions", {})
                if pattern and not re.match(pattern.get("pattern", ".*"), func_name):
                    issues[pattern.get("severity", "info")].append({
                        "file": file_path,
                        "line": line_number,
                        "type": "naming_convention",
                        "message": f"Funkcja static '{func_name}' nie spełnia konwencji: {pattern.get('description', '')}",
                        "code": code_line.strip()
                    })
            else:
                # Funkcje publiczne powinny być PascalCase
                pattern = self.config.get("naming_conventions", {}).get("public_functions", {})
                if pattern and not re.match(pattern.get("pattern", ".*"), func_name):
                    issues[pattern.get("severity", "info")].append({
                        "file": file_path,
                        "line": line_number,
                        "type": "naming_convention",
                        "message": f"Funkcja publiczna '{func_name}' nie spełnia konwencji: {pattern.get('description', '')}",
                        "code": code_line.strip()
                    })

    def _check_struct_naming(self, code_line: str, file_path: str, line_number: int, issues: Dict):
        """Sprawdza nazewnictwo struktur"""
        # Szukamy nazwy struktury po typedef struct
        struct_match = re.search(r'typedef\s+struct\s+\{?\s*(\w+)?', code_line)
        if struct_match and struct_match.group(1):
            struct_name = struct_match.group(1)
            pattern = self.config.get("naming_conventions", {}).get("structs", {})
            if pattern and not re.match(pattern.get("pattern", ".*"), struct_name):
                issues[pattern.get("severity", "info")].append({
                    "file": file_path,
                    "line": line_number,
                    "type": "naming_convention",
                    "message": f"Struktura '{struct_name}' nie spełnia konwencji: {pattern.get('description', '')}",
                    "code": code_line.strip()
                })

    def _check_enum_naming(self, code_line: str, file_path: str, line_number: int, issues: Dict):
        """Sprawdza nazewnictwo enumów"""
        enum_match = re.search(r'typedef\s+enum\s+\{?\s*(\w+)?', code_line)
        if enum_match and enum_match.group(1):
            enum_name = enum_match.group(1)
            pattern = self.config.get("naming_conventions", {}).get("enums", {})
            if pattern and not re.match(pattern.get("pattern", ".*"), enum_name):
                issues[pattern.get("severity", "info")].append({
                    "file": file_path,
                    "line": line_number,
                    "type": "naming_convention",
                    "message": f"Enum '{enum_name}' nie spełnia konwencji: {pattern.get('description', '')}",
                    "code": code_line.strip()
                })

    def _aggregate_issues(self, issues: Dict[str, List]) -> Dict[str, Any]:
        """Agreguje identyczne problemy"""
        aggregated = {}

        for severity in issues:
            aggregated[severity] = []
            issue_groups = {}

            for issue in issues[severity]:
                # Klucz grupowania: typ + wiadomość (bez kodu i linii)
                key = (issue.get('type', ''), issue.get('message', ''))

                if key not in issue_groups:
                    issue_groups[key] = []
                issue_groups[key].append(issue)

            # Dla każdej grupy: pokaż 2 pierwsze wystąpienia + liczbę pozostałych
            for (issue_type, message), group in issue_groups.items():
                if len(group) == 1:
                    aggregated[severity].append(group[0])
                else:
                    # Agreguj: pokaż 2 pierwsze + podsumowanie
                    aggregated[severity].append({
                        "type": issue_type,
                        "message": message,
                        "occurrences": len(group),
                        "examples": [
                            {
                                "file": g.get("file"),
                                "line": g.get("line"),
                                "code": g.get("code", "")
                            }
                            for g in group[:2]  # Tylko 2 pierwsze
                        ],
                        "additional_files": list(set(g.get("file") for g in group[2:])) if len(group) > 2 else []
                    })

        return aggregated

    def format_review_report(self, issues: Dict[str, List], mr_info: Dict, detail_level: str = "full",
                           page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """Formatuje raport z code review

        Args:
            issues: Słownik problemów pogrupowanych po severity
            mr_info: Informacje o merge requeście
            detail_level: Poziom szczegółowości - "summary", "aggregated", "paginated", "full"
            page: Numer strony (dla paginated)
            per_page: Liczba problemów na stronę (dla paginated)
        """
        total_issues = sum(len(issues[severity]) for severity in issues)

        summary = {
            "total_issues": total_issues,
            "critical": len(issues["critical"]),
            "error": len(issues["error"]),
            "warning": len(issues["warning"]),
            "info": len(issues["info"])
        }

        # Podział per plik
        by_file = {}
        for severity in issues:
            for issue in issues[severity]:
                file_path = issue.get("file", "unknown")
                if file_path not in by_file:
                    by_file[file_path] = {"critical": 0, "error": 0, "warning": 0, "info": 0}
                by_file[file_path][severity] += 1

        summary["by_file"] = by_file

        base_response = {
            "success": True,
            "merge_request": mr_info,
            "summary": summary,
            "detail_level": detail_level
        }

        if detail_level == "summary":
            # Tylko statystyki + top 10 najważniejszych problemów
            top_issues = []
            for severity in ["critical", "error", "warning", "info"]:
                for issue in issues[severity][:10]:  # Max 10 z każdego poziomu
                    top_issues.append({
                        "severity": severity,
                        **issue
                    })
                    if len(top_issues) >= 10:
                        break
                if len(top_issues) >= 10:
                    break

            base_response["top_issues"] = top_issues
            return base_response

        elif detail_level == "aggregated":
            # Agreguj identyczne problemy
            aggregated = self._aggregate_issues(issues)
            base_response["issues"] = aggregated
            return base_response

        elif detail_level == "paginated":
            # Zwracaj partiami
            all_issues_flat = []
            for severity in ["critical", "error", "warning", "info"]:
                for issue in issues[severity]:
                    all_issues_flat.append({
                        "severity": severity,
                        **issue
                    })

            # Paginacja
            start = (page - 1) * per_page
            end = start + per_page
            paginated_issues = all_issues_flat[start:end]

            base_response["issues"] = paginated_issues
            base_response["pagination"] = {
                "page": page,
                "per_page": per_page,
                "total_issues": len(all_issues_flat),
                "total_pages": (len(all_issues_flat) + per_page - 1) // per_page
            }
            return base_response

        else:  # full
            base_response["issues"] = issues
            return base_response


class GitLabServer:
    def __init__(self):
        self.server = Server("gitlab-mcp-server")
        self.config = self._load_config()
        self.gitlab_url = self.config.get("gitlab_url", "").rstrip("/")
        self.api_token = self.config.get("api_token", "")
        self.default_state = self.config.get("default_state", "opened")
        self.default_scope = self.config.get("default_scope", "all")
        self.per_page = self.config.get("per_page", 20)
        self.verify_ssl = self.config.get("verify_ssl", True)
        self.timeout = self.config.get("timeout", 30)
        self.watched_projects = self.config.get("watched_projects", [])

        # Inicjalizacja code reviewera
        review_config_path = os.path.join(os.path.dirname(__file__), "code-review-config.json")
        self.code_reviewer = CCodeReviewer(review_config_path)

        self._setup_handlers()

    def _load_config(self) -> Dict[str, Any]:
        """Ładuje konfigurację z pliku config.json"""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        secrets_path = os.path.join(os.path.dirname(__file__), "secrets.json")

        config = {}

        # Ładuj główny config
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"Ostrzeżenie: Nie znaleziono {config_path}", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"Błąd parsowania config.json: {e}", file=sys.stderr)

        # Ładuj secrets (nadpisuje wartości z config)
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                secrets = json.load(f)
                config.update(secrets)
        except FileNotFoundError:
            print(f"Ostrzeżenie: Nie znaleziono {secrets_path}. Utwórz ten plik z api_token.", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"Błąd parsowania secrets.json: {e}", file=sys.stderr)

        return config

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Wykonuje zapytanie do GitLab API"""
        url = f"{self.gitlab_url}/api/v4{endpoint}"
        headers = {
            "PRIVATE-TOKEN": self.api_token,
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json(),
                "total_pages": response.headers.get("X-Total-Pages"),
                "total": response.headers.get("X-Total")
            }
        except requests.exceptions.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP Error: {e.response.status_code}",
                "message": str(e)
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

    def _setup_handlers(self):
        """Konfiguruje handlery MCP"""

        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """Lista dostępnych narzędzi"""
            return [
                types.Tool(
                    name="list_projects",
                    description="Listuje wszystkie dostępne projekty/repozytoria w GitLab. Można filtrować po nazwie i widoczności.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search": {
                                "type": "string",
                                "description": "Opcjonalny: wyszukaj projekty po nazwie"
                            },
                            "visibility": {
                                "type": "string",
                                "enum": ["public", "internal", "private"],
                                "description": "Opcjonalny: filtruj po widoczności projektu"
                            },
                            "owned": {
                                "type": "boolean",
                                "description": "Opcjonalny: pokaż tylko projekty, których jesteś właścicielem"
                            },
                            "per_page": {
                                "type": "number",
                                "description": "Liczba wyników na stronę (domyślnie: 20)"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="fetch_merge_requests",
                    description="Pobiera wszystkie merge requesty dostępne dla zalogowanego użytkownika. Można filtrować po statusie, scope, labelach itp.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "state": {
                                "type": "string",
                                "enum": ["opened", "closed", "merged", "locked", "all"],
                                "description": "Status merge requestów (domyślnie: opened)"
                            },
                            "scope": {
                                "type": "string",
                                "enum": ["created_by_me", "assigned_to_me", "all"],
                                "description": "Zakres merge requestów (domyślnie: all)"
                            },
                            "labels": {
                                "type": "string",
                                "description": "Opcjonalny: filtruj po labelach (rozdzielone przecinkami)"
                            },
                            "search": {
                                "type": "string",
                                "description": "Opcjonalny: wyszukaj w tytule i opisie"
                            },
                            "per_page": {
                                "type": "number",
                                "description": "Liczba wyników na stronę (domyślnie: 20)"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="fetch_project_merge_requests",
                    description="Pobiera merge requesty dla konkretnego projektu lub projektów. Wymaga podania ID projektu lub listy ID projektów.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "ID projektu lub ścieżka projektu (namespace/project-name)"
                            },
                            "project_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Lista ID projektów (alternatywa do project_id)"
                            },
                            "state": {
                                "type": "string",
                                "enum": ["opened", "closed", "merged", "locked", "all"],
                                "description": "Status merge requestów (domyślnie: opened)"
                            },
                            "author_username": {
                                "type": "string",
                                "description": "Opcjonalny: filtruj po autorze"
                            },
                            "assignee_username": {
                                "type": "string",
                                "description": "Opcjonalny: filtruj po przypisanym użytkowniku"
                            },
                            "labels": {
                                "type": "string",
                                "description": "Opcjonalny: filtruj po labelach"
                            },
                            "per_page": {
                                "type": "number",
                                "description": "Liczba wyników na stronę (domyślnie: 20)"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="fetch_merge_request_details",
                    description="Pobiera szczegółowe informacje o konkretnym merge requeście, włącznie z komentarzami, zmianami i statusem pipeline.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "ID projektu lub ścieżka projektu"
                            },
                            "merge_request_iid": {
                                "type": "number",
                                "description": "IID (wewnętrzne ID) merge requesta w projekcie"
                            }
                        },
                        "required": ["project_id", "merge_request_iid"]
                    }
                ),
                types.Tool(
                    name="search_merge_requests",
                    description="Zaawansowane wyszukiwanie merge requestów z filtrowaniem po dacie utworzenia/aktualizacji, labelach i tekście.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search": {
                                "type": "string",
                                "description": "Tekst do wyszukania w tytule i opisie"
                            },
                            "state": {
                                "type": "string",
                                "enum": ["opened", "closed", "merged", "locked", "all"],
                                "description": "Status merge requestów"
                            },
                            "created_after": {
                                "type": "string",
                                "description": "Opcjonalny: data w formacie ISO 8601 (np. 2024-01-01T00:00:00Z)"
                            },
                            "created_before": {
                                "type": "string",
                                "description": "Opcjonalny: data w formacie ISO 8601"
                            },
                            "updated_after": {
                                "type": "string",
                                "description": "Opcjonalny: data w formacie ISO 8601"
                            },
                            "updated_before": {
                                "type": "string",
                                "description": "Opcjonalny: data w formacie ISO 8601"
                            },
                            "labels": {
                                "type": "string",
                                "description": "Opcjonalny: filtruj po labelach"
                            },
                            "per_page": {
                                "type": "number",
                                "description": "Liczba wyników na stronę"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="fetch_merge_request_changes",
                    description="Pobiera listę zmodyfikowanych plików w ramach merge requesta wraz z podstawowymi statystykami (dodane/usunięte linie, typ zmiany).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "ID projektu lub ścieżka projektu"
                            },
                            "merge_request_iid": {
                                "type": "number",
                                "description": "IID (wewnętrzne ID) merge requesta w projekcie"
                            }
                        },
                        "required": ["project_id", "merge_request_iid"]
                    }
                ),
                types.Tool(
                    name="fetch_merge_request_diffs",
                    description="Pobiera szczegółowe zmiany (diff) dla wszystkich plików w merge requeście. Zwraca pełny diff w formacie unified diff.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "ID projektu lub ścieżka projektu"
                            },
                            "merge_request_iid": {
                                "type": "number",
                                "description": "IID (wewnętrzne ID) merge requesta w projekcie"
                            }
                        },
                        "required": ["project_id", "merge_request_iid"]
                    }
                ),
                types.Tool(
                    name="review_merge_request",
                    description="Wykonuje code review merge requesta dla projektów w C. Analizuje kod pod kątem: formatowania, nazewnictwa, niebezpiecznych funkcji, potencjalnych błędów. Zwraca szczegółowy raport z poziomami: critical/error/warning/info. Wspiera różne poziomy szczegółowości dla dużych MR.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "ID projektu lub ścieżka projektu"
                            },
                            "merge_request_iid": {
                                "type": "number",
                                "description": "IID (wewnętrzne ID) merge requesta w projekcie"
                            },
                            "detail_level": {
                                "type": "string",
                                "enum": ["summary", "aggregated", "paginated", "full"],
                                "description": "Poziom szczegółowości: summary (statystyki + top 10), aggregated (zagregowane identyczne problemy), paginated (wyniki partiami), full (pełny raport - domyślnie)"
                            },
                            "page": {
                                "type": "number",
                                "description": "Numer strony (tylko dla detail_level=paginated, domyślnie: 1)"
                            },
                            "per_page": {
                                "type": "number",
                                "description": "Liczba problemów na stronę (tylko dla detail_level=paginated, domyślnie: 50)"
                            }
                        },
                        "required": ["project_id", "merge_request_iid"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict | None
        ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
            """Obsługa wywołań narzędzi"""

            if not arguments:
                arguments = {}

            try:
                if name == "list_projects":
                    result = self._list_projects(arguments)
                elif name == "fetch_merge_requests":
                    result = self._fetch_merge_requests(arguments)
                elif name == "fetch_project_merge_requests":
                    result = self._fetch_project_merge_requests(arguments)
                elif name == "fetch_merge_request_details":
                    result = self._fetch_merge_request_details(arguments)
                elif name == "search_merge_requests":
                    result = self._search_merge_requests(arguments)
                elif name == "fetch_merge_request_changes":
                    result = self._fetch_merge_request_changes(arguments)
                elif name == "fetch_merge_request_diffs":
                    result = self._fetch_merge_request_diffs(arguments)
                elif name == "review_merge_request":
                    result = self._review_merge_request(arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False)
                )]

            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Internal error",
                        "message": str(e)
                    }, indent=2, ensure_ascii=False)
                )]

    def _list_projects(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Listuje projekty"""
        params = {
            "per_page": args.get("per_page", self.per_page),
            "simple": False,
            "membership": True
        }

        if "search" in args:
            params["search"] = args["search"]

        if "visibility" in args:
            params["visibility"] = args["visibility"]

        if args.get("owned", False):
            params["owned"] = True

        result = self._make_request("/projects", params)

        if result["success"]:
            projects = result["data"]
            return {
                "success": True,
                "count": len(projects),
                "total": result.get("total", "unknown"),
                "projects": [
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "path": p["path"],
                        "path_with_namespace": p["path_with_namespace"],
                        "description": p.get("description", ""),
                        "visibility": p.get("visibility", ""),
                        "web_url": p["web_url"],
                        "default_branch": p.get("default_branch", ""),
                        "last_activity_at": p.get("last_activity_at", "")
                    }
                    for p in projects
                ]
            }
        else:
            return result

    def _fetch_merge_requests(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Pobiera merge requesty"""
        params = {
            "state": args.get("state", self.default_state),
            "scope": args.get("scope", self.default_scope),
            "per_page": args.get("per_page", self.per_page)
        }

        if "labels" in args:
            params["labels"] = args["labels"]

        if "search" in args:
            params["search"] = args["search"]

        result = self._make_request("/merge_requests", params)

        if result["success"]:
            merge_requests = result["data"]
            return {
                "success": True,
                "count": len(merge_requests),
                "total": result.get("total", "unknown"),
                "merge_requests": [self._format_merge_request(mr) for mr in merge_requests]
            }
        else:
            return result

    def _fetch_project_merge_requests(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Pobiera merge requesty dla projektu/projektów"""
        project_id = args.get("project_id")
        project_ids = args.get("project_ids", [])

        if not project_id and not project_ids:
            return {
                "success": False,
                "error": "Missing required parameter",
                "message": "Musisz podać 'project_id' lub 'project_ids'"
            }

        # Jeśli podano pojedynczy projekt
        if project_id:
            project_ids = [project_id]

        all_merge_requests = []

        for pid in project_ids:
            # Enkoduj ID projektu dla URL
            encoded_pid = quote(str(pid), safe='')

            params = {
                "state": args.get("state", self.default_state),
                "per_page": args.get("per_page", self.per_page)
            }

            if "author_username" in args:
                params["author_username"] = args["author_username"]

            if "assignee_username" in args:
                params["assignee_username"] = args["assignee_username"]

            if "labels" in args:
                params["labels"] = args["labels"]

            result = self._make_request(f"/projects/{encoded_pid}/merge_requests", params)

            if result["success"]:
                all_merge_requests.extend(result["data"])
            else:
                return result

        return {
            "success": True,
            "count": len(all_merge_requests),
            "projects_searched": len(project_ids),
            "merge_requests": [self._format_merge_request(mr) for mr in all_merge_requests]
        }

    def _fetch_merge_request_details(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Pobiera szczegóły merge requesta"""
        project_id = args.get("project_id")
        mr_iid = args.get("merge_request_iid")

        if not project_id or not mr_iid:
            return {
                "success": False,
                "error": "Missing required parameters",
                "message": "Wymagane: 'project_id' i 'merge_request_iid'"
            }

        encoded_pid = quote(str(project_id), safe='')
        result = self._make_request(f"/projects/{encoded_pid}/merge_requests/{mr_iid}")

        if result["success"]:
            mr = result["data"]
            return {
                "success": True,
                "merge_request": self._format_merge_request_detailed(mr)
            }
        else:
            return result

    def _search_merge_requests(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wyszukuje merge requesty"""
        params = {
            "per_page": args.get("per_page", self.per_page)
        }

        if "search" in args:
            params["search"] = args["search"]

        if "state" in args:
            params["state"] = args["state"]
        else:
            params["state"] = self.default_state

        if "created_after" in args:
            params["created_after"] = args["created_after"]

        if "created_before" in args:
            params["created_before"] = args["created_before"]

        if "updated_after" in args:
            params["updated_after"] = args["updated_after"]

        if "updated_before" in args:
            params["updated_before"] = args["updated_before"]

        if "labels" in args:
            params["labels"] = args["labels"]

        result = self._make_request("/merge_requests", params)

        if result["success"]:
            merge_requests = result["data"]
            return {
                "success": True,
                "count": len(merge_requests),
                "total": result.get("total", "unknown"),
                "merge_requests": [self._format_merge_request(mr) for mr in merge_requests]
            }
        else:
            return result

    def _format_merge_request(self, mr: Dict[str, Any]) -> Dict[str, Any]:
        """Formatuje podstawowe informacje o merge requeście"""
        return {
            "id": mr.get("id"),
            "iid": mr.get("iid"),
            "title": mr.get("title"),
            "description": mr.get("description", ""),
            "state": mr.get("state"),
            "merged_by": mr.get("merged_by", {}).get("username") if mr.get("merged_by") else None,
            "merged_at": mr.get("merged_at"),
            "created_at": mr.get("created_at"),
            "updated_at": mr.get("updated_at"),
            "target_branch": mr.get("target_branch"),
            "source_branch": mr.get("source_branch"),
            "author": {
                "username": mr.get("author", {}).get("username"),
                "name": mr.get("author", {}).get("name")
            },
            "assignees": [
                {"username": a.get("username"), "name": a.get("name")}
                for a in mr.get("assignees", [])
            ],
            "reviewers": [
                {"username": r.get("username"), "name": r.get("name")}
                for r in mr.get("reviewers", [])
            ],
            "labels": mr.get("labels", []),
            "web_url": mr.get("web_url"),
            "project_id": mr.get("project_id"),
            "draft": mr.get("draft", False),
            "work_in_progress": mr.get("work_in_progress", False)
        }

    def _format_merge_request_detailed(self, mr: Dict[str, Any]) -> Dict[str, Any]:
        """Formatuje szczegółowe informacje o merge requeście"""
        basic = self._format_merge_request(mr)
        basic.update({
            "detailed_merge_status": mr.get("detailed_merge_status"),
            "merge_status": mr.get("merge_status"),
            "sha": mr.get("sha"),
            "merge_commit_sha": mr.get("merge_commit_sha"),
            "squash_commit_sha": mr.get("squash_commit_sha"),
            "user_notes_count": mr.get("user_notes_count", 0),
            "upvotes": mr.get("upvotes", 0),
            "downvotes": mr.get("downvotes", 0),
            "changes_count": mr.get("changes_count"),
            "should_remove_source_branch": mr.get("should_remove_source_branch"),
            "force_remove_source_branch": mr.get("force_remove_source_branch"),
            "squash": mr.get("squash", False),
            "has_conflicts": mr.get("has_conflicts", False),
            "blocking_discussions_resolved": mr.get("blocking_discussions_resolved", True),
            "pipeline": mr.get("head_pipeline"),
            "milestone": mr.get("milestone"),
            "time_stats": mr.get("time_stats")
        })
        return basic

    def _fetch_merge_request_changes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Pobiera listę zmodyfikowanych plików w merge requeście"""
        project_id = args.get("project_id")
        mr_iid = args.get("merge_request_iid")

        if not project_id or not mr_iid:
            return {
                "success": False,
                "error": "Missing required parameters",
                "message": "Wymagane: 'project_id' i 'merge_request_iid'"
            }

        encoded_pid = quote(str(project_id), safe='')
        result = self._make_request(f"/projects/{encoded_pid}/merge_requests/{mr_iid}/changes")

        if result["success"]:
            data = result["data"]
            changes = data.get("changes", [])

            return {
                "success": True,
                "merge_request": {
                    "id": data.get("id"),
                    "iid": data.get("iid"),
                    "title": data.get("title"),
                    "state": data.get("state"),
                    "web_url": data.get("web_url")
                },
                "changes_count": len(changes),
                "files": [
                    {
                        "old_path": change.get("old_path"),
                        "new_path": change.get("new_path"),
                        "a_mode": change.get("a_mode"),
                        "b_mode": change.get("b_mode"),
                        "new_file": change.get("new_file", False),
                        "renamed_file": change.get("renamed_file", False),
                        "deleted_file": change.get("deleted_file", False),
                        "diff_size": len(change.get("diff", ""))
                    }
                    for change in changes
                ]
            }
        else:
            return result

    def _fetch_merge_request_diffs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Pobiera szczegółowe diffy dla merge requesta"""
        project_id = args.get("project_id")
        mr_iid = args.get("merge_request_iid")

        if not project_id or not mr_iid:
            return {
                "success": False,
                "error": "Missing required parameters",
                "message": "Wymagane: 'project_id' i 'merge_request_iid'"
            }

        encoded_pid = quote(str(project_id), safe='')
        result = self._make_request(f"/projects/{encoded_pid}/merge_requests/{mr_iid}/changes")

        if result["success"]:
            data = result["data"]
            changes = data.get("changes", [])

            return {
                "success": True,
                "merge_request": {
                    "id": data.get("id"),
                    "iid": data.get("iid"),
                    "title": data.get("title"),
                    "state": data.get("state"),
                    "web_url": data.get("web_url")
                },
                "changes_count": len(changes),
                "diffs": [
                    {
                        "old_path": change.get("old_path"),
                        "new_path": change.get("new_path"),
                        "new_file": change.get("new_file", False),
                        "renamed_file": change.get("renamed_file", False),
                        "deleted_file": change.get("deleted_file", False),
                        "diff": change.get("diff", "")
                    }
                    for change in changes
                ]
            }
        else:
            return result

    def _review_merge_request(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wykonuje code review merge requesta"""
        project_id = args.get("project_id")
        mr_iid = args.get("merge_request_iid")
        detail_level = args.get("detail_level", "aggregated")  # Domyślnie aggregated dla dużych MR
        page = args.get("page", 1)
        per_page = args.get("per_page", 50)

        if not project_id or not mr_iid:
            return {
                "success": False,
                "error": "Missing required parameters",
                "message": "Wymagane: 'project_id' i 'merge_request_iid'"
            }

        # Pobierz diffy z merge requesta
        encoded_pid = quote(str(project_id), safe='')
        result = self._make_request(f"/projects/{encoded_pid}/merge_requests/{mr_iid}/changes")

        if not result["success"]:
            return result

        data = result["data"]
        changes = data.get("changes", [])

        # Zbierz wszystkie problemy z wszystkich plików
        all_issues = {
            "critical": [],
            "error": [],
            "warning": [],
            "info": []
        }

        files_reviewed = 0
        c_files_reviewed = 0

        for change in changes:
            file_path = change.get("new_path", "")
            diff = change.get("diff", "")

            # Analizuj tylko pliki C/H
            if file_path.endswith('.c') or file_path.endswith('.h'):
                c_files_reviewed += 1
                file_issues = self.code_reviewer.review_diff(diff, file_path)

                # Dodaj problemy do globalnej listy
                for severity in all_issues:
                    all_issues[severity].extend(file_issues[severity])

            files_reviewed += 1

        # Przygotuj informacje o MR
        mr_info = {
            "id": data.get("id"),
            "iid": data.get("iid"),
            "title": data.get("title"),
            "state": data.get("state"),
            "web_url": data.get("web_url"),
            "files_total": files_reviewed,
            "c_files_reviewed": c_files_reviewed
        }

        # Zwróć raport z wybranym poziomem szczegółowości
        return self.code_reviewer.format_review_report(
            all_issues, mr_info,
            detail_level=detail_level,
            page=page,
            per_page=per_page
        )

    async def run(self):
        """Uruchamia serwer MCP"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="gitlab-mcp-server",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )


def main():
    """Główna funkcja"""
    server = GitLabServer()
    import asyncio
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
