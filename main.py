# PostMaker -- A simple TUI PostMan clone for testing REST APIs
import requests
import json
from termcolor import colored
import shlex
import argparse
import os
import difflib
from rich.syntax import Syntax
from rich.console import Console
from rich.table import Table
import re
import io
import time
from datetime import datetime
from rich.markdown import Markdown
import sys

console = Console()

# Get the absolute directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def rel_path(filename):
    return os.path.join(SCRIPT_DIR, filename)

COLLECTIONS_FILE = rel_path("data/collections.json")
HISTORY_FILE = rel_path("data/history.json")
VARIABLES_FILE = rel_path("data/variables.json")
GLOBAL_ALIASES_FILE = rel_path("data/global_aliases.json")
TEMPLATES_FILE = rel_path("data/templates.json")

def color_status(status_code):
    if 200 <= status_code < 300:
        return "green"
    elif 300 <= status_code < 400:
        return "cyan"
    elif 400 <= status_code < 500:
        return "yellow"
    elif 500 <= status_code < 600:
        return "red"
    else:
        return "white"

def print_banner():
    print(colored("="*60, "magenta"))
    print(colored("Welcome to PostMaker - A simple TUI PostMan clone for testing REST APIs", "blue", attrs=["bold"]))
    print(colored("="*60, "magenta"))
    print(colored("type `request` to make an API request.", "green"))
    print(colored("type `help` for more information.", "yellow"))
    print(colored("type `clear` to clear the screen.", "cyan"))
    print(colored("type `exit` to leave.", "red"))
    print(colored("="*60, "magenta"))

def load_collections():
    if os.path.exists(COLLECTIONS_FILE):
        with open(COLLECTIONS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            try:
                return json.loads(content)
            except Exception as e:
                return {}
    return {}

def save_collections(collections):
    # Ensure data directory exists
    os.makedirs(os.path.dirname(COLLECTIONS_FILE), exist_ok=True)
    with open(COLLECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(collections, f, indent=2)

def save_history(entry):
    # Ensure data directory exists
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def load_global_aliases():
    if os.path.exists(GLOBAL_ALIASES_FILE):
        with open(GLOBAL_ALIASES_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            try:
                return json.loads(content)
            except Exception:
                return {}
    return {}

def load_variables():
    if os.path.exists(VARIABLES_FILE):
        with open(VARIABLES_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            try:
                return json.loads(content)
            except Exception:
                return {}
    return {}

def load_templates():
    if os.path.exists(TEMPLATES_FILE):
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            try:
                return json.loads(content)
            except Exception:
                return {}
    return {}

def print_collections(collections):
    if not collections:
        print(colored("No collections saved.", "yellow"))
        return
    for collection, reqs in collections.items():
        print(colored(f"\nCollection: {collection}", "magenta", attrs=["bold"]))
        for alias, req in reqs.items():
            print(colored(f"  Alias: {alias}", "cyan"))
            print(colored(f"    Method: {req['method']}", "green"))
            print(colored(f"    URL: {req['url']}", "yellow"))
            print(colored(f"    Headers: {json.dumps(req.get('headers', {}))}", "white"))
            print(colored(f"    Data: {json.dumps(req.get('data', {}))}", "white"))

def print_global_aliases(alias=None):
    global_aliases = load_global_aliases()
    if not global_aliases:
        print(colored("No global aliases saved.", "yellow"))
        return
    print(colored("Global Aliases:", "magenta", attrs=["bold"]))
    if alias:
        req = global_aliases.get(alias)
        if not req:
            print(colored(f"Alias '{alias}' not found in global aliases.", "yellow"))
            return
        print(colored(f"  Alias: {alias}", "cyan"))
        print(colored(f"    Method: {req.get('method', '')}", "green"))
        print(colored(f"    URL: {req.get('url', '')}", "yellow"))
        print(colored(f"    Headers: {json.dumps(req.get('headers', {}))}", "white"))
        print(colored(f"    Data: {json.dumps(req.get('data', {}))}", "white"))
    else:
        for alias, req in global_aliases.items():
            print(colored(f"  Alias: {alias}", "cyan"))
            print(colored(f"    Method: {req.get('method', '')}", "green"))
            print(colored(f"    URL: {req.get('url', '')}", "yellow"))
            print(colored(f"    Headers: {json.dumps(req.get('headers', {}))}", "white"))
            print(colored(f"    Data: {json.dumps(req.get('data', {}))}", "white"))

def parse_auth(auth_type, auth_value):
    """
    Returns a headers dict for the given auth type and value.
    """
    if not auth_type or not auth_value:
        return {}
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {auth_value}"}
    elif auth_type == "basic":
        import base64
        if ':' not in auth_value:
            raise ValueError("Basic auth value must be in the form username:password")
        user, pwd = auth_value.split(':', 1)
        token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    else:
        raise ValueError("Unsupported auth type. Use 'bearer' or 'basic'.")

def highlight_body(body_str, content_type=None):
    """
    Print highlighted JSON or HTML, or fallback to plain text.
    """
    if content_type and "application/json" in content_type:
        try:
            console.print_json(body_str)
            return
        except Exception:
            pass
    elif content_type and ("html" in content_type or "<html" in body_str.lower()):
        syntax = Syntax(body_str, "html", theme="monokai", line_numbers=False)
        console.print(syntax)
        return
    # Try JSON anyway if not detected by content_type
    try:
        console.print_json(body_str)
        return
    except Exception:
        pass
    # Fallback: plain text
    console.print(body_str, style="white")

def highlight_headers(headers_dict):
    """
    Pretty-print headers as JSON using rich.
    """
    try:
        console.print_json(json.dumps(headers_dict))
    except Exception:
        print(colored(json.dumps(headers_dict, indent=2), "white"))

def print_response(status_code, reason, headers, body, content_type, only=None, console=console, elapsed=None, size=None):
    if elapsed is not None and size is not None:
        console.print(f"[bold blue]Time:[/bold blue] {elapsed:.2f} ms  [bold blue]Size:[/bold blue] {format_size(size)}")
    if only in (None, "status"):
        status_color = "green" if 200 <= status_code < 300 else "cyan" if 300 <= status_code < 400 else "yellow" if 400 <= status_code < 500 else "red"
        console.print(f"[bold {status_color}]Status: {status_code} {reason}[/bold {status_color}]")
    if only in (None, "headers"):
        table = Table(title="Headers:", show_header=True, header_style="bold magenta", show_lines=True, title_justify="left", title_style="bold magenta")
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        for k, v in headers.items():
            table.add_row(str(k), str(v))
        console.print(table)
    if only in (None, "body"):
        console.print("[bold yellow]Body:[/bold yellow]")
        if content_type and "application/json" in content_type:
            try:
                parsed = json.loads(body)
                console.print_json(json.dumps(parsed, indent=2))
            except Exception:
                console.print(body, style="white")
        elif content_type and "html" in content_type:
            syntax = Syntax(body, "html", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print(body, style="white")

def format_size(num):
    for unit in ['B','KB','MB','GB']:
        if num < 1024.0:
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{num:.2f} TB"

def request(method, url, headers=None, data=None, output_file=None, only=None, auth=None, assertion=None, preview=False, render=False):
    method = method.upper()
    if headers is None:
        headers = {}
    if data == {}:
        data = None

    urls = []
    if isinstance(url, str) and os.path.isfile(url):
        with open(url, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        urls = [url.strip()]

    for single_url in urls:
        vars = load_variables()
        url_to_use = single_url
        headers_to_use = headers.copy()
        data_to_use = data.copy() if isinstance(data, dict) else data
        for k, v in vars.items():
            url_to_use = url_to_use.replace(f"{{{{{k}}}}}", v)
            if headers_to_use:
                for hk in list(headers_to_use.keys()):
                    if isinstance(headers_to_use[hk], str):
                        headers_to_use[hk] = headers_to_use[hk].replace(f"{{{{{k}}}}}", v)
            if isinstance(data_to_use, dict):
                for dk in list(data_to_use.keys()):
                    if isinstance(data_to_use[dk], str):
                        data_to_use[dk] = data_to_use[dk].replace(f"{{{{{k}}}}}", v)

        auth_headers = {}
        if auth:
            try:
                auth_type, auth_value = auth.split(" ", 1)
                auth_headers = parse_auth(auth_type.lower(), auth_value)
            except Exception as e:
                print(colored(f"Auth error: {e}", "red", attrs=["bold"]))
                continue
        headers_to_use.update(auth_headers)

        if preview:
            print_request_preview(method, url_to_use, headers_to_use, data_to_use)
            confirm = input(colored("Send this request? (y/N): ", "yellow"))
            if confirm.lower() != "y":
                print(colored("Cancelled.", "yellow"))
                continue

        try:
            start = time.time()
            response = requests.request(method, url_to_use, headers=headers_to_use, json=data_to_use)
            elapsed = (time.time() - start) * 1000  # ms
            content_type = response.headers.get("Content-Type", "")
            try:
                body_str = json.dumps(response.json(), indent=2)
            except Exception:
                body_str = response.text
            resp_size = len(response.content)
            print_response(response.status_code, response.reason, dict(response.headers), body_str, content_type, only=only, console=console, elapsed=elapsed, size=resp_size)
            # Save to history
            save_history({
                "method": method,
                "url": url_to_use,
                "headers": headers_to_use,
                "data": data_to_use,
                "output_file": output_file,
                "only": only,
                "status": response.status_code,
                "elapsed": elapsed,
                "size": resp_size,
                "date": datetime.now().isoformat()
            })

            # Handle assertions
            if assertion:
                if assertion.startswith("status="):
                    expected = int(assertion.split("=", 1)[1])
                    if response.status_code == expected:
                        print(colored(f"Assertion passed: status={expected}", "green"))
                    else:
                        print(colored(f"Assertion failed: status={response.status_code} (expected {expected})", "red"))
                elif assertion.startswith("body_contains="):
                    expected = assertion.split("=", 1)[1]
                    if expected in body_str:
                        print(colored(f"Assertion passed: body contains '{expected}'", "green"))
                    else:
                        print(colored(f"Assertion failed: body does not contain '{expected}'", "red"))

        except Exception as e:
            print(colored(f"Error: {e}", "red", attrs=["bold"]))

def print_request_preview(method, url, headers, data):
    print(colored("REQUEST PREVIEW", "magenta", attrs=["bold"]))
    print(colored(f"Method: {method}", "green"))
    print(colored(f"URL: {url}", "yellow"))
    print(colored(f"Headers: {json.dumps(headers, indent=2)}", "white"))
    print(colored(f"Data: {json.dumps(data, indent=2) if data else None}", "white"))

def import_curl_command(curl_command, collection=None, alias=None):
    """
    Import a cURL command as a saved request (optionally into a collection).
    """
    import shlex
    import re
    tokens = shlex.split(curl_command)
    if not tokens or tokens[0] != "curl":
        print(colored("Not a valid cURL command.", "red"))
        return
    method = "GET"
    url = ""
    headers = {}
    data = None
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t in ("-X", "--request"):
            i += 1
            method = tokens[i].upper()
        elif t in ("-H", "--header"):
            i += 1
            h = tokens[i]
            if ":" in h:
                k, v = h.split(":", 1)
                headers[k.strip()] = v.strip()
        elif t in ("-d", "--data", "--data-raw", "--data-binary"):
            i += 1
            data = tokens[i]
        elif not t.startswith("-"):
            url = t
        i += 1
    if not url:
        print(colored("Could not parse URL from cURL command.", "red"))
        return
    req = {
        "method": method,
        "url": url,
        "headers": headers,
        "data": data
    }
    if collection and alias:
        collections = load_collections()
        if collection not in collections:
            collections[collection] = {}
        collections[collection][alias] = req
        save_collections(collections)
        print(colored(f"Imported cURL as '{alias}' in collection '{collection}'.", "green"))
    elif alias:
        global_aliases = load_global_aliases()
        global_aliases[alias] = req
        save_global_aliases(global_aliases)
        print(colored(f"Imported cURL as global alias '{alias}'.", "green"))
    else:
        print(colored("Alias required for import.", "red"))

def export_to_curl(req):
    """
    Export a saved request as a cURL command string.
    """
    method = req.get("method", "GET")
    url = req.get("url", "")
    headers = req.get("headers", {})
    data = req.get("data", None)
    cmd = ["curl"]
    if method != "GET":
        cmd += ["-X", method]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    if data:
        if isinstance(data, dict):
            data_str = json.dumps(data)
        else:
            data_str = str(data)
        cmd += ["-d", data_str]
    cmd += [url]
    return " ".join(shlex.quote(str(x)) for x in cmd)

def remove_global_alias(alias):
    global_aliases = load_global_aliases()
    if alias in global_aliases:
        confirm = input(colored(f"Remove global alias '{alias}'? (y/N): ", "red"))
        if confirm.lower() == "y":
            global_aliases.pop(alias)
            save_global_aliases(global_aliases)
            print(colored(f"Global alias '{alias}' removed.", "green"))
        else:
            print(colored("Cancelled.", "yellow"))
    else:
        print(colored(f"Global alias '{alias}' not found.", "yellow"))

def clear_history():
    if os.path.exists(HISTORY_FILE):
        confirm = input(colored("Are you sure you want to clear all history? (y/N): ", "red"))
        if confirm.lower() == "y":
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
            print(colored("History cleared.", "green"))
        else:
            print(colored("Cancelled.", "yellow"))
    else:
        print(colored("No history file found.", "yellow"))

def save_global_aliases(aliases):
    os.makedirs(os.path.dirname(GLOBAL_ALIASES_FILE), exist_ok=True)
    with open(GLOBAL_ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(aliases, f, indent=2)

def save_variables(vars):
    os.makedirs(os.path.dirname(VARIABLES_FILE), exist_ok=True)
    with open(VARIABLES_FILE, "w", encoding="utf-8") as f:
        json.dump(vars, f, indent=2)

def save_templates(templates):
    os.makedirs(os.path.dirname(TEMPLATES_FILE), exist_ok=True)
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2)

def clear_variables():
    vars = load_variables()
    if vars:
        confirm = input(colored("Are you sure you want to clear all variables? (y/N): ", "red"))
        if confirm.lower() == "y":
            save_variables({})
            print(colored("All variables cleared.", "green"))
        else:
            print(colored("Cancelled.", "yellow"))
    else:
        print(colored("No variables to clear.", "yellow"))

def remove_variable(var_name):
    vars = load_variables()
    if var_name in vars:
        confirm = input(colored(f"Remove variable '{var_name}'? (y/N): ", "red"))
        if confirm.lower() == "y":
            vars.pop(var_name)
            save_variables(vars)
            print(colored(f"Variable '{var_name}' removed.", "green"))
        else:
            print(colored("Cancelled.", "yellow"))
    else:
        print(colored(f"Variable '{var_name}' not found.", "yellow"))

def delete_collection(collection_name):
    collections = load_collections()
    if collection_name in collections:
        confirm = input(colored(f"Delete collection '{collection_name}' and all its requests? (y/N): ", "red"))
        if confirm.lower() == "y":
            collections.pop(collection_name)
            save_collections(collections)
            print(colored(f"Collection '{collection_name}' deleted.", "green"))
        else:
            print(colored("Cancelled.", "yellow"))
    else:
        print(colored(f"Collection '{collection_name}' not found.", "yellow"))

def delete_collection_item(collection_name, alias):
    collections = load_collections()
    if collection_name in collections and alias in collections[collection_name]:
        confirm = input(colored(f"Delete alias '{alias}' from collection '{collection_name}'? (y/N): ", "red"))
        if confirm.lower() == "y":
            collections[collection_name].pop(alias)
            save_collections(collections)
            print(colored(f"Alias '{alias}' deleted from collection '{collection_name}'.", "green"))
        else:
            print(colored("Cancelled.", "yellow"))
    else:
        print(colored(f"Alias '{alias}' not found in collection '{collection_name}'.", "yellow"))

def print_colored_diff(diff_lines):
    """
    Print unified diff lines with color:
    - Insertions (starting with '+') in green
    - Deletions (starting with '-') in red
    - Context/info lines in default color
    """
    for line in diff_lines:
        if line.startswith('+') and not line.startswith('+++'):
            print(colored(line, "green"))
        elif line.startswith('-') and not line.startswith('---'):
            print(colored(line, "red"))
        elif re.match(r'^@@.*@@', line):
            print(colored(line, "cyan", attrs=["bold"]))
        else:
            print(line)

def interactive_mode():
    print(colored("Interactive Request Builder", "magenta", attrs=["bold"]))
    method = input("HTTP method (GET/POST/...): ").strip().upper()
    url = input("URL: ").strip()
    headers = {}
    while True:
        h = input("Add header (key:value) or blank to finish: ").strip()
        if not h: break
        if ':' in h:
            k, v = h.split(':', 1)
            headers[k.strip()] = v.strip()
    data = input("Body (JSON or blank): ").strip()
    data_obj = json.loads(data) if data else None
    print_request_preview(method, url, headers, data_obj)
    if input("Send this request? (y/N): ").lower() == "y":
        request(method, url, headers, data_obj)
    else:
        print(colored("Cancelled.", "yellow"))

def main():
    ensure_data_files()  # <-- Ensure files/folders exist and are initialized
    print_banner()
    collections = load_collections()
    while True:
        try:
            cmd = input(colored("> ", "magenta", attrs=["bold"]))
        except EOFError:
            print()
            break
        if cmd != '':
            cmd = cmd.strip()
            if cmd.startswith('exit'):
                print(colored("Goodbye!", "red", attrs=["bold"]))
                save_collections(collections)
                exit()
            elif cmd.startswith('help'):
                print(colored("Available commands:", "blue", attrs=["bold"]))
                print(colored("request - Make an HTTP request", "green"))
                print(colored("save - Save a request to a collection or as a global alias", "yellow"))
                print(colored("send - Send a saved request by alias", "magenta"))
                print(colored("collections - List, view, or manage collections and items", "cyan"))
                print(colored("globalaliases - List all global aliases or show a specific alias", "magenta"))
                print(colored("vars - View, remove, or clear variables", "yellow"))
                print(colored("setvar - Set a variable", "green"))
                print(colored("history - View or clear request history", "cyan"))
                print(colored("replay - Replay a request from history", "magenta"))
                print(colored("chain - Run a chain of requests from a file", "cyan"))
                print(colored("diff - Diff two responses (from history or files)", "magenta"))
                print(colored("importcurl - Import a cURL command as a saved request", "green"))
                print(colored("exportcurl - Export a saved request as a cURL command", "yellow"))
                print(colored("removeglobal - Remove a global alias", "yellow"))
                print(colored("template - Manage request templates (save, list, use, delete)", "cyan"))
                print(colored("export - Export data (collections, aliases, variables, templates, or all)", "yellow"))
                print(colored("import - Import data from a file", "yellow"))
                print(colored("cat - View the contents of a file", "cyan"))
                print(colored("interactive - Interactive request builder", "green"))
                print(colored("clear - Clear the screen", "cyan"))
                print(colored("exit - Exit the program", "red"))
            elif cmd.startswith('clear'):
                print("\033c", end="")
            elif cmd.startswith('globalaliases'):
                parser = argparse.ArgumentParser(
                    prog='globalaliases',
                    description='List all global aliases or show a specific alias'
                )
                parser.add_argument('-a', '--alias', help='[Optional] Show only this alias')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                except SystemExit:
                    continue
                print_global_aliases(alias=args.alias)
            elif cmd.startswith('collections'):
                parser = argparse.ArgumentParser(
                    prog='collections',
                    description='List, delete, or manage collections and items.\n'
                                'Examples:\n'
                                '  collections                        # List all collections\n'
                                '  collections -c mycollection        # List all requests in mycollection\n'
                                '  collections -c mycollection -a alias1  # Show details for alias1 in mycollection\n'
                                '  collections -del mycollection      # Delete a collection\n'
                                '  collections -del mycollection:alias1  # Delete a specific alias in a collection\n'
                                '  collections -rm mycollection:alias1   # Remove a specific alias from a collection'
                )
                parser.add_argument('-c', '--collection', help='[Optional] Show only this collection')
                parser.add_argument('-a', '--alias', help='[Optional] Show only this alias (requires --collection)')
                parser.add_argument('-del', '--delete', metavar='TARGET', help='[Optional] Remove a specific collection')
                parser.add_argument('-rm', '--remove', metavar='TARGET', help='[Optional] Remove a specific alias from a collection (format: collection:alias)')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                except SystemExit:
                    continue
                try:
                    if args.remove:
                        if ':' in args.remove:
                            collection, alias = args.remove.split(':', 1)
                            delete_collection_item(collection, alias)
                        else:
                            print(colored("Format for --remove is collection:alias", "yellow"))
                    elif args.delete:
                        if ':' in args.delete:
                            collection, alias = args.delete.split(':', 1)
                            delete_collection_item(collection, alias)
                        else:
                            delete_collection(args.delete)
                    else:
                        collection = args.collection
                        alias = args.alias
                        collections = load_collections()
                        if collection and alias:
                            reqs = collections.get(collection, {})
                            req = reqs.get(alias)
                            if req:
                                print(colored(f"\nCollection: {collection}", "magenta", attrs=["bold"]))
                                print(colored(f"  Alias: {alias}", "cyan"))
                                print(colored(f"    Method: {req['method']}", "green"))
                                print(colored(f"    URL: {req['url']}", "yellow"))
                                print(colored(f"    Headers: {json.dumps(req.get('headers', {}))}", "white"))
                                print(colored(f"    Data: {json.dumps(req.get('data', {}))}", "white"))
                            else:
                                print(colored(f"Alias '{alias}' not found in collection '{collection}'.", "red", attrs=["bold"]))
                        elif collection:
                            reqs = collections.get(collection)
                            if reqs:
                                print(colored(f"\nCollection: {collection}", "magenta", attrs=["bold"]))
                                for alias, req in reqs.items():
                                    print(colored(f"  Alias: {alias}", "cyan"))
                                    print(colored(f"    Method: {req['method']}", "green"))
                                    print(colored(f"    URL: {req['url']}", "yellow"))
                                    print(colored(f"    Headers: {json.dumps(req.get('headers', {}))}", "white"))
                                    print(colored(f"    Data: {json.dumps(req.get('data', {}))}", "white"))
                            else:
                                print(colored(f"Collection '{collection}' not found.", "red", attrs=["bold"]))
                        else:
                            print_collections(collections)
                except SystemExit:
                    continue

            elif cmd.startswith('save'):
                parser = argparse.ArgumentParser(
                    prog='save',
                    description='Save a request to a collection or as a global alias. Example: save -a myalias -m GET -u https://example.com -hd \'{"Authorization":"token"}\' -d \'{"key":"value"}\''
                )
                parser.add_argument('-c', '--collection', help='[Optional] Collection name (if omitted, saves as global alias)')
                parser.add_argument('-a', '--alias', required=True, help='[Required] Alias (nickname) for the request')
                parser.add_argument('-m', '--method', required=True, help='[Required] HTTP method')
                parser.add_argument('-u', '--url', required=True, help='[Required] Request URL')
                parser.add_argument('-hd', '--headers', help='[Optional] Headers as JSON string')
                parser.add_argument('-d', '--data', help='[Optional] Body as JSON string')
                parser.add_argument('--auth', metavar='"bearer TOKEN" or "basic USER:PASS"', help='[Optional] Authentication helper: bearer <token> or basic <user>:<pass>')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    alias = args.alias
                    method = args.method.upper()
                    url = args.url
                    headers = json.loads(args.headers) if args.headers else {}
                    data = json.loads(args.data) if args.data else None
                    auth_headers = {}
                    if args.auth:
                        try:
                            auth_type, auth_value = args.auth.split(" ", 1)
                            auth_headers = parse_auth(auth_type.lower(), auth_value)
                        except Exception as e:
                            print(colored(f"Auth error: {e}", "red", attrs=["bold"]))
                            return
                    headers.update(auth_headers)
                    # Always store data as None if empty or {}
                    if not data or data == {}:
                        data = None
                    if args.collection:
                        # Save to collection
                        if args.collection not in collections:
                            collections[args.collection] = {}
                        collections[args.collection][alias] = {
                            "method": method,
                            "url": url,
                            "headers": headers,
                            "data": data
                        }
                        save_collections(collections)
                        print(colored(f"Request saved as '{alias}' in collection '{args.collection}'.", "green", attrs=["bold"]))
                    else:
                        # Save as global alias
                        global_aliases = load_global_aliases()
                        global_aliases[alias] = {
                            "method": method,
                            "url": url,
                            "headers": headers,
                            "data": data
                        }
                        save_global_aliases(global_aliases)
                        print(colored(f"Request saved as global alias '{alias}'.", "green", attrs=["bold"]))
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('send'):
                parser = argparse.ArgumentParser(
                    prog='send',
                    description='Send a saved request by alias. Example: send -a myalias [--output file] [--only body|headers|status]'
                )
                parser.add_argument('-a', '--alias', required=True, help='[Required] Alias of the saved request')
                parser.add_argument('-c', '--collection', help='[Optional] Collection name (default: search global aliases)')
                parser.add_argument('-o', '--output', help='[Optional] Output response to file')
                parser.add_argument('--only', choices=['body', 'headers', 'status'], help='[Optional] Output only this part of the response')
                parser.add_argument('--auth', metavar='"bearer TOKEN" or "basic USER:PASS"', help='[Optional] Override authentication for this request')
                parser.add_argument('--assertion', help='[Optional] Assertion to validate response (e.g., status=200, body_contains=keyword)')
                parser.add_argument('-p', '--preview', action='store_true', help='[Optional] Preview request before sending')
                # REMOVED: parser.add_argument('-r', '--render', action='store_true', help='[Optional] Render Markdown/HTML response')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    alias = args.alias
                    collection = args.collection
                    output_file = args.output
                    only = args.only
                    assertion = args.assertion
                    preview = args.preview
                    # REMOVED: render = args.render
                    auth_headers = {}

                    if args.auth:
                        try:
                            auth_type, auth_value = args.auth.split(" ", 1)
                            auth_headers = parse_auth(auth_type.lower(), auth_value)
                        except Exception as e:
                            print(colored(f"Auth error: {e}", "red", attrs=["bold"]))
                            return

                    req = None
                    if collection:
                        reqs = collections.get(collection, {})
                        req = reqs.get(alias)
                    else:
                        # Search global aliases first
                        global_aliases = load_global_aliases()
                        req = global_aliases.get(alias)
                        if not req:
                            print(colored(
                                f"Alias '{alias}' not found in global aliases. "
                                f"Did you mean to specify a collection with -c <collection>?",
                                "red", attrs=["bold"]))
                            continue
                        # Fallback: search all collections (optional, can be removed if you want strict global/collection separation)
                        # for coll, reqs in collections.items():
                        #     if alias in reqs:
                        #         req = reqs[alias]
                        #         break

                    if not req:
                        print(colored(f"Alias '{alias}' not found in collection '{collection}'.", "red", attrs=["bold"]))
                    else:
                        headers = dict(req.get('headers') or {})
                        headers.update(auth_headers)
                        data = req.get('data', None)
                        if data == {}:
                            data = None
                        request(
                            req['method'],
                            req['url'],
                            headers,
                            data,
                            output_file,
                            only,
                            assertion=assertion,
                            preview=preview,
                            render=False  # Always False, feature removed
                        )
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('request'):
                parser = argparse.ArgumentParser(
                    prog='request',
                    description='Make an HTTP request. Example: request -m GET -u https://example.com -hd \'{"Authorization": "token"}\' -d \'{"key": "value"}\' -o output.txt --only body'
                )
                parser.add_argument('-m', '--method', required=True, help='[Required] HTTP method (GET, POST, etc)')
                parser.add_argument('-u', '--url', required=True, help='[Required] Request URL')
                parser.add_argument('-hd', '--headers', help='[Optional] Headers as JSON string or @file.json')
                parser.add_argument('-d', '--data', help='[Optional] Body as JSON string or @file.json')
                parser.add_argument('-o', '--output', help='[Optional] Output response to file')
                parser.add_argument('--only', choices=['body', 'headers', 'status'], help='[Optional] Output only this part of the response')
                parser.add_argument('--auth', metavar='"bearer TOKEN" or "basic USER:PASS"', help='[Optional] Authentication helper: bearer <token> or basic <user>:<pass>')
                parser.add_argument('--assert', dest='assertion', help='[Optional] Assertion, e.g. status=200 or body_contains=foo')
                parser.add_argument('-p', '--preview', action='store_true', help='[Optional] Preview request before sending')
                # REMOVED: parser.add_argument('-r', '--render', action='store_true', help='[Optional] Render Markdown/HTML response')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    method = args.method.upper()
                    url = args.url

                    # --- Support loading headers/data from JSON files ---
                    headers = {}
                    if args.headers:
                        if args.headers.strip().startswith('@'):
                            file_path = args.headers.strip()[1:]
                            with open(file_path, "r", encoding="utf-8") as f:
                                headers = json.load(f)
                        else:
                            headers = json.loads(args.headers)
                    data = None
                    if args.data:
                        if args.data.strip().startswith('@'):
                            file_path = args.data.strip()[1:]
                            with open(file_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                        else:
                            data = json.loads(args.data)
                    # ---------------------------------------------------

                    output_file = args.output
                    only = args.only
                    assertion = args.assertion
                    auth_headers = {}
                    preview = args.preview
                    # REMOVED: render = args.render
                    if args.auth:
                        try:
                            auth_type, auth_value = args.auth.split(" ", 1)
                            auth_headers = parse_auth(auth_type.lower(), auth_value)
                        except Exception as e:
                            print(colored(f"Auth error: {e}", "red", attrs=["bold"]))
                            return
                    headers.update(auth_headers)
                    request(method, url, headers, data, output_file, only, assertion=assertion, preview=preview, render=False)
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('history'):
                parser = argparse.ArgumentParser(
                    prog='history',
                    description='View or clear request history.'
                )
                parser.add_argument('-cl', '--clear', action='store_true', help='[Optional] Clear all request history')
                parser.add_argument('-n', '--number', type=int, help='Show N most recent entries')
                parser.add_argument('-s', '--search', help='Search by URL or method')
                args = parser.parse_args(shlex.split(cmd)[1:])
                if args.clear:
                    clear_history()
                else:
                    if os.path.exists(HISTORY_FILE):
                        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                            history = json.load(f)
                        entries = history
                        if args.search:
                            entries = [e for e in entries if args.search.lower() in e["url"].lower() or args.search.lower() in e["method"].lower()]
                        if args.number:
                            entries = entries[-args.number:]
                        for i, entry in enumerate(entries):
                            print(colored(f"[{i}] {entry['method']} {entry['url']}  status={entry.get('status','?')}  time={entry.get('elapsed',0):.1f}ms  size={format_size(entry.get('size',0))}  date={entry.get('date','')}", "cyan"))
                    else:
                        print(colored("No history found.", "yellow"))
            elif cmd.startswith('replay'):
                # Usage: replay <index>
                parts = cmd.split()
                if len(parts) == 2 and parts[1].isdigit():
                    idx = int(parts[1])
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    if 0 <= idx < len(history):
                        entry = history[idx]
                        request(entry['method'], entry['url'], entry['headers'], entry['data'], entry.get('output_file'), entry.get('only'))
                    else:
                        print(colored("Invalid history index.", "red"))
                else:
                    print(colored("Usage: replay <index>", "yellow"))
            elif cmd.startswith('chain'):
                # Usage: chain <filename>
                parts = cmd.split()
                if len(parts) == 2:
                    filename = parts[1]
                    with open(filename, "r", encoding="utf-8") as f:
                        chain = json.load(f)
                    for req in chain:
                        print(colored(f"Running: {req['method']} {req['url']}", "cyan"))
                        request(
                            req['method'],
                            req['url'],
                            req.get('headers'),
                            req.get('data'),
                            req.get('output_file'),
                            req.get('only'),
                            req.get('auth')
                        )
                else:
                    print(colored("Usage: chain <filename>", "yellow"))
            elif cmd.startswith('setvar'):
                # Usage: setvar key value
                parts = cmd.split(maxsplit=2)
                if len(parts) == 3:
                    vars = load_variables()
                    vars[parts[1]] = parts[2]
                    save_variables(vars)
                    print(colored(f"Variable '{parts[1]}' set.", "green"))
                else:
                    print(colored("Usage: setvar key value", "yellow"))
            elif cmd.startswith('vars'):
                parser = argparse.ArgumentParser(
                    prog='vars',
                    description='View, remove, or clear variables.'
                )
                parser.add_argument('-rm', '--remove', metavar='KEY', help='[Optional] Remove a variable by key')
                parser.add_argument('-cl', '--clear', action='store_true', help='[Optional] Clear all variables')
                args = parser.parse_args(shlex.split(cmd)[1:])
                if args.clear:
                    clear_variables()
                elif args.remove:
                    remove_variable(args.remove)
                else:
                    vars = load_variables()
                    print(json.dumps(vars, indent=2))
            elif cmd.startswith('importcurl'):
                # Usage: importcurl "<curl command>" -a alias [-c collection]
                parser = argparse.ArgumentParser(
                    prog='importcurl',
                    description='Import a cURL command as a saved request. Example: importcurl "curl ..." -a alias [-c collection]'
                )
                parser.add_argument('curl', help='[Required] The cURL command string (in quotes)')
                parser.add_argument('-a', '--alias', required=True, help='[Required] Alias for the saved request')
                parser.add_argument('-c', '--collection', help='[Optional] Collection name')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    import_curl_command(args.curl, args.collection, args.alias)
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))

            elif cmd.startswith('exportcurl'):
                # Usage: exportcurl alias [-c collection]
                parser = argparse.ArgumentParser(
                    prog='exportcurl',
                    description='Export a saved request as a cURL command. Example: exportcurl myalias [-c collection]'
                )
                parser.add_argument('-a', '--alias', help='[Required] Alias of the saved request')
                parser.add_argument('-c', '--collection', help='[Optional] Collection name (default: global alias)')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    alias = args.alias
                    collection = args.collection
                    req = None
                    if collection:
                        reqs = collections.get(collection, {})
                        req = reqs.get(alias)
                    else:
                        global_aliases = load_global_aliases()
                        req = global_aliases.get(alias)
                    if not req:
                        print(colored(f"Alias '{alias}' not found.", "red"))
                    else:
                        print(export_to_curl(req))
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))

            elif cmd.startswith('removeglobal'):
                # Usage: removeglobal alias
                parts = cmd.split()
                if len(parts) == 2:
                    remove_global_alias(parts[1])
                else:
                    print(colored("Usage: removeglobal <alias>", "yellow"))
            elif cmd.startswith('diff'):
                parser = argparse.ArgumentParser(
                    prog='diff',
                    description='Diff two responses from history or files. Usage: diff <history_index1> <history_index2> OR diff <file1> <file2>'
                )
                parser.add_argument('first', help='First history index or file')
                parser.add_argument('second', help='Second history index or file')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                except SystemExit:
                    continue
                # Try to diff history indexes
                if args.first.isdigit() and args.second.isdigit():
                    idx1, idx2 = int(args.first), int(args.second)
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    if 0 <= idx1 < len(history) and 0 <= idx2 < len(history):
                        resp1 = history[idx1].get("body", "") if "body" in history[idx1] else json.dumps(history[idx1], indent=2)
                        resp2 = history[idx2].get("body", "") if "body" in history[idx2] else json.dumps(history[idx2], indent=2)
                        diff = difflib.unified_diff(
                            resp1.splitlines(), resp2.splitlines(),
                            fromfile=f"history[{idx1}]", tofile=f"history[{idx2}]",
                            lineterm=""
                        )
                        print_colored_diff(list(diff))
                    else:
                        print(colored("Invalid history indexes.", "red"))
                else:
                    # Try to diff files
                    if os.path.exists(args.first) and os.path.exists(args.second):
                        with open(args.first, "r", encoding="utf-8") as f1, open(args.second, "r", encoding="utf-8") as f2:
                            lines1 = f1.read().splitlines()
                            lines2 = f2.read().splitlines()
                        diff = difflib.unified_diff(
                            lines1, lines2,
                            fromfile=args.first, tofile=args.second,
                            lineterm=""
                        )
                        print_colored_diff(list(diff))
                    else:
                        print(colored("Files not found or invalid arguments.", "red"))
            elif cmd.startswith('cat '):
                # Usage: cat <filename>
                parts = cmd.split(maxsplit=1)
                if len(parts) == 2:
                    filename = parts[1].strip()
                    if os.path.exists(filename):
                        try:
                            with open(filename, "r", encoding="utf-8") as f:
                                content = f.read()
                            print(content)
                        except Exception as e:
                            print(colored(f"cat error: {e}", "red", attrs=["bold"]))
                    else:
                        print(colored(f"File '{filename}' not found.", "red"))
                else:
                    print(colored("Usage: cat <filename>", "yellow"))
            elif cmd.startswith('template'):
                parser = argparse.ArgumentParser(
                    prog='template',
                    description='Manage request templates.\n'
                                'Examples:\n'
                                '  template save -n mytemplate -m GET -u https://example.com -hd \'{"Authorization":"token"}\' -d \'{"key":"value"}\'\n'
                                '  template list\n'
                                '  template use -n mytemplate\n'
                                '  template delete -n mytemplate'
                )
                subparsers = parser.add_subparsers(dest='subcmd', required=True)

                # Save
                save_parser = subparsers.add_parser('save', help='Save a new template')
                save_parser.add_argument('-n', '--name', required=True, help='Template name')
                save_parser.add_argument('-m', '--method', required=True, help='HTTP method')
                save_parser.add_argument('-u', '--url', required=True, help='Request URL')
                save_parser.add_argument('-hd', '--headers', default="{}", help='Headers as JSON string')
                save_parser.add_argument('-d', '--data', default="{}", help='Body as JSON string')

                # List
                list_parser = subparsers.add_parser('list', help='List all templates')

                # Use
                use_parser = subparsers.add_parser('use', help='Use a template')
                use_parser.add_argument('-n', '--name', required=True, help='Template name')

                # Delete
                delete_parser = subparsers.add_parser('delete', help='Delete a template')
                delete_parser.add_argument('-n', '--name', required=True, help='Template name')

                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    if args.subcmd == 'save':
                        headers = json.loads(args.headers)
                        data = json.loads(args.data)
                        template_save(args.name, args.method, args.url, headers, data)
                    elif args.subcmd == 'list':
                        template_list()
                    elif args.subcmd == 'use':
                        template_use(args.name)
                    elif args.subcmd == 'delete':
                        templates = load_templates()
                        if args.name in templates:
                            templates.pop(args.name)
                            save_templates(templates)
                            print(colored(f"Template '{args.name}' deleted.", "green"))
                        else:
                            print(colored(f"Template '{args.name}' not found.", "yellow"))
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('export'):
                parser = argparse.ArgumentParser(
                    prog='export',
                    description='Export data to a file.\n'
                                'Examples:\n'
                                '  export -t all -f <file>\n'
                                '  export -t collections -f <file>\n'
                                '  export -t aliases -f <file>'
                )
                parser.add_argument('-t', '--target', required=True, help='[Required] Export target (all, collections, aliases, variables, templates)')
                parser.add_argument('-f', '--file', required=True, help='[Required] Output file')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    export_data(args.target, args.file)
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('import'):
                parser = argparse.ArgumentParser(
                    prog='import',
                    description='Import data from a file.'
                )
                parser.add_argument('-f', '--file', required=True, help='[Required] Input file')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    import_data(args.file)
                except SystemExit:
                    continue
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('interactive'):
                interactive_mode()
            else:
                print(colored("Invalid command. Type 'help' for a list of commands.", "red", attrs=["bold"]))

if __name__ == "__main__":
    main()