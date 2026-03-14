import subprocess
import json
import sys

def run_agent(question):
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        timeout=120
    )
    assert result.returncode == 0
    return json.loads(result.stdout.strip())

def test_framework_uses_read_file():
    output = run_agent("What Python web framework does this project's backend use?")
    assert "answer" in output
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "read_file" in tool_names
    assert "FastAPI" in output["answer"]

def test_item_count_uses_query_api():
    output = run_agent("How many items are in the database?")
    assert "answer" in output
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "query_api" in tool_names
