# Arcturus Lightweight Resource Monitor
Write-Host "--- Arcturus Resource Monitor ---" -ForegroundColor Cyan

$processNames = @("python", "pythonw", "node", "ollama", "ollama_llama_server", "curl", "git", "language_server_windows_x64", "uv", "uvicorn", "powershell")
$heavyProcesses = Get-Process | Where-Object { $processNames -contains $_.ProcessName } | Sort-Object CPU -Descending

if ($heavyProcesses) {
    Write-Host ("{0,-20} {1,-10} {2,-15} {3,-10}" -f "ProcessName", "Id", "Mem(MB)", "CPU(s)")
    Write-Host ("-" * 60)
    foreach ($p in $heavyProcesses) {
        try {
            $mem = [math]::Round($p.WorkingSet64 / 1MB, 2)
            $cpu = [math]::Round($p.CPU, 2)
            Write-Host ("{0,-20} {1,-10} {2,-15} {3,-10}" -f $p.ProcessName, $p.Id, $mem, $cpu)
        }
        catch {
            # Some processes might exit while we iterate
        }
    }
}
else {
    Write-Host "No active Arcturus-related processes found." -ForegroundColor Gray
}

Write-Host "`nRecommendation:" -ForegroundColor Yellow
Write-Host "If memory is > 1000MB or CPU is consistently high, consider running: .\scripts\hard_cleanup.ps1"
