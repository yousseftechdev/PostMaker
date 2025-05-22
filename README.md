# PostMaker

**PostMaker** is a simple, terminal-based (TUI) API client inspired by Postman, designed for developers who prefer the command line. It allows you to send HTTP requests, manage collections of requests, use variables, view and replay history, assert responses, and more—all from your terminal.

---

## Features

- **Send HTTP requests** (GET, POST, PUT, DELETE, etc.)
- **Save requests** to named collections or as global aliases for reuse
- **Send saved requests** by alias (from collections or global aliases)
- **Use variables** in URLs, headers, and bodies
- **View and replay request history**
- **Pretty-print and syntax highlight** JSON and HTML responses and headers
- **Assertions** for status codes and response content
- **Chain requests** from a file
- **Diff responses** from history or files
- **Manage collections, global aliases, and variables** (add, remove, clear)
- **Import/export requests as cURL commands**
- **Authentication helpers** (Bearer, Basic)
- **Output responses to files** (with auto-naming for batch requests)
- **Robust CLI with helpful error handling**

---

## Getting Started

### 1. **Install Requirements**

```sh
pip install requests termcolor rich flask
```

### 2. **Run PostMaker**

```sh
python main.py
```

---

## Usage

### Basic Commands

- `request` — Make an HTTP request
- `save` — Save a request to a collection or as a global alias
- `send` — Send a saved request by alias (searches global aliases first, then collections)
- `collections` — List, view, or manage collections and items
- `vars` — View, remove, or clear variables
- `setvar` — Set a variable
- `history` — View or clear request history
- `replay` — Replay a request from history
- `chain` — Run a chain of requests from a file
- `diff` — Diff two responses (from history or files)
- `importcurl` — Import a cURL command as a saved request
- `exportcurl` — Export a saved request as a cURL command
- `removeglobal` — Remove a global alias
- `clear` — Clear the screen
- `exit` — Exit the program

---

### Making a Request

```sh
request -m GET -u https://jsonplaceholder.typicode.com/posts/1
```

**Options:**
- `-m, --method` (**required**) — HTTP method (GET, POST, etc.)
- `-u, --url` (**required**) — Request URL (can be a file with URLs)
- `-hd, --headers` — Headers as JSON string
- `-d, --data` — Body as JSON string
- `-o, --output` — Output response to file
- `--only` — Output only `body`, `headers`, or `status`
- `--auth` — Authentication helper: `"bearer TOKEN"` or `"basic USER:PASS"`
- `--assert` — Assertion, e.g. `status=200` or `body_contains=foo`

**Example:**
```sh
request -m POST -u https://api.example.com/data -hd '{"Authorization": "Bearer token"}' -d '{"key": "value"}'
```

---

### Using Variables

Variables let you reuse values (like base URLs, tokens, etc.) in your requests.

#### Set a Variable

```sh
setvar base_url https://jsonplaceholder.typicode.com
```

#### View Variables

```sh
vars
```

#### Use Variables in Requests

Use double curly braces in URLs, headers, or data:

```sh
request -m GET -u "{{base_url}}/posts/1"
```

#### Use Variables in Saved Requests

```sh
save -c demo -a getpost -m GET -u "{{base_url}}/posts/1"
send getpost -c demo
```

#### Remove or Clear Variables

```sh
vars -rm base_url      # Remove a variable
vars -cl               # Clear all variables
```

---

### Collections and Global Aliases

#### Save a Request to a Collection

```sh
save -c mycollection -a myalias -m GET -u https://api.example.com/data
```

#### Save a Request as a Global Alias

If you omit `-c`, the alias is saved globally and can be used from anywhere:

```sh
save -a myalias -m GET -u https://api.example.com/data
```

#### List Collections

```sh
collections
```

#### View a Collection

```sh
collections -c mycollection
```

#### View a Specific Request

```sh
collections -c mycollection -a myalias
```

#### Delete a Collection or Alias

```sh
collections -del mycollection
collections -del mycollection:myalias
collections -rm mycollection:myalias
```

#### Remove a Global Alias

```sh
removeglobal myalias
```

#### Using Global Aliases

You can use `send myalias` to send a request saved as a global alias. If not found, `send` will search all collections for the alias.

---

### Import/Export cURL

#### Import a cURL Command

```sh
importcurl "curl -X POST https://api.example.com/data -H 'Authorization: Bearer token' -d '{\"key\": \"value\"}'" -a myalias
importcurl "curl https://api.example.com/data" -a myalias -c mycollection
```

#### Export a Saved Request as cURL

```sh
exportcurl -a myalias
exportcurl -a myalias -c mycollection
```

---

### History

#### View History

```sh
history
```

#### Replay a Request

```sh
replay 0
```

#### Clear History

```sh
history -cl
```

---

### Chaining Requests

Run a sequence of requests from a JSON file:

**chain.json**
```json
[
  {"method": "GET", "url": "https://jsonplaceholder.typicode.com/posts/1"},
  {"method": "GET", "url": "https://jsonplaceholder.typicode.com/posts/2"}
]
```

```sh
chain chain.json
```

---

### Assertions

Add assertions to requests:

```sh
request -m GET -u https://jsonplaceholder.typicode.com/posts/1 --assert status=200
request -m GET -u https://jsonplaceholder.typicode.com/posts/1 --assert body_contains=title
```

---

### Diff Responses

Compare two responses from history or files:

```sh
diff 0 1
diff response1.txt response2.txt
```

---

### Authentication Helpers

Add authentication easily:

```sh
request -m GET -u https://api.example.com/data --auth "bearer mytoken"
request -m GET -u https://api.example.com/data --auth "basic user:pass"
```

---

### Output and Highlighting

- **All JSON and HTML responses and headers are syntax highlighted** using [rich](https://rich.readthedocs.io/).
- **Output to file:** Use `-o output.txt` to save the response (auto-numbered for batch requests).

---

## Example Workflow

```sh
setvar base_url https://jsonplaceholder.typicode.com
request -m GET -u "{{base_url}}/posts/1"
save -c demo -a getpost -m GET -u "{{base_url}}/posts/1"
send getpost -c demo
save -a globalget -m GET -u "{{base_url}}/posts/2"
send globalget
history
replay 0
diff 0 1
collections -c demo
collections -del demo:getpost
removeglobal globalget
vars -cl
importcurl "curl -X POST https://api.example.com/data -H 'Authorization: Bearer token' -d '{\"key\": \"value\"}'" -a myalias
exportcurl demo:getpost
```

---

## Testing API

You can use the included `testAPI.py` Flask app to test PostMaker locally:

```sh
python testAPI.py
```

---

## Tips

- Use variables for anything that repeats (base URLs, tokens, IDs).
- Use collections and global aliases to organize and reuse requests.
- Use history and diff to debug and compare responses.
- Use assertions to automate API checks.
- Use output files to save responses for further analysis.
- Use `importcurl` and `exportcurl` to work with cURL commands.

---

## License

MIT License

---

**Enjoy using PostMaker!**