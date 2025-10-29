# JSON Validator MCP Server

MCP (Model Context Protocol) server for comprehensive JSON validation, analysis, and manipulation.

## Features

- ✅ **Precise error reporting** - Line and column numbers for syntax errors
- ✅ **Large file support** - Handles files of any size without token limits
- ✅ **Schema validation** - Validate against JSON Schema (draft-07, draft-2020-12)
- ✅ **Deep comparison** - Compare two JSON objects with detailed diff
- ✅ **Statistics** - Analyze structure depth, key counts, type distribution
- ✅ **Format conversion** - Convert JSON to YAML, CSV, or XML
- ✅ **Deep merge** - Merge multiple JSON objects intelligently
- ✅ **Type validation** - Detect and validate URLs, emails, dates in JSON values
- ✅ **File support** - Validate files directly or JSON strings

## Installation

### 1. Install Python dependencies

```bash
cd json-validator-mcp-server
pip install -r requirements.txt
```

### 2. Configure Claude Code

Add to your global MCP settings file:

**Windows:** `%APPDATA%\.claude\mcp_settings.json`
**macOS/Linux:** `~/.claude/mcp_settings.json`

```json
{
  "mcpServers": {
    "json-validator": {
      "command": "python",
      "args": [
        "C:\\Users\\YourUsername\\path\\to\\json-validator-mcp-server\\server.py"
      ]
    }
  }
}
```

**Important:** Update the path to match your installation directory.

### 3. Restart Claude Code

After adding the configuration, restart Claude Code to load the MCP server.

## Usage Examples

### 1. Validate JSON syntax

```
Validate this JSON: {"name": "test", "value": 123,}
```

**Response:**
```json
{
  "valid": false,
  "error": {
    "line": 1,
    "column": 35,
    "error_line": "{\"name\": \"test\", \"value\": 123,}",
    "message": "Expecting property name enclosed in double quotes",
    "context_before": null,
    "context_after": null
  }
}
```

### 2. Validate JSON file (small files)

```
Validate file: data/config.json
```

**Response (valid file):**
```json
{
  "valid": true,
  "message": "JSON is valid",
  "file_path": "data/config.json",
  "file_size_bytes": 1234,
  "size_bytes": 1234,
  "size_chars": 1234,
  "root_type": "dict",
  "root_keys": ["users", "settings", "version"],
  "root_key_count": 3
}
```

### 2b. Validate large JSON file (recommended for files >1MB)

**For large files, the server automatically avoids returning full data to prevent token limit errors.**

```
Validate file: data/large-config.json
```

**Response:**
```json
{
  "valid": true,
  "message": "JSON is valid",
  "file_path": "data/large-config.json",
  "file_size_bytes": 15728640,
  "size_bytes": 15728640,
  "size_chars": 15728640,
  "root_type": "dict",
  "root_keys": ["tiles", "barParams", "editionScreens", "..."],
  "root_key_count": 13,
  "warning": "Large file (>10MB). Consider using json_stats for analysis instead of returning full data."
}
```

**Note:** By default, `return_data` is `false` to handle large files efficiently. Set `return_data=true` only for small files when you need the parsed content.

### 3. Validate against JSON Schema

```
Validate this JSON against schema:
JSON: {"name": "John", "age": 30}
Schema: {"type": "object", "required": ["name", "age", "email"], "properties": {"name": {"type": "string"}, "age": {"type": "number"}, "email": {"type": "string"}}}
```

**Response:**
```json
{
  "valid": false,
  "error": "Schema validation failed",
  "message": "'email' is a required property",
  "path": [],
  "schema_path": ["required"]
}
```

### 4. Calculate JSON statistics

```
Get statistics for this JSON: {"users": [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}], "total": 2}
```

**Response:**
```json
{
  "size_bytes": 95,
  "size_chars": 95,
  "max_depth": 2,
  "total_keys": 7,
  "type_counts": {
    "object": 3,
    "array": 1,
    "string": 2,
    "integer": 3
  },
  "root_type": "dict",
  "root_keys": ["users", "total"],
  "root_key_count": 2
}
```

### 5. Compare two JSON objects

```
Compare these JSON objects:
First: {"name": "John", "age": 30, "city": "NYC"}
Second: {"name": "John", "age": 31, "country": "USA"}
```

**Response:**
```json
{
  "identical": false,
  "difference_count": 3,
  "differences": [
    {
      "path": "city",
      "type": "missing_in_second",
      "value": "NYC"
    },
    {
      "path": "country",
      "type": "missing_in_first",
      "value": "USA"
    },
    {
      "path": "age",
      "type": "value_mismatch",
      "value1": 30,
      "value2": 31
    }
  ]
}
```

### 6. Convert JSON to other formats

```
Convert this JSON to YAML: {"name": "John", "hobbies": ["reading", "coding"]}
```

**Response:**
```yaml
name: John
hobbies:
- reading
- coding
```

**CSV conversion (for flat arrays of objects):**
```
Convert to CSV: [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
```

**Response:**
```csv
age,name
"30","John"
"25","Jane"
```

### 7. Merge multiple JSON objects

```
Merge these JSON objects:
1. {"user": {"name": "John", "age": 30}}
2. {"user": {"email": "john@example.com"}, "active": true}
```

**Response:**
```json
{
  "merged": {
    "user": {
      "name": "John",
      "age": 30,
      "email": "john@example.com"
    },
    "active": true
  },
  "merged_count": 2
}
```

### 8. Validate special types (URLs, emails, dates)

```
Find and validate URLs, emails and dates in this JSON: {"website": "https://example.com", "contact": "info@example.com", "created": "2024-01-15"}
```

**Response:**
```json
{
  "total_found": 3,
  "by_type": {
    "url": [
      {
        "path": "website",
        "value": "https://example.com"
      }
    ],
    "email": [
      {
        "path": "contact",
        "value": "info@example.com"
      }
    ],
    "date": [
      {
        "path": "created",
        "value": "2024-01-15"
      }
    ]
  }
}
```

### 9. Suggest JSON fixes

**NEW!** Analyze JSON and get suggestions for fixing common errors.

```
Suggest fixes for this JSON: {"name": "test",sdsdsd "value": 123,}
```

**Response:**
```json
{
  "valid": false,
  "has_errors": true,
  "has_warnings": false,
  "suggestion_count": 2,
  "suggestions": [
    {
      "line": 1,
      "column": 20,
      "type": "invalid_text",
      "severity": "error",
      "message": "Expecting property name enclosed in double quotes",
      "current": "{\"name\": \"test\",sdsdsd \"value\": 123,}",
      "invalid_text": "sdsdsd",
      "fix_description": "Remove invalid text 'sdsdsd'",
      "suggested": "{\"name\": \"test\", \"value\": 123,}",
      "context_before": null,
      "context_after": null
    },
    {
      "line": 1,
      "column": 35,
      "type": "trailing_comma",
      "severity": "error",
      "message": "Illegal trailing comma before end of object",
      "current": "{\"name\": \"test\", \"value\": 123,}",
      "fix_description": "Remove trailing comma before closing bracket",
      "suggested": "{\"name\": \"test\", \"value\": 123}",
      "context_before": null,
      "context_after": null
    }
  ]
}
```

**Detected error types:**
- **trailing_comma**: Commas before closing brackets
- **invalid_text**: Random text that shouldn't be there
- **single_quotes**: Should use double quotes
- **comment**: JSON doesn't support comments
- **unquoted_key**: Property names must be in quotes
- **missing_comma**: Missing comma between properties
- **missing_value**: Missing value after colon

**Note:** This tool only suggests fixes, it does NOT automatically modify your JSON. You need to apply the suggestions manually.

## Handling Large JSON Files

This server is **optimized for large JSON files** and can handle files of any size without hitting token limits.

### Strategy for Large Files

**Problem:** Large JSON files can exceed the 25,000 token limit when returned in MCP responses.

**Solution:** The server uses smart defaults:
- By default, `validate_json` and `validate_json_file` **do NOT return the full JSON data**
- Instead, they return validation results + metadata (size, root keys, structure info)
- Use `return_data=true` only for small files when you need the parsed content

### Best Practices by File Size

| File Size | Recommended Approach | Example |
|-----------|---------------------|---------|
| < 100KB | Use `return_data=true` if needed | `validate_json_file("config.json", return_data=true)` |
| 100KB - 1MB | Use default (`return_data=false`) | `validate_json_file("data.json")` |
| 1MB - 10MB | Use `validate_json_file` + `json_stats` | First validate, then get stats |
| > 10MB | Use only `json_stats` for analysis | `json_stats` returns structure without full data |

### Example: Validating profile.json (15MB)

```
Validate file: profile.json
```

**Response:**
```json
{
  "valid": true,
  "message": "JSON is valid",
  "file_path": "profile.json",
  "file_size_bytes": 15728640,
  "size_bytes": 15728640,
  "size_chars": 15728640,
  "root_type": "dict",
  "root_keys": [
    "tiles",
    "barParams",
    "editionScreens",
    "schedules",
    "schemas",
    "charts",
    "alarms",
    "advancedParameters",
    "notifications",
    "wizards",
    "pairingConfig",
    "counters",
    "energyManagement"
  ],
  "root_key_count": 13,
  "warning": "Large file (>10MB). Consider using json_stats for analysis instead of returning full data."
}
```

Then get detailed statistics:
```
Get JSON stats for file: profile.json
```

This approach allows you to validate and analyze JSON files of **any size** without errors!

## Available Tools

The server provides 9 MCP tools:

### 1. validate_json
Validate JSON syntax with detailed error reporting including line and column numbers.

**Parameters:**
- `json_string` (required) - JSON string to validate
- `return_data` (optional, default: false) - Whether to return parsed JSON data

**Returns:**
- `valid`: boolean
- `size_bytes`, `size_chars`: Size information
- `root_type`: Type of root element (dict, list, etc.)
- `root_keys`: List of top-level keys (for objects)
- `root_key_count`: Number of top-level keys (for objects)
- `root_array_length`: Length (for arrays)
- `error`: object with line, column, error_line, context, message (if invalid)
- `data`: parsed JSON object (only if `return_data=true` and valid)

**Important:** For large JSON (>1MB), keep `return_data=false` to avoid token limits.

### 2. validate_json_file
Validate JSON file directly. **Optimized for large files** - automatically avoids returning full data.

**Parameters:**
- `file_path` (required) - Path to JSON file
- `return_data` (optional, default: false) - Whether to return parsed JSON data

**Returns:** Same as validate_json plus:
- `file_path`: Path to the validated file
- `file_size_bytes`: File size in bytes
- `warning`: Appears for files >10MB
- `info`: Appears for files >1MB

**Recommended:**
- Files <100KB: Can use `return_data=true`
- Files 100KB-1MB: Use `return_data=false` (default)
- Files >1MB: Always use `return_data=false` and `json_stats` for analysis
- Files >10MB: Use only `json_stats` for structure analysis

### 3. validate_schema
Validate JSON against a JSON Schema.

**Parameters:**
- `json_string` (required) - JSON to validate
- `schema` (required) - JSON Schema object

**Returns:**
- `valid`: boolean
- `error`, `message`, `path`, `schema_path` (if invalid)

**Requires:** `jsonschema` library

### 4. json_stats
Calculate comprehensive statistics about JSON structure.

**Parameters:**
- `json_string` (required) - JSON to analyze

**Returns:**
- `size_bytes`, `size_chars`: Size information
- `max_depth`: Maximum nesting depth
- `total_keys`: Total number of object keys
- `type_counts`: Distribution of types (object, array, string, number, etc.)
- `root_type`: Type of root element
- `root_keys`, `root_key_count`: Root-level information

### 5. compare_json
Deep comparison of two JSON objects.

**Parameters:**
- `json_string1` (required) - First JSON
- `json_string2` (required) - Second JSON

**Returns:**
- `identical`: boolean
- `difference_count`: number of differences
- `differences`: array of difference objects with path, type, and values

**Difference types:**
- `type_mismatch`: Different data types
- `missing_in_first`: Key only in second object
- `missing_in_second`: Key only in first object
- `value_mismatch`: Different primitive values
- `array_length_mismatch`: Different array lengths

### 6. convert_json
Convert JSON to other formats.

**Parameters:**
- `json_string` (required) - JSON to convert
- `output_format` (required) - Target format: "yaml", "csv", or "xml"

**Returns:**
- `format`: output format
- `output`: converted string

**Notes:**
- YAML conversion requires `pyyaml` library
- CSV conversion requires root to be array of objects
- XML conversion is simplified (for basic structures)

### 7. merge_json
Deep merge multiple JSON objects.

**Parameters:**
- `json_strings` (required) - Array of JSON strings to merge

**Returns:**
- `merged`: merged JSON object
- `merged_count`: number of objects merged

**Merge behavior:**
- Objects: keys are merged recursively
- Arrays: concatenated
- Primitives: later values overwrite earlier ones

### 8. validate_types
Scan JSON for special data types and validate them.

**Parameters:**
- `json_string` (required) - JSON to scan

**Returns:**
- `total_found`: number of special types found
- `by_type`: grouped results (url, email, date)
- `all_validations`: complete list with paths and values

**Detected types:**
- **URL**: Valid URLs with scheme and netloc
- **Email**: Valid email addresses
- **Date**: Dates in common formats (ISO 8601, dd.mm.yyyy, dd/mm/yyyy)

### 9. suggest_json_fixes
**NEW!** Analyze JSON and suggest fixes for common errors without auto-fixing.

**Parameters:**
- `json_string` (required) - JSON string to analyze
- `show_context` (optional, default: true) - Show context lines around errors

**Returns:**
- `valid`: boolean - overall validity
- `has_errors`: boolean - has critical errors
- `has_warnings`: boolean - has warnings
- `suggestion_count`: number of suggestions
- `suggestions`: array of suggestion objects

**Suggestion object structure:**
```json
{
  "line": 97,
  "column": 36,
  "type": "invalid_text",
  "severity": "error",
  "message": "Error description",
  "current": "Current line content",
  "suggested": "Suggested fix",
  "fix_description": "Human-readable fix description",
  "invalid_text": "sdsdsd",
  "context_before": "Previous line",
  "context_after": "Next line"
}
```

**Detected error types:**
- `trailing_comma`: Commas before closing brackets `}` or `]`
- `invalid_text`: Random text that shouldn't be there
- `single_quotes`: Single quotes instead of double quotes
- `comment`: JSON doesn't support `//` or `/* */` comments
- `unquoted_key`: Property names must be in double quotes
- `missing_comma`: Missing comma between properties
- `missing_value`: Missing value after colon
- `syntax_error`: General syntax errors

**Severity levels:**
- `error`: Critical errors that prevent JSON parsing
- `warning`: Non-critical issues (e.g., comments in valid JSON)

**Important:** This tool **only suggests** fixes. It does NOT modify your JSON. You must apply the suggestions manually.

## Configuration

Edit [config.json](config.json) to customize:

```json
{
  "default_language": "en",
  "indent": 2,
  "date_formats": [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%d.%m.%Y",
    "%d/%m/%Y"
  ]
}
```

## JSON Schema Examples

### Basic schema

```json
{
  "type": "object",
  "required": ["name", "age"],
  "properties": {
    "name": {"type": "string"},
    "age": {"type": "number", "minimum": 0}
  }
}
```

### Complex schema with nested objects

```json
{
  "type": "object",
  "required": ["user"],
  "properties": {
    "user": {
      "type": "object",
      "required": ["id", "email"],
      "properties": {
        "id": {"type": "integer"},
        "email": {"type": "string", "format": "email"},
        "profile": {
          "type": "object",
          "properties": {
            "firstName": {"type": "string"},
            "lastName": {"type": "string"},
            "age": {"type": "integer", "minimum": 0, "maximum": 150}
          }
        }
      }
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

### Schema with patterns and enums

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["active", "inactive", "pending"]
    },
    "phone": {
      "type": "string",
      "pattern": "^\\+?[1-9]\\d{1,14}$"
    },
    "url": {
      "type": "string",
      "format": "uri"
    }
  }
}
```

## Error Examples

### Syntax error - trailing comma

```json
Input: {"name": "test",}

Error:
{
  "valid": false,
  "error": {
    "line": 1,
    "column": 19,
    "error_line": "{\"name\": \"test\",}",
    "message": "Expecting property name enclosed in double quotes"
  }
}
```

### Syntax error - missing quotes

```json
Input: {name: "test"}

Error:
{
  "valid": false,
  "error": {
    "line": 1,
    "column": 2,
    "error_line": "{name: \"test\"}",
    "message": "Expecting property name enclosed in double quotes"
  }
}
```

### Syntax error - multiline with context

```json
Input:
{
  "name": "John",
  "age": 30,
  "city": "NYC"
  "country": "USA"
}

Error:
{
  "valid": false,
  "error": {
    "line": 5,
    "column": 3,
    "error_line": "  \"country\": \"USA\"",
    "context_before": "  \"city\": \"NYC\"",
    "context_after": "}",
    "message": "Expecting ',' delimiter"
  }
}
```

## Troubleshooting

### Server not starting

- Make sure Python 3.7+ is installed
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify the path in `mcp_settings.json` is correct and uses double backslashes on Windows

### Schema validation not working

- Install jsonschema: `pip install jsonschema`
- Restart Claude Code after installation

### YAML conversion not working

- Install PyYAML: `pip install pyyaml`
- Restart Claude Code after installation

### CSV conversion fails

- CSV conversion only works with flat arrays of objects
- Example valid input: `[{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]`
- Invalid: `{"data": [1, 2, 3]}` (not an array at root)

## Development

### Testing locally with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py
```

This will:
- Start the server
- Launch a web interface at http://localhost:6274
- Allow you to test all tools interactively

### Direct testing

```bash
python server.py
```

The server communicates via stdin/stdout using the MCP protocol.

## Use Cases

### 1. API Development
- Validate API request/response payloads
- Compare API versions for breaking changes
- Generate schemas from example data

### 2. Configuration Files
- Validate configuration files before deployment
- Merge environment-specific configs
- Convert configs between formats (JSON ↔ YAML)

### 3. Data Quality
- Validate data exports
- Check for required fields
- Detect malformed URLs, emails, dates

### 4. Testing
- Compare expected vs actual JSON in tests
- Generate test data statistics
- Validate test fixtures

### 5. Migration
- Compare data before/after migration
- Validate transformed data
- Convert between data formats

## Performance Notes

- **Large files**: The server loads entire JSON into memory. For very large files (>100MB), consider splitting or streaming
- **Deep nesting**: Deep comparison and statistics calculation are recursive. Very deep structures (>1000 levels) may be slow
- **Schema validation**: Complex schemas with many conditionals may be slower to validate

## Dependencies

- [mcp](https://github.com/modelcontextprotocol/python-sdk) - Model Context Protocol SDK
- [jsonschema](https://github.com/python-jsonschema/jsonschema) - JSON Schema validator (optional but recommended)
- [PyYAML](https://pyyaml.org/) - YAML support (optional)

## License

MIT License - see your project license for details.

## Related Tools

- **languagetool-mcp-server** - Spell checking for JSON values
- Use both together for comprehensive JSON validation (syntax + content)

## Contributing

Found a bug or want a feature? Please open an issue or submit a pull request!

## Changelog

### Version 1.0.0 (2024)
- Initial release
- 8 comprehensive JSON tools
- Precise error reporting with line/column numbers
- Schema validation support
- Format conversion (YAML, CSV, XML)
- Deep comparison and merge
- Type validation (URL, email, date)
