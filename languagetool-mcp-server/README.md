# LanguageTool MCP Server

MCP (Model Context Protocol) server for spell and grammar checking using LanguageTool.

## Features

- ✅ **Multi-language support** - Auto-detects Polish, English, German, and more
- ✅ **JSON-aware** - Validates translation files, checking values not keys
- ✅ **Offline operation** - No external API needed
- ✅ **Customizable** - Ignore technical terms and abbreviations
- ✅ **Detailed reports** - Get spelling errors with suggestions and context

## Installation

### 1. Install Python dependencies

```bash
cd languagetool-mcp-server
pip install -r requirements.txt
```

**Note:** The first time you run the server, `language-tool-python` will automatically download LanguageTool (~200MB). This may take a few minutes.

### 2. Configure Claude Code

Add to your global MCP settings file:

**Windows:** `%APPDATA%\.claude\mcp_settings.json`
**macOS/Linux:** `~/.claude/mcp_settings.json`

```json
{
  "mcpServers": {
    "languagetool": {
      "command": "python",
      "args": [
        "path to server.py"
      ]
    }
  }
}
```

**Important:** Update the path to match your installation directory.

### 3. Restart Claude Code

After adding the configuration, restart Claude Code to load the MCP server.

## Usage

### Check spelling in text

```
Check the spelling in this text: "Temperatura zewnetrzna jest zbyt niska"
```

### Check JSON translation file

```
Check spelling in file: modbus/trans_pl.json
```

### Add technical terms to ignore list

```
Add "ecoMULTI" to the spelling ignore list
```

## Available Tools

The server provides 4 MCP tools:

1. **check_spelling** - Check spelling in any text
   - Parameters:
     - `text` (required) - Text to check
     - `language` (optional) - Language code (pl-PL, en-US, de-DE) or "auto"

2. **check_json_file** - Check spelling in JSON file
   - Parameters:
     - `file_path` (required) - Path to JSON file
     - `language` (optional) - Language code or "auto"

3. **check_json_values** - Check spelling in JSON data
   - Parameters:
     - `json_string` (required) - JSON as string
     - `language` (optional) - Language code or "auto"

4. **add_ignored_word** - Add word to ignore list
   - Parameters:
     - `word` (required) - Word to ignore

## Configuration

Edit [config.json](config.json) to customize:

```json
{
  "default_language": "auto",
  "ignored_words": [
    "cop",
    "eer",
    "cwu",
    "modbus",
    "ecomulti",
    ...
  ]
}
```

Add technical terms, abbreviations, product names, etc. to the `ignored_words` array.

## Supported Languages

- Polish (pl-PL)
- English (en-US)
- German (de-DE)
- Spanish (es)
- French (fr)
- Italian (it)
- Dutch (nl)
- Portuguese (pt)
- And many more...

See [LanguageTool documentation](https://languagetool.org/languages) for the full list.

## Example Output

### Spelling check result:

```json
{
  "language": "pl-PL",
  "error_count": 1,
  "errors": [
    {
      "message": "Możliwy błąd ortograficzny",
      "context": "Temperatura zewnetrzna jest...",
      "offset": 12,
      "length": 10,
      "replacements": ["zewnętrzna"],
      "rule_id": "MORFOLOGIK_RULE_PL_PL",
      "category": "TYPOS"
    }
  ]
}
```

### JSON file check result:

```json
{
  "total_errors": 2,
  "errors": [
    {
      "key": "temp_zewnetrzna",
      "value": "Temperatura zewnetrzna",
      "check_result": {
        "language": "pl-PL",
        "error_count": 1,
        "errors": [...]
      }
    }
  ]
}
```

## Troubleshooting

### Server not starting

- Make sure Python 3.7+ is installed
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify the path in `mcp_settings.json` is correct

### First run is slow

- The first run downloads LanguageTool (~200MB)
- Subsequent runs will be much faster

### False positives

- Add technical terms to `config.json` ignored_words
- Or use the `add_ignored_word` tool: "Add 'ecoMULTI' to ignore list"

## Development

To test the server locally:

```bash
python server.py
```

The server communicates via stdin/stdout using the MCP protocol.

## License

MIT License - see your project license for details.

## Dependencies

- [language-tool-python](https://github.com/jxmorris12/language_tool_python) - Python wrapper for LanguageTool
- [mcp](https://github.com/modelcontextprotocol/python-sdk) - Model Context Protocol SDK
