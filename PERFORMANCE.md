# Arcturus Performance Guide

Working with multiple agents, LLMs (Ollama), and full-stack development can be resource-intensive. Use this guide to keep your system responsive.

## 1. Monitoring Resources

The most common resource hogs are:
- **Node.js**: The frontend development server (`npm run dev`).
- **Python**: The backend API (`uvicorn`) and background agent tasks.
- **Ollama**: Local LLM serving can consume significant CPU/GPU and Memory even when idle.
- **CURL/Network Tasks**: Long-running or hung network requests.

### Usage Monitoring
Run the monitoring script to see what's using your resources:
```powershell
.\scripts\resource_monitor.ps1
```

## 2. Preventive Measures

- **Use `uv`**: We use `uv` for Python package management. it is significantly faster and more resource-efficient than standard `pip`.
- **Selective LLM Usage**: If you aren't actively testing LLM features, stop the Ollama service to free up 4GB+ of RAM.
- **Frontend Reloading**: If the frontend feels sluggish, restart the `npm run dev` process. Node.js memory usage can grow over time with HMR (Hot Module Replacement).

## 3. Cleanup Strategies

When the system feels slow, use the provided cleanup scripts to reset your environment:

### Aggressive Cleanup
This script kills all instances of Python, Node, Git, Ollama, and hung CURL processes.
```powershell
.\scripts\hard_cleanup.ps1
```

### Regular Dev Cleanup
A lighter version that targets only the development servers.
```powershell
.\scripts\cleanup_dev.ps1
```

## 4. Known Issues
- **Hung CURL processes**: Sometimes agents might leave `curl` processes running. The `hard_cleanup.ps1` script handles these.
- **LSP Overload**: If your editor (VS Code/Cursor) feels slow, the `hard_cleanup.ps1` script also kills the Language Server processes to force a refresh.
