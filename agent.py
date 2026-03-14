import sys
import json
import os
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(".env.agent.secret")
load_dotenv(".env.docker.secret")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use for wiki docs and source code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path from project root, e.g. wiki/git.md or backend/app/main.py"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory. Use to discover files before reading them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory path from project root, e.g. wiki or backend/app/routers"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the deployed backend API. Use for live data: item counts, HTTP status codes, API errors. Set no_auth=true to test unauthenticated requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method: GET, POST, etc."},
                    "path": {"type": "string", "description": "API path, e.g. /items/ or /analytics/completion-rate?lab=lab-1"},
                    "body": {"type": "string", "description": "Optional JSON request body"},
                    "no_auth": {"type": "boolean", "description": "Set true to send request without Authorization header"}
                },
                "required": ["method", "path"]
            }
        }
    }
]

def is_safe_path(path):
    full_path = os.path.realpath(os.path.join(PROJECT_ROOT, path))
    return full_path.startswith(PROJECT_ROOT)

def read_file(path):
    if not is_safe_path(path):
        return "Error: path traversal not allowed."
    full_path = os.path.join(PROJECT_ROOT, path)
    if not os.path.isfile(full_path):
        return f"Error: file not found: {path}"
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

def list_files(path):
    if not is_safe_path(path):
        return "Error: path traversal not allowed."
    full_path = os.path.join(PROJECT_ROOT, path)
    if not os.path.isdir(full_path):
        return f"Error: directory not found: {path}"
    return "\n".join(os.listdir(full_path))

def query_api(method, path, body=None, no_auth=False):
    url = API_BASE_URL + path
    headers = {"Content-Type": "application/json"}
    if not no_auth:
        headers["Authorization"] = f"Bearer {os.getenv('LMS_API_KEY')}"
    try:
        resp = requests.request(
            method.upper(), url, headers=headers,
            json=json.loads(body) if body else None, timeout=10
        )
        return json.dumps({"status_code": resp.status_code, "body": resp.json()})
    except Exception as e:
        return json.dumps({"error": str(e)})

def execute_tool(name, args):
    if name == "read_file":
        return read_file(args["path"])
    elif name == "list_files":
        return list_files(args["path"])
    elif name == "query_api":
        return query_api(args["method"], args["path"], args.get("body"), args.get("no_auth", False))
    return "Error: unknown tool."

def main():
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py <question>", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_API_BASE"),
    )

    messages = [
        {"role": "system", "content": (
            "You are a helpful assistant for a software engineering project.\n"
            "Tools available:\n"
            "- list_files: discover files in a directory\n"
            "- read_file: read wiki docs (wiki/) or source code (backend/app/)\n"
            "- query_api: get live data from the backend API\n\n"
            "When to use each tool:\n"
            "- Wiki questions: read_file on wiki/ files\n"
            "- Source code questions: list_files on backend/app/routers, then read_file\n- Infrastructure questions: read Dockerfile, docker-compose.yml, caddy/ to trace requests\n"
            "- Live data questions (counts, status codes): query_api\n"
            "- Testing auth: query_api with no_auth=true\n- Bug diagnosis: first query_api to get the error, then read_file on backend/app/routers/ to find the bug in source code\n\n"
            "Always set source to the wiki file path if you used read_file on wiki/.\n"
            "Be concise."
        )},
        {"role": "user", "content": question}
    ]

    all_tool_calls = []
    max_tool_calls = 15
    tool_call_count = 0
    answer = ""
    source = ""

    while tool_call_count < max_tool_calls:
        print("Calling LLM...", file=sys.stderr)
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=messages,
            tools=TOOLS,
            timeout=60,
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                tool_call_count += 1
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                print(f"Tool call: {name}({args})", file=sys.stderr)
                result = execute_tool(name, args)
                all_tool_calls.append({"tool": name, "args": args, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result
                })
        else:
            answer = (msg.content or "").strip()
            break

    for tc in all_tool_calls:
        if tc["tool"] == "read_file" and tc["args"].get("path", "").startswith("wiki/"):
            source = tc["args"]["path"]
            break
    if not source:
        for tc in all_tool_calls:
            if tc["tool"] == "read_file" and tc["args"].get("path", "").startswith("backend/"):
                source = tc["args"]["path"]
                break
    if not source:
        for line in answer.split("\n"):
            if "wiki/" in line:
                parts = line.split("wiki/")
                if len(parts) > 1:
                    source = "wiki/" + parts[1].strip().strip(".")
                    break

    result = {"answer": answer, "source": source, "tool_calls": all_tool_calls}
    print(json.dumps(result))

if __name__ == "__main__":
    main()
