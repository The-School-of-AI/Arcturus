# Arcturus Aggressive Cleanup Script
Write-Host "Starting Aggressive Workspace Cleanup..." -ForegroundColor Yellow

function Stop-ProjectProcess {
    param([string]$Name, [string]$Label)
    Write-Host "Clearing $Label ($Name)..." -NoNewline
    $procs = Get-Process -Name $Name -ErrorAction SilentlyContinue
    if ($procs) {
        taskkill /F /IM "$Name.exe" /T 2>$null | Out-Null
        Write-Host " Done." -ForegroundColor Green
    }
    else {
        Write-Host " Not running." -ForegroundColor Gray
    }
}

# 1. Kill hung curl processes
Stop-ProjectProcess "curl" "hung CURL processes"

# 2. Kill all Python instances
Stop-ProjectProcess "python" "all Python instances"

# 3. Kill all Node/NPM instances
Stop-ProjectProcess "node" "all Node/NPM instances"

# 4. Kill lingering Git/LSP processes
Stop-ProjectProcess "git" "Git processes"
Stop-ProjectProcess "language_server_windows_x64" "Language Server"

# 5. Terminate Ollama
Stop-ProjectProcess "ollama" "Ollama idle load"

Write-Host "`nCleanup Complete. System should feel more responsive." -ForegroundColor Cyan
Write-Host "Note: You will need to restart your Dev servers (uvicorn/npm) when you are ready to resume work."
