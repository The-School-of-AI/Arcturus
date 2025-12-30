# Sandbox MCP Server

This MCP server provides a secure, isolated environment for executing secure Python code. It is designed for performing calculations, data processing, and logical operations without risking the host system.

## Tools

### `run_python_script(code: str) -> str`
Execute Python code in a secure sandbox.
- **code**: The Python code to execute.

## Restrictions
- The sandbox environment is isolated.
- Network access may be restricted.
- File system access is limited to the sandbox temporary directories.
