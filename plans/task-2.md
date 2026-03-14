# Task 2: The Documentation Agent

## Overview
Extend agent.py with two tools (read_file, list_files) and an agentic loop.

## Tools
- read_file: reads a file from the project directory
- list_files: lists files in a directory

## Security
- Both tools check that path does not contain ../ to prevent traversal outside project directory

## Agentic Loop
1. Send question + tool definitions to LLM
2. If LLM responds with tool_calls -> execute each tool, append results, go to step 1
3. If LLM responds with text -> output final JSON and exit
4. Stop after 10 tool calls maximum

## Output
JSON with answer, source, and tool_calls fields
