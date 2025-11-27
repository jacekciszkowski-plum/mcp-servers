# Atlassian MCP Server

Serwer MCP do integracji z Atlassian Jira i Confluence. Umożliwia wyszukiwanie zadań Jira, odczyt stron Confluence oraz automatyczne generowanie changelogów dla projektu evoSYNC.

## Funkcje

✅ **Jira Integration**
- Wyszukiwanie zadań używając zapytań JQL
- Pobieranie szczegółów konkretnych zadań
- Listowanie sprintów dla board'ów
- Pobieranie szczegółów sprintu (daty, status)

✅ **Confluence Integration**
- Odczyt stron Confluence (po ID lub URL)
- Tworzenie nowych stron w określonej lokalizacji
- Wyszukiwanie stron używając CQL

✅ **Automatyczne Changelog**
- Generowanie changelog z zadań sprintu (automatyczne daty)
- Generowanie changelog z wybranych zadań (wymagany zakres dat)
- Automatyczna klasyfikacja typów zmian (Dodano/Zmieniono/Naprawiono/Usunięto)
- Wykrywanie linków do dokumentacji Confluence
- Eksport do pliku Markdown LUB publikacja na Confluence

## Instalacja

### 1. Instalacja zależności Python

```bash
cd atlassian-mcp-server
pip install -r requirements.txt
```

### 2. Konfiguracja

Skopiuj przykładowy plik secrets:

```bash
cp secrets.json.example secrets.json
```

Edytuj plik `secrets.json` i dodaj swoje dane uwierzytelniające:

```json
{
  "email": "twoj.email@example.com",
  "api_token": "TWOJ_API_TOKEN"
}
```

**Wymagane w `secrets.json`:**
- `email` - twój email Atlassian
- `api_token` - token API Atlassian

**Opcjonalnie możesz dostosować `config.json`:**
```json
{
  "atlassian_url": "https://your-company.atlassian.net",
  "default_project": "PROJECT",
  "confluence_space": "SPACE",
  "changelog_parent_id": "1234567890",
  "timeout": 30,
  "per_page": 100
}
```

#### Jak uzyskać API Token:
1. Zaloguj się do https://id.atlassian.com/manage-profile/security/api-tokens
2. Kliknij "Create API token"
3. Nadaj nazwę i skopiuj wygenerowany token
4. Wklej token do `config.json`

### 3. Dodanie serwera do Claude Code

Uruchom:

```bash
claude mcp add atlassian-mcp-server
```

Lub ręcznie dodaj do konfiguracji MCP (~/.claude/mcp_settings.json):

```json
{
  "mcpServers": {
    "atlassian-mcp-server": {
      "command": "python",
      "args": [
        "c:/Users/jacek.ciszkowski/Documents/Git/mcp-servers/atlassian-mcp-server/server.py",
        "c:/Users/jacek.ciszkowski/Documents/Git/mcp-servers/atlassian-mcp-server/config.json"
      ]
    }
  }
}
```

## Użycie

### Jira Tools

#### 1. Wyszukiwanie zadań (search_jira_issues)

```python
{
  "jql": "project = VSNC AND status = Done AND updated >= 2025-01-01",
  "max_results": 50,
  "fields": ["summary", "description", "issuetype", "status", "key"]
}
```

#### 2. Szczegóły zadania (get_issue_details)

```python
{
  "issue_key": "VSNC-123"
}
```

#### 3. Lista sprintów (list_sprints)

```python
{
  "board_id": 1,
  "state": "active"  # lub "closed", "future"
}
```

#### 4. Szczegóły sprintu (get_sprint_details)

```python
{
  "sprint_id": 42
}
```

### Confluence Tools

#### 1. Odczyt strony (get_confluence_page)

```python
{
  "page_id": "1673560113"  # lub pełny URL
}
```

#### 2. Tworzenie strony (create_confluence_page)

```python
{
  "space_key": "GATEWAY",
  "title": "Nowa strona",
  "content": "<p>Treść w formacie Confluence HTML</p>",
  "parent_id": "1673560113"  # opcjonalne
}
```

#### 3. Wyszukiwanie stron (search_confluence_pages)

```python
{
  "query": "changelog",
  "space_key": "GATEWAY",  # opcjonalne
  "limit": 25
}
```

### Changelog Tool

#### Tryb 1: Changelog ze sprintu (automatyczne daty)

```python
{
  "mode": "sprint",
  "sprint_id": 42,
  "output_type": "markdown",
  "output_path": "C:/changelog.md"
}
```

lub publikacja na Confluence:

```python
{
  "mode": "sprint",
  "sprint_id": 42,
  "output_type": "confluence",
  "confluence_parent_url": "https://plummichals.atlassian.net/wiki/spaces/GATEWAY/pages/1673560113",
  "confluence_title": "Lista zmian - Sprint 42"  # opcjonalne
}
```

#### Tryb 2: Changelog z wybranych zadań (wymagany zakres dat)

```python
{
  "mode": "issues",
  "issue_keys": ["VSNC-123", "VSNC-456", "VSNC-789"],
  "from_date": "2025-01-01",
  "to_date": "2025-01-31",
  "output_type": "markdown",
  "output_path": "C:/changelog_january.md"
}
```

## Format Changelog

Wygenerowany changelog zawiera:

### Nagłówek
```markdown
# Zmiany z okresu DD.MM.YYYY - DD.MM.YYYY

**Program evoSYNC G0:** [nazwa_wersji]
```

### Tabela z 4 kolumnami

| **Zmiana / Opis** | **Typ zmiany** | **Zadanie** | **Dokumentacja** |
|-------------------|----------------|-------------|------------------|
| Opis funkcjonalności | ➕ Dodano | [VSNC-123](link) | [Dokumentacja](link) |

### Automatyczna klasyfikacja typu zmiany

- **🔧 Naprawiono** - zadania typu "Bug"
- **➕ Dodano** - nowe funkcjonalności (słowa kluczowe: dodano, dodać, nowy, nowa)
- **✏️ Zmieniono** - modyfikacje (słowa kluczowe: zmiana, zmieniono, modyfikacja)
- **➖ Usunięto** - usunięte funkcjonalności (słowa kluczowe: usunięto, usunąć)

### Sortowanie
- Według priorytetu: Critical/Blocker → High → Medium → Low
- Filtrowanie sub-tasków (chyba że parent jest uwzględniony)

## Wymagania techniczne

- Python 3.7+
- Pakiety: `mcp>=1.0.0`, `requests>=2.31.0`, `python-dateutil>=2.8.0`
- Aktywne konto Atlassian z API tokenem
- Dostęp do Jira i Confluence

## Struktura projektu

```
atlassian-mcp-server/
├── server.py              # Główny serwer MCP
├── config.json            # Konfiguracja (nie commituj!)
├── requirements.txt       # Zależności Python
├── .gitignore            # Ignorowane pliki
├── README.md             # Ta dokumentacja
└── changelog_requirements.md  # Wymagania do changelog
```

## Troubleshooting

### Problem: "Unauthorized" / 401 error
- Sprawdź czy API token jest poprawny
- Upewnij się że email w config.json zgadza się z kontem Atlassian

### Problem: "Not found" / 404 error
- Sprawdź czy ID sprintu/strony/board'a są poprawne
- Upewnij się że masz dostęp do danego projektu/przestrzeni

### Problem: Brak linków do dokumentacji w changelog
- Upewnij się że w polu `description` zadań Jira są linki do Confluence
- Linki muszą zawierać `atlassian.net/wiki`

### Problem: Niepoprawna klasyfikacja typu zmiany
- Sprawdź pole `description` zadania - klasyfikacja opiera się na słowach kluczowych
- Możesz ręcznie dostosować regex w funkcji `_classify_change_type()` w [server.py](server.py)

## Przykładowe użycie w Claude Code

```
Użytkownik: Wygeneruj changelog ze sprintu 42 i zapisz do pliku changelog.md

Claude: [Używa generate_changelog z mode="sprint", sprint_id=42, output_type="markdown"]
```

```
Użytkownik: Stwórz changelog z zadań VSNC-100, VSNC-101, VSNC-102 z okresu 01-15 stycznia i opublikuj na Confluence

Claude: [Używa generate_changelog z mode="issues", issue_keys=[...], dates, output_type="confluence"]
```

## Autor

Jacek Ciszkowski (jacek.ciszkowski@plum.pl)

## Licencja

Wewnętrzne narzędzie Plum Sp. z o.o.
