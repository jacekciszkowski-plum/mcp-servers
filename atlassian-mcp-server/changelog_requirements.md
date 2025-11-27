# Wymagania do automatycznego generowania Changelog dla evoSYNC

## 1. Struktura tabelki Changelog

### Format tabeli
Tabela powinna mieć 4 kolumny:
| **Zmiana / Opis** | **Typ zmiany** | **Zadanie** | **Dokumentacja** |

### Kolumny tabeli

#### 1.1 Kolumna "Zmiana / Opis"
- **Zawartość**: Szczegółowy opis zmian w funkcjonalności
- **Źródło danych**: 
  - Pole `summary` z zadania JIRA
  - Pole `description` z zadania JIRA (opcjonalnie, jeśli zawiera więcej szczegółów)
- **Format**: Tekst opisowy, może zawierać listy punktowane
- **Przykład**: "Konfiguracja działania akumulatora w koszcie średnim. Możliwe opcje to autokonsumpcja lub blokada rozładowywania."

#### 1.2 Kolumna "Typ zmiany"
- **Zawartość**: Emoji + tekst opisujący typ zmiany
- **Dostępne typy**:
  - **➕ Dodano** - nowe funkcjonalności
  - **✏️ Zmieniono** - modyfikacje istniejących funkcji
  - **🔧 Naprawiono** - poprawki błędów
  - **➖ Usunięto** - usunięte funkcjonalności
- **Logika przypisania**:
  - Jeśli `issuetype.name` == "Bug" → **🔧 Naprawiono**
  - Jeśli `description` zawiera słowa: "dodano", "dodać", "nowy", "nowa" → **➕ Dodano**
  - Jeśli `description` zawiera słowa: "zmiana", "zmieniono", "modyfikacja", "poprawka w interfejsie" → **✏️ Zmieniono**
  - Jeśli `description` zawiera słowa: "usunięto", "usunąć", "pozbycie się" → **➖ Usunięto**
  - Domyślnie dla `issuetype.name` == "Zadanie" → **➕ Dodano**

#### 1.3 Kolumna "Zadanie"
- **Zawartość**: Link do zadania JIRA z emoji
- **Format**: `[VSNC-XXX](https://plummichals.atlassian.net/browse/VSNC-XXX)`
- **Emoji**: `:logo_jira:` (po linku)
- **Źródło**: Pole `key` z zadania JIRA

#### 1.4 Kolumna "Dokumentacja"
- **Zawartość**: Linki do dokumentacji Confluence z emoji
- **Dostępne typy**:
  - 📋 Instrukcja - dokumentacja użytkownika
  - 🛠️ Techniczna - dokumentacja techniczna
  - ℹ️ Info - dodatkowe informacje
- **Format**: `[🛠️ Techniczna](URL)` lub `[📋 Instrukcja](URL)`
- **Źródło**: 
  - Linki z pola `description` zadania JIRA
  - Powiązane strony Confluence
- **Może być puste** jeśli brak dokumentacji

## 2. Kryteria filtrowania zadań

### 2.1 Status zadań
- **Uwzględniane statusy**: 
  - "Done" / "Zakończone"
  - "Closed" / "Zamknięte"
  - "Merged" / "Scalony"

### 2.2 Zakres czasowy
- **Format nagłówka**: "Zmiany z okresu DD.MM.YYYY - DD.MM.YYYY"
- **Konfigurowalny**: Możliwość podania własnego zakresu dat
- **Domyślny okres**: od dnia rozpoczęcia sprintu do dnia zakończenia sprintu

### 2.3 Projekt
- **Projekt**: VSNC (głównie)
- **Dodatkowe**: Zadania powiązane z evoSYNC z innych projektów

## 3. Informacje dodatkowe

### 3.1 Nagłówek sekcji
```markdown
# Zmiany z okresu DD.MM.YYYY - DD.MM.YYYY

**Program evoSYNC G0:** [nazwa_wersji] ([dodatkowe_info])
```

### 3.2 Sekcja "Inne osiągnięcia"
- **Zawartość**: Zadania analityczne, badawcze, które nie wpływają bezpośrednio na kod
- **Kryteria**: 
  - Zadania typu "Epic"
  - Zadania, które miały status "Analiza"
  - Zadania z etykietami: "analiza", "badania", "dokumentacja"

## 4. Algoritm tworzenia tabeli

### 4.1 Pobieranie danych
1. **JQL Query**: `project = VSNC AND status in (Done, Closed) AND updated >= startDate AND updated <= endDate ORDER BY updated DESC`
2. **Pola do pobrania**: `summary`, `description`, `issuetype`, `status`, `key`, `updated`, `priority`

### 4.2 Przetwarzanie zadań
1. **Filtrowanie**: Usunięcie zadań technicznych/wewnętrznych
2. **Grupowanie**: Według typu zmiany
3. **Sortowanie**: Według ważności (nowe funkcje → zmiany → naprawki → usunięcia)

### 4.3 Generowanie markdown
1. **Tworzenie tabeli** w formacie Confluence/Markdown
2. **Dodawanie linków** do JIRA i Confluence
3. **Formatowanie emoji** zgodnie ze standardem Confluence

## 5. Lokalizacja docelowa

### 5.1 Confluence
- **Przestrzeń**: GATEWAY
- **Folder**: Changelog (ID: 1673560113)
- **Nazwa strony**: "Lista zmian w evoSYNC - [okres]"
- **Template**: Bazujący na istniejącej stronie "Lista zmian w evoSYNC"

### 5.2 Automatyzacja
- **Trigger**: Na żądanie
- **Publikacja**: Automatyczne dodanie nowej strony do folderu Changelog
- **Notyfikacja**: Powiadomienie zespołu o nowej stronie changelog

## 6. Konfiguracja

### 6.1 Mapowanie priorytetów
- **Critical/Blocker** → Na początku tabeli
- **High** → Wysokie w kolejności
- **Medium** → Standardowa kolejość
- **Low** → Na końcu lub w sekcji "Inne osiągnięcia"

### 6.2 Ignorowane zadania
- Zadania typu "Sub-task" (chyba że parent jest uwzględniony)

## 7. Przykład użycia
```bash
# Generowanie changelog za ostatnie 3 tygodnie
generate_changelog --from="2025-10-17" --to="2025-11-06" --project="VSNC"

# Generowanie i publikacja w Confluence
generate_changelog --publish --space="GATEWAY" --parent-folder="1673560113"
```
