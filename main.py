# PostMaker -- A simple TUI PostMan clone for testing REST APIs
import requests
import json
from termcolor import colored
import shlex
import argparse
import os
from rich import print_json
import uuid
import difflib
from rich.syntax import Syntax
from rich.console import Console
import re

console = Console()

COLLECTIONS_FILE = "data/collections.json"
HISTORY_FILE = "data/history.json"
VARIABLES_FILE = "data/variables.json"
GLOBAL_ALIASES_FILE = "data/global_aliases.json"

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
            return json.load(f)
    return {}

def save_collections(collections):
    with open(COLLECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(collections, f, indent=2)

def save_history(entry):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def load_variables():
    if os.path.exists(VARIABLES_FILE):
        with open(VARIABLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_variables(vars):
    with open(VARIABLES_FILE, "w", encoding="utf-8") as f:
        json.dump(vars, f, indent=2)

def load_global_aliases():
    if os.path.exists(GLOBAL_ALIASES_FILE):
        with open(GLOBAL_ALIASES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_global_aliases(aliases):
    with open(GLOBAL_ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(aliases, f, indent=2)

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

def request(method, url, headers=None, data=None, output_file=None, only=None, auth=None, assertion=None):
    method = method.upper()
    headers_input = headers
    data_input = data

    # If url is a file, load all URLs from it
    urls = []
    if isinstance(url, str) and os.path.isfile(url):
        with open(url, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        urls = [url.strip()]

    for single_url in urls:
        # Replace variables in URL, headers, and data
        vars = load_variables()
        url_to_use = single_url
        headers_to_use = headers_input
        data_to_use = data_input
        for k, v in vars.items():
            url_to_use = url_to_use.replace(f"{{{{{k}}}}}", v)
            if headers_to_use:
                headers_to_use = headers_to_use.replace(f"{{{{{k}}}}}", v)
            if data_to_use:
                data_to_use = data_to_use.replace(f"{{{{{k}}}}}", v)

        # Parse auth if provided
        auth_headers = {}
        if auth:
            try:
                auth_type, auth_value = auth.split(" ", 1)
                auth_headers = parse_auth(auth_type.lower(), auth_value)
            except Exception as e:
                print(colored(f"Auth error: {e}", "red", attrs=["bold"]))
                continue

        headers_dict = json.loads(headers_to_use) if headers_to_use else {}
        headers_dict.update(auth_headers)
        data_dict = json.loads(data_to_use) if data_to_use else None

        try:
            response = requests.request(method, url_to_use, headers=headers_dict, json=data_dict)
            status_color = color_status(response.status_code)
            status_line = f"\nStatus: {response.status_code} {response.reason}"
            headers_str = json.dumps(dict(response.headers), indent=2)
            try:
                body_str = json.dumps(response.json(), indent=2)
            except Exception:
                body_str = response.text

            # Determine what to print/output
            output_content = ""
            if only == "status":
                print(colored(status_line, status_color, attrs=["bold"]))
                output_content = status_line + "\n"
            elif only == "headers":
                print(colored("Headers:", "cyan", attrs=["bold"]))
                highlight_headers(dict(response.headers))
                output_content = headers_str + "\n"
            elif only == "body":
                print(colored("Body:", "yellow", attrs=["bold"]))
                content_type = response.headers.get("Content-Type", "")
                highlight_body(body_str, content_type)
                output_content = body_str + "\n"
            else:
                # Print all
                print(colored(status_line, status_color, attrs=["bold"]))
                print(colored("-"*60, "magenta"))
                print(colored("Headers:", "cyan", attrs=["bold"]))
                highlight_headers(dict(response.headers))
                print(colored("-"*60, "magenta"))
                print(colored("Body:", "yellow", attrs=["bold"]))
                content_type = response.headers.get("Content-Type", "")
                highlight_body(body_str, content_type)
                print(colored("-"*60, "magenta"))
                output_content = (
                    status_line + "\n" +
                    "-"*60 + "\n" +
                    "Headers:\n" + headers_str + "\n" +
                    "-"*60 + "\n" +
                    "Body:\n" + body_str + "\n" +
                    "-"*60 + "\n"
                )

            # Output to file if requested
            if output_file:
                # If multiple URLs, append index to filename
                if len(urls) > 1:
                    base, ext = os.path.splitext(output_file)
                    out_file = f"{base}_{urls.index(single_url)}{ext}"
                else:
                    out_file = output_file
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(output_content)
                print(colored(f"Response written to {out_file}", "green", attrs=["bold"]))

            # Save to history
            save_history({
                "method": method,
                "url": url_to_use,
                "headers": headers_dict,
                "data": data_dict,
                "output_file": output_file,
                "only": only
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

def main():
    print_banner()
    collections = load_collections()
    while True:
        cmd = input(colored("> ", "magenta", attrs=["bold"]))
        if cmd != '':
            cmd = cmd.strip()
            if cmd.startswith('exit'):
                print(colored("Goodbye!", "red", attrs=["bold"]))
                save_collections(collections)
                exit()
            elif cmd.startswith('help'):
                print(colored("Available commands:", "blue", attrs=["bold"]))
                print(colored("request - Make an HTTP request", "green"))
                print(colored("save - Save a request to a collection", "yellow"))
                print(colored("collections - List all collections and requests", "cyan"))
                print(colored("send <alias> [--output file] [--only body|headers|status] - Send a saved request by alias", "magenta"))
                print(colored("history - View or clear request history", "cyan"))
                print(colored("replay <index> - Replay a request from history", "magenta"))
                print(colored("chain <filename> - Run a chain of requests from a file", "cyan"))
                print(colored("setvar key value - Set a variable", "green"))
                print(colored("vars - View, remove, or clear variables", "yellow"))
                print(colored("importcurl \"<curl command>\" -a alias [-c collection] - Import a cURL command", "green"))
                print(colored("exportcurl <alias> [-c collection] - Export a saved request as cURL", "yellow"))
                print(colored("removeglobal <alias> - Remove a global alias", "yellow"))
                print(colored("diff <history_index1> <history_index2> OR diff <file1> <file2> - Diff two responses", "magenta"))
                print(colored("exit - Exit the program", "red"))
                print(colored("clear - Clear the screen", "cyan"))
            elif cmd.startswith('clear'):
                print("\033c", end="")
                # print_banner()
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
                parser.add_argument('-del', '--delete', metavar='TARGET', help='[Optional] Delete a collection')
                parser.add_argument('-rm', '--remove', metavar='TARGET', help='[Optional] Remove a specific alias from a collection (format: collection:alias)')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                except SystemExit:
                    print(colored("Invalid usage. See 'help' or use -h for options.", "red"))
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
                    parser.print_help()

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
                    parser.print_help()
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('send'):
                parser = argparse.ArgumentParser(
                    prog='send',
                    description='Send a saved request by alias. Example: send myalias [--output file] [--only body|headers|status]'
                )
                parser.add_argument('alias', help='[Required] Alias of the saved request')
                parser.add_argument('-c', '--collection', help='[Optional] Collection name (default: search global aliases)')
                parser.add_argument('-o', '--output', help='[Optional] Output response to file')
                parser.add_argument('--only', choices=['body', 'headers', 'status'], help='[Optional] Output only this part of the response')
                parser.add_argument('--auth', metavar='"bearer TOKEN" or "basic USER:PASS"', help='[Optional] Override authentication for this request')
                parser.add_argument('--assertion', help='[Optional] Assertion to validate response (e.g., status=200, body_contains=keyword)')
                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    alias = args.alias
                    collection = args.collection
                    output_file = args.output
                    only = args.only
                    assertion = args.assertion
                    auth_headers = {}
                    if args.auth:
                        try:
                            auth_type, auth_value = args.auth.split(" ", 1)
                            auth_headers = parse_auth(auth_type.lower(), auth_value)
                        except Exception as e:
                            print(colored(f"Auth error: {e}", "red", attrs=["bold"]))
                            return
                    found = False
                    req = None
                    if collection:
                        reqs = collections.get(collection, {})
                        req = reqs.get(alias)
                        if req:
                            found = True
                    else:
                        # Search global aliases first
                        global_aliases = load_global_aliases()
                        if alias in global_aliases:
                            req = global_aliases[alias]
                            found = True
                        else:
                            # Optionally, search all collections for alias as fallback
                            for coll, reqs in collections.items():
                                if alias in reqs:
                                    req = reqs[alias]
                                    found = True
                                    break
                    if not found or not req:
                        print(colored(f"Alias '{alias}' not found.", "red", attrs=["bold"]))
                    else:
                        headers = req.get('headers', {})
                        headers.update(auth_headers)
                        request(req['method'], req['url'], json.dumps(headers), json.dumps(req.get('data', {})), output_file, only, assertion=assertion)
                except SystemExit:
                    parser.print_help()
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('request'):
                parser = argparse.ArgumentParser(
                    prog='request',
                    description='Make an HTTP request. Example: request -m GET -u https://example.com -hd \'{"Authorization": "token"}\' -d \'{"key": "value"}\' -o output.txt --only body'
                )
                parser.add_argument('-m', '--method', required=True, help='[Required] HTTP method (GET, POST, etc)')
                parser.add_argument('-u', '--url', required=True, help='[Required] Request URL')
                parser.add_argument('-hd', '--headers', help='[Optional] Headers as JSON string')
                parser.add_argument('-d', '--data', help='[Optional] Body as JSON string')
                parser.add_argument('-o', '--output', help='[Optional] Output response to file')
                parser.add_argument('--only', choices=['body', 'headers', 'status'], help='[Optional] Output only this part of the response')
                parser.add_argument('--auth', metavar='"bearer TOKEN" or "basic USER:PASS"', help='[Optional] Authentication helper: bearer <token> or basic <user>:<pass>')
                parser.add_argument('--assert', dest='assertion', help='[Optional] Assertion, e.g. status=200 or body_contains=foo')

                try:
                    args = parser.parse_args(shlex.split(cmd)[1:])
                    method = args.method.upper()
                    url = args.url
                    headers = json.loads(args.headers) if args.headers else {}
                    data = json.loads(args.data) if args.data else None
                    output_file = args.output
                    only = args.only
                    assertion = args.assertion
                    auth_headers = {}
                    if args.auth:
                        try:
                            auth_type, auth_value = args.auth.split(" ", 1)
                            auth_headers = parse_auth(auth_type.lower(), auth_value)
                        except Exception as e:
                            print(colored(f"Auth error: {e}", "red", attrs=["bold"]))
                            return
                    headers.update(auth_headers)
                    request(method, url, headers, data, output_file, only, assertion=assertion)
                except SystemExit:
                    parser.print_help()
                except Exception as e:
                    print(colored(f"Error: {e}", "red", attrs=["bold"]))
            elif cmd.startswith('history'):
                parser = argparse.ArgumentParser(
                    prog='history',
                    description='View or clear request history.'
                )
                parser.add_argument('-cl', '--clear', action='store_true', help='[Optional] Clear all request history')
                args = parser.parse_args(shlex.split(cmd)[1:])
                if args.clear:
                    clear_history()
                else:
                    if os.path.exists(HISTORY_FILE):
                        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                            history = json.load(f)
                        for i, entry in enumerate(history):
                            print(colored(f"[{i}] {entry['method']} {entry['url']}", "cyan"))
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
                    parser.print_help()
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
                    parser.print_help()
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
                    print(colored("Invalid usage. See 'help' or use -h for options.", "red"))
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

if __name__ == "__main__":
    main()