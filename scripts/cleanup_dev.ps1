# Arcturus Development Environment Cleanup Script
Write-Host "🧹 Starting Arcturus Cleanup..."

# 1. Kill Python processes (Backend, RAG server, Uvicorn)
Write-Host "🐍 Killing Python/Uvicorn processes..."
taskkill /F /IM python.exe /T 2>$null

# 2. Kill Node processes (Frontend dev server)
Write-Host "📦 Killing Node/NPM processes..."
taskkill /F /IM node.exe /T 2>$null

# 3. Kill hung network/utility processes
Write-Host "🌐 Clearing hung network tasks (curl, powershell)..."
taskkill /F /IM curl.exe /T 2>$null

Write-Host "✅ Cleanup Complete. System resources freed."
Write-Host "🚀 To restart:"
Write-Host "   - 'uv run uvicorn api:app --reload' (Backend)"
Write-Host "   - 'npm run dev' (Frontend)"
