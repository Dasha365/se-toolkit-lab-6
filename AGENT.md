# Agent Documentation

## Overview
A CLI agent that answers questions about a software engineering project. It uses an agentic loop with three tools to read documentation, source code, and query the live backend API.

## How to Run
```bash
uv run agent.py "Your question here"
```

## Output Format
```json
{"answer": "...", "source": "wiki/file.md#section", "tool_calls": [...]}
```

## LLM Provider
- Provider: Qwen Code API (via qwen-code-oai-proxy on VM)
- Model: qwen3-coder-plus
- Base URL: configured in .env.agent.secret

## Environment Variables
- `LLM_API_KEY` — LLM provider API key (.env.agent.secret)
- `LLM_API_BASE` — LLM API endpoint URL (.env.agent.secret)
- `LLM_MODEL` — model name (.env.agent.secret)
- `LMS_API_KEY` — backend API key for query_api (.env.docker.secret)
- `AGENT_API_BASE_URL` — backend base URL, defaults to http://localhost:42002

## Tools

### read_file
Reads a file from the project by relative path. Used for wiki documentation and source code. Blocks path traversal outside the project directory.

### list_files
Lists files in a directory by relative path. Used to discover files before reading them. Blocks path traversal outside the project directory.

### query_api
Calls the deployed backend API. Authenticates with LMS_API_KEY. Supports GET/POST and optional no_auth flag to test unauthenticated requests.

## Agentic Loop
1. Send question + tool definitions to LLM
2. If LLM responds with tool_calls → execute each tool, append results, repeat
3. If LLM responds with text → output final JSON and exit
4. Maximum 15 tool calls per question

## System Prompt Strategy
The system prompt tells the LLM which tool to use for each type of question:
- Wiki questions → read_file on wiki/ files
- Source code questions → list_files on backend/app/routers, then read_file
- Infrastructure questions → read Dockerfile, docker-compose.yml, caddy/
- Live data questions → query_api
- Bug diagnosis → query_api first, then read_file on backend/app/routers/
- Auth testing → query_api with no_auth=true

## Lessons Learned
The biggest challenge was getting the LLM to use the right tool for the right question. Vague tool descriptions caused the LLM to call the wrong tools or build wrong paths. Fixing tool descriptions and adding specific path hints in the system prompt made a big difference. Another issue was the source field — the agent was only looking for wiki/ references in the answer text, but switching to extracting source from tool_calls directly made it reliable. The tool call limit also caused problems for complex questions that needed many file reads — increasing it from 10 to 15 fixed the last failing question.

## Final Eval Score
10/10 local questions passed.
