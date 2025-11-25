# GitLab MCP Server

Serwer MCP (Model Context Protocol) do integracji z GitLab API. Umożliwia pobieranie informacji o merge requestach, projektach i ich szczegółach bezpośrednio z Claude Code.

## Funkcjonalności

- Listowanie dostępnych projektów/repozytoriów
- Pobieranie aktywnych i wszystkich merge requestów
- Filtrowanie MR po projektach, statusie, autorze, assignee
- Szczegółowe informacje o konkretnym merge requeście
- Zaawansowane wyszukiwanie z filtrowaniem po dacie i labelach

## Instalacja

### 1. Zainstaluj zależności

```bash
cd gitlab-mcp-server
pip install -r requirements.txt
```

### 1.1. Zainstaluj cppcheck (opcjonalne, ale zalecane)

**Code review używa cppcheck do zaawansowanej analizy kodu C!**

**Windows:**
- Pobierz instalator z: https://github.com/danmar/cppcheck/releases
- LUB przez Chocolatey: `choco install cppcheck`

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install cppcheck
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install cppcheck
```

**macOS:**
```bash
brew install cppcheck
```

**Sprawdź instalację:**
```bash
cppcheck --version
```

Jeśli cppcheck nie jest zainstalowany, code review nadal będzie działać, ale bez zaawansowanej analizy błędów.

### 2. Skonfiguruj serwer

Skopiuj przykładowy plik secrets:

```bash
cp secrets.json.example secrets.json
```

Edytuj plik `secrets.json` i dodaj swój token:

```json
{
  "gitlab_url": "http://gitlab.plumlan.pl",
  "api_token": "glpat-YOUR-TOKEN-HERE"
}
```

**Wymagane ustawienia w `secrets.json`:**
- `gitlab_url` - URL Twojej instancji GitLab (bez końcowego `/`)
- `api_token` - Personal Access Token z uprawnieniami `read_api`

**Opcjonalne ustawienia w `config.json`:**
- `default_state` - domyślny stan MR (`opened`, `closed`, `merged`, `all`)
- `default_scope` - domyślny zakres (`all`, `created_by_me`, `assigned_to_me`)
- `per_page` - liczba wyników na stronę (domyślnie: 20)
- `verify_ssl` - weryfikacja certyfikatu SSL (domyślnie: true)
- `timeout` - timeout dla requestów w sekundach (domyślnie: 30)
- `watched_projects` - lista obserwowanych projektów (opcjonalne)

### 3. Wygeneruj Personal Access Token

1. Przejdź do: `http://gitlab.plumlan.pl/-/user_settings/personal_access_tokens`
2. Kliknij "Add new token"
3. Ustaw nazwę, np. "MCP Server"
4. Wybierz uprawnienia: **read_api** (wystarczające do odczytu)
5. Kliknij "Create personal access token"
6. Skopiuj token i wklej do `config.json`

### 4. Dodaj do Claude Code

Edytuj plik konfiguracyjny Claude Code (zazwyczaj `~/.config/claude/config.json` lub podobny):

```json
{
  "mcpServers": {
    "gitlab": {
      "command": "python",
      "args": ["c:/Users/jacek.ciszkowski/Documents/Git/mcp-servers/gitlab-mcp-server/server.py"]
    }
  }
}
```

**Uwaga:** Ścieżka musi być bezwzględna i dostosowana do Twojego systemu.

### 5. Uruchom ponownie Claude Code

Po dodaniu konfiguracji, uruchom ponownie Claude Code, aby załadować nowy serwer MCP.

## Dostępne narzędzia

### 1. `list_projects`

Listuje wszystkie dostępne projekty/repozytoria.

**Parametry:**
- `search` (opcjonalny) - wyszukaj projekty po nazwie
- `visibility` (opcjonalny) - filtruj po widoczności: `public`, `internal`, `private`
- `owned` (opcjonalny) - pokaż tylko projekty, których jesteś właścicielem
- `per_page` (opcjonalny) - liczba wyników na stronę

**Przykład użycia:**
```
Pokaż wszystkie moje projekty w GitLab
```
```
Znajdź projekty zawierające "mcp" w nazwie
```

### 2. `fetch_merge_requests`

Pobiera wszystkie merge requesty dostępne dla zalogowanego użytkownika.

**Parametry:**
- `state` (opcjonalny) - status: `opened`, `closed`, `merged`, `locked`, `all` (domyślnie: `opened`)
- `scope` (opcjonalny) - zakres: `created_by_me`, `assigned_to_me`, `all` (domyślnie: `all`)
- `labels` (opcjonalny) - filtruj po labelach (oddzielone przecinkami)
- `search` (opcjonalny) - wyszukaj w tytule i opisie
- `per_page` (opcjonalny) - liczba wyników na stronę

**Przykład użycia:**
```
Pokaż wszystkie otwarte merge requesty
```
```
Pokaż MR-y przypisane do mnie
```
```
Znajdź otwarte MR-y z labelem "bug"
```

### 3. `fetch_project_merge_requests`

Pobiera merge requesty dla konkretnego projektu lub projektów.

**Parametry:**
- `project_id` (wymagany*) - ID projektu lub ścieżka (np. `123` lub `namespace/project-name`)
- `project_ids` (wymagany*) - lista ID projektów (alternatywa do `project_id`)
- `state` (opcjonalny) - status MR (domyślnie: `opened`)
- `author_username` (opcjonalny) - filtruj po autorze
- `assignee_username` (opcjonalny) - filtruj po przypisanym użytkowniku
- `labels` (opcjonalny) - filtruj po labelach
- `per_page` (opcjonalny) - liczba wyników na stronę

*Uwaga: Musisz podać `project_id` LUB `project_ids`

**Przykład użycia:**
```
Pokaż otwarte MR-y w projekcie 123
```
```
Pokaż MR-y w projektach 123, 456 i 789
```
```
Znajdź MR-y autora "john.doe" w projekcie "team/backend"
```

### 4. `fetch_merge_request_details`

Pobiera szczegółowe informacje o konkretnym merge requeście.

**Parametry:**
- `project_id` (wymagany) - ID projektu lub ścieżka
- `merge_request_iid` (wymagany) - IID merge requesta (numer MR w projekcie)

**Przykład użycia:**
```
Pokaż szczegóły MR #42 w projekcie 123
```
```
Jakie są szczegóły merge requesta 15 w projekcie team/frontend?
```

### 5. `search_merge_requests`

Zaawansowane wyszukiwanie merge requestów z filtrowaniem po dacie.

**Parametry:**
- `search` (opcjonalny) - tekst do wyszukania
- `state` (opcjonalny) - status MR
- `created_after` (opcjonalny) - data w formacie ISO 8601 (np. `2024-01-01T00:00:00Z`)
- `created_before` (opcjonalny) - data w formacie ISO 8601
- `updated_after` (opcjonalny) - data w formacie ISO 8601
- `updated_before` (opcjonalny) - data w formacie ISO 8601
- `labels` (opcjonalny) - filtruj po labelach
- `per_page` (opcjonalny) - liczba wyników na stronę

**Przykład użycia:**
```
Pokaż MR-y utworzone po 1 stycznia 2024
```
```
Znajdź otwarte MR-y z "refactor" w tytule zaktualizowane w ostatnim tygodniu
```

### 6. `fetch_merge_request_changes`

Pobiera listę zmodyfikowanych plików w ramach merge requesta wraz z podstawowymi statystykami.

**Parametry:**
- `project_id` (wymagany) - ID projektu lub ścieżka
- `merge_request_iid` (wymagany) - IID merge requesta (numer MR w projekcie)

**Zwraca:**
- Lista zmodyfikowanych plików
- Informacje o typie zmiany (nowy plik, usunięty, zmieniona nazwa)
- Rozmiar diffa dla każdego pliku
- Tryby plików (uprawnienia)

**Przykład użycia:**
```
Pokaż listę zmienionych plików w MR #42 w projekcie 123
```
```
Jakie pliki zostały zmodyfikowane w merge requeście 15?
```

**Przykład odpowiedzi:**
```json
{
  "success": true,
  "merge_request": {
    "id": 12345,
    "iid": 42,
    "title": "Add new feature",
    "state": "opened",
    "web_url": "http://gitlab.plumlan.pl/project/merge_requests/42"
  },
  "changes_count": 3,
  "files": [
    {
      "old_path": "src/server.py",
      "new_path": "src/server.py",
      "a_mode": "100644",
      "b_mode": "100644",
      "new_file": false,
      "renamed_file": false,
      "deleted_file": false,
      "diff_size": 245
    },
    {
      "old_path": "tests/test_api.py",
      "new_path": "tests/test_api.py",
      "a_mode": "100644",
      "b_mode": "100644",
      "new_file": true,
      "renamed_file": false,
      "deleted_file": false,
      "diff_size": 450
    }
  ]
}
```

### 7. `fetch_merge_request_diffs`

Pobiera szczegółowe zmiany (diff) dla wszystkich plików w merge requeście w formacie unified diff.

**Parametry:**
- `project_id` (wymagany) - ID projektu lub ścieżka
- `merge_request_iid` (wymagany) - IID merge requesta

**Zwraca:**
- Pełny diff dla każdego pliku w formacie unified diff
- Informacje o typie zmiany
- Stare i nowe ścieżki plików

**Przykład użycia:**
```
Pokaż szczegółowe zmiany w MR #42
```
```
Jakie są dokładne zmiany kodu w merge requeście 15 w projekcie team/backend?
```

**Przykład odpowiedzi:**
```json
{
  "success": true,
  "merge_request": {
    "id": 12345,
    "iid": 42,
    "title": "Add new feature",
    "state": "opened",
    "web_url": "http://gitlab.plumlan.pl/project/merge_requests/42"
  },
  "changes_count": 2,
  "diffs": [
    {
      "old_path": "src/server.py",
      "new_path": "src/server.py",
      "new_file": false,
      "renamed_file": false,
      "deleted_file": false,
      "diff": "@@ -10,7 +10,7 @@ def handle_request():\n-    return \"old response\"\n+    return \"new response\"\n"
    }
  ]
}
```

### 8. `review_merge_request`

Wykonuje automatyczny code review merge requesta dla projektów w C. **Wspiera różne poziomy szczegółowości** - idealne dla dużych MR!

**Parametry:**
- `project_id` (wymagany) - ID projektu lub ścieżka
- `merge_request_iid` (wymagany) - IID merge requesta
- `detail_level` (opcjonalny) - Poziom szczegółowości raportu:
  - **`summary`** - Tylko statystyki + top 10 najważniejszych problemów (najmniej tokenów!)
  - **`aggregated`** - Zagregowane identyczne problemy (2 przykłady każdego) - **DOMYŚLNIE**
  - **`paginated`** - Wyniki partiami (użyj z `page` i `per_page`)
  - **`full`** - Pełny raport (dla małych MR)
- `page` (opcjonalny) - Numer strony dla `paginated` (domyślnie: 1)
- `per_page` (opcjonalny) - Liczba problemów na stronę dla `paginated` (domyślnie: 50)

**Co sprawdza:**
- **cppcheck (zaawansowana analiza)**:
  - Memory leaks (malloc bez free)
  - Buffer overflows
  - NULL pointer dereference
  - Use after free, double free
  - Undefined behavior
  - Nieużywane zmienne
  - Performance issues
- **Formatowanie**: długość linii (max 80 znaków), wcięcia
- **Nazewnictwo**: zgodność z konwencjami (struktury, enumy, funkcje, zmienne)
- **Niebezpieczne funkcje**: strcpy, sprintf, gets, scanf (ostrzeżenia)
- **Code patterns**: malloc bez sprawdzenia NULL, potencjalne memory leaks
- **Best practices**: głębokość zagnieżdżeń, długość funkcji

**Zwraca:**
- Raport z 4 poziomami: critical / error / warning / info
- Lista problemów z lokalizacją (plik, linia)
- Sugestie poprawek
- Podsumowanie

**Przykłady użycia:**

```
# Duży MR - szybki przegląd (summary)
Zrób szybki code review MR #42 (tylko podsumowanie)

# Duży MR - agregowane problemy (domyślnie)
Zrób code review MR #42 w projekcie 123

# Duży MR - paginacja
Zrób code review MR #42 (paginated, strona 1)
Pokaż stronę 2 problemów z MR #42

# Mały MR - pełny raport
Zrób pełny code review MR #15 w projekcie embedded-firmware
```

**Przykład odpowiedzi (aggregated - domyślnie):**
```json
{
  "success": true,
  "detail_level": "aggregated",
  "merge_request": {
    "id": 12345,
    "iid": 42,
    "title": "Add UART driver",
    "state": "opened",
    "web_url": "http://gitlab.plumlan.pl/project/merge_requests/42",
    "files_total": 8,
    "c_files_reviewed": 4
  },
  "summary": {
    "total_issues": 45,
    "critical": 2,
    "error": 0,
    "warning": 35,
    "info": 8,
    "by_file": {
      "src/uart.c": {"critical": 1, "warning": 20, "info": 3},
      "src/gpio.c": {"critical": 1, "warning": 15, "info": 5}
    }
  },
  "issues": {
    "critical": [
      {
        "file": "src/uart.c",
        "line": 45,
        "type": "unsafe_function",
        "message": "NIGDY nie używaj gets() - jest ekstremalnie niebezpieczna!",
        "suggestion": "Użyj fgets(buffer, sizeof(buffer), stdin)",
        "code": "gets(input_buffer);"
      },
      {
        "file": "src/uart.c",
        "line": 78,
        "type": "cppcheck_memleak",
        "message": "[cppcheck] Memory leak: buffer - allocated memory is never freed",
        "suggestion": "cppcheck wykrył potencjalny problem (ID: memleak)"
      }
    ],
    "warning": [
      {
        "type": "line_length",
        "message": "Linia przekracza 80 znaków",
        "occurrences": 25,
        "examples": [
          {
            "file": "src/uart.c",
            "line": 23,
            "code": "void uart_send_data(uint8_t *data, size_t len, bool wait_for_completion, uint32_t timeout_ms) {"
          },
          {
            "file": "src/uart.c",
            "line": 67,
            "code": "static inline void process_data(const uint8_t *buffer, size_t length, bool verify) {"
          }
        ],
        "additional_files": ["src/gpio.c", "src/spi.c"]
      },
      {
        "type": "unsafe_function",
        "message": "Używasz strcpy - rozważ strncpy() dla bezpieczeństwa",
        "occurrences": 5,
        "examples": [
          {
            "file": "src/uart.c",
            "line": 89,
            "code": "strcpy(buffer, input);"
          },
          {
            "file": "src/gpio.c",
            "line": 45,
            "code": "strcpy(name, default_name);"
          }
        ],
        "additional_files": ["src/utils.c"]
      }
    ],
    "info": [
      {
        "file": "src/uart.h",
        "line": 12,
        "type": "naming_convention",
        "message": "Funkcja publiczna 'uart_init' nie spełnia konwencji: PascalCase (np. UartInit)",
        "code": "void uart_init(void);"
      }
    ]
  }
}
```

**Konfiguracja:**

Code review używa pliku [code-review-config.json](code-review-config.json), który można dostosować do własnych potrzeb:
- **cppcheck settings**: włącz/wyłącz, poziomy sprawdzeń (error, warning, performance, portability, style)
- Konwencje nazewnictwa
- Maksymalna długość linii
- Lista funkcji do sprawdzenia
- Wzorce kodu (regex patterns)
- Poziomy severity

**Przykład konfiguracji cppcheck:**
```json
{
  "cppcheck": {
    "enabled": true,
    "checks": ["error", "warning", "performance", "portability", "style"]
  }
}
```

Ustaw `"enabled": false` żeby wyłączyć cppcheck (np. jeśli nie jest zainstalowany).

**Formatowanie (opcjonalne):**

Możesz również użyć pliku [.clang-format](.clang-format) do automatycznego formatowania kodu zgodnie ze standardem projektu.

## Jak przekazać repozytorium?

Istnieje kilka sposobów na wskazanie repozytoriów:

### Metoda 1: Przez ID projektu

Najprostszy sposób - użyj numerycznego ID projektu:

```
Pokaż MR-y w projekcie 123
```

**Jak znaleźć ID projektu?**
- Wejdź na stronę projektu w GitLab
- ID jest widoczne pod nazwą projektu
- LUB użyj narzędzia `list_projects` aby wylistować wszystkie projekty z ich ID

### Metoda 2: Przez ścieżkę projektu

Użyj pełnej ścieżki projektu (namespace/nazwa):

```
Pokaż MR-y w projekcie "team/backend-api"
```

### Metoda 3: Przez listę projektów

Możesz podać wiele projektów jednocześnie:

```
Pokaż MR-y w projektach 123, 456 i 789
```

### Metoda 4: Przez konfigurację (watched_projects)

Dodaj w `config.json` ulubione projekty:

```json
{
  "watched_projects": ["123", "456", "team/frontend"]
}
```

A następnie możesz się do nich odwoływać naturalnie:

```
Pokaż MR-y w moich obserwowanych projektach
```

## Odpowiedzi narzędzi

Wszystkie narzędzia zwracają wynik w formacie JSON:

### Sukces

```json
{
  "success": true,
  "count": 5,
  "merge_requests": [
    {
      "id": 12345,
      "iid": 42,
      "title": "Add new feature",
      "state": "opened",
      "author": {
        "username": "john.doe",
        "name": "John Doe"
      },
      "target_branch": "main",
      "source_branch": "feature/new-feature",
      "web_url": "http://gitlab.plumlan.pl/project/merge_requests/42",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-16T14:20:00Z"
    }
  ]
}
```

### Błąd

```json
{
  "success": false,
  "error": "HTTP Error: 401",
  "message": "Unauthorized"
}
```

## Najczęstsze błędy

### Błąd autoryzacji (401 Unauthorized)

**Przyczyna:** Nieprawidłowy lub wygasły API token.

**Rozwiązanie:**
1. Sprawdź czy token w `config.json` jest poprawny
2. Wygeneruj nowy token w ustawieniach GitLab
3. Upewnij się, że token ma uprawnienie `read_api`

### Błąd połączenia (Connection failed)

**Przyczyna:** Nieprawidłowy URL GitLab lub problem z siecią.

**Rozwiązanie:**
1. Sprawdź czy `gitlab_url` w `config.json` jest poprawny
2. Upewnij się, że GitLab jest dostępny (otwórz w przeglądarce)
3. Jeśli używasz self-signed SSL, ustaw `verify_ssl: false`

### Błąd 404 (Not Found)

**Przyczyna:** Projekt lub merge request nie istnieje lub nie masz do niego dostępu.

**Rozwiązanie:**
1. Sprawdź czy ID projektu jest poprawne
2. Upewnij się, że masz uprawnienia do projektu
3. Użyj `list_projects` aby zobaczyć dostępne projekty

## Bezpieczeństwo

### Najlepsze praktyki:

1. **Nigdy nie commituj `secrets.json` z tokenem** do repozytorium
   - Plik `secrets.json` jest już w `.gitignore`
   - Użyj `secrets.json.example` jako szablonu

2. **Używaj minimalnych uprawnień**
   - Token powinien mieć tylko `read_api` scope
   - Nie używaj tokenów z prawami `write` jeśli nie są potrzebne

3. **Regularnie rotuj tokeny**
   - Ustawiaj datę wygaśnięcia tokenów
   - Odświeżaj tokeny co kilka miesięcy

4. **Chroń plik konfiguracyjny**
   - Ustaw uprawnienia tylko dla swojego użytkownika
   - Na Linuxie: `chmod 600 config.json`

## Wsparcie i rozwój

### Zgłaszanie problemów

Jeśli napotkasz problem:
1. Sprawdź czy wszystkie zależności są zainstalowane
2. Upewnij się, że `config.json` jest poprawnie skonfigurowany
3. Sprawdź logi Claude Code
4. Otwórz issue w repozytorium projektu

### Zaimplementowane funkcjonalności

- [x] Listowanie projektów/repozytoriów
- [x] Pobieranie merge requestów (wszystkich, projektu, filtrowanie)
- [x] Szczegółowe informacje o merge requeście
- [x] Zaawansowane wyszukiwanie z filtrowaniem po dacie
- [x] Pobieranie listy zmienionych plików w MR
- [x] Pobieranie szczegółowych diffów z merge requestów
- [x] **Code Review dla projektów w C**
  - [x] **Integracja z cppcheck** - zaawansowana analiza statyczna
    - [x] Memory leaks
    - [x] Buffer overflows
    - [x] NULL pointer dereference
    - [x] Undefined behavior
  - [x] Sprawdzanie formatowania
  - [x] Walidacja nazewnictwa (struktury, enumy, funkcje)
  - [x] Wykrywanie niebezpiecznych funkcji
  - [x] Analiza wzorców kodu
  - [x] Konfigurowalny system reguł

### Planowane funkcjonalności

- [ ] Pobieranie komentarzy do merge requestów
- [ ] Automatyczne dodawanie komentarzy z code review do MR
- [ ] Filtrowanie po milestone
- [ ] Webhook support dla powiadomień
- [ ] Cache'owanie wyników
- [ ] Wsparcie dla grup (group-level merge requests)
- [ ] Pobieranie informacji o pipeline/CI
- [ ] Code review dla innych języków (Python, JavaScript)

## Licencja

MIT License

## Autor

Stworzony z pomocą Claude Code
