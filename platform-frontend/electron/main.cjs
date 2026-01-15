const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const isDev = !app.isPackaged;
const { spawn } = require('child_process');
const os = require('os');
const fs = require('fs');

// Try to load node-pty
let pty;
try {
    pty = require('node-pty');
} catch (e) {
    console.error("[Electron] Failed to load node-pty. Terminal features will be disabled.", e);
}

let mainWindow;
let backendProcesses = [];
// Terminal state
let ptyProcess = null;
let activeTerminalCwd = null;
let activeTerminalBuffer = ""; // Store terminal history

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.cjs'),
            webviewTag: true,
        },
        titleBarStyle: 'hiddenInset',
        trafficLightPosition: { x: 12, y: 12 }, // Optional: adjust slightly if needed
        backgroundColor: '#0b0f1a', // Matching your theme
        title: "Arcturus Platform"
    });

    const startUrl = isDev
        ? 'http://localhost:5173'
        : `file://${path.join(__dirname, '../dist/index.html')}`;

    console.log(`[Electron] Loading URL: ${startUrl}`);
    mainWindow.loadURL(startUrl);

    // DevTools: Uncomment to enable by default
    // if (isDev) {
    //     mainWindow.webContents.openDevTools();
    // }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startBackend(command, args, name) {
    console.log(`[Electron] Spawning Backend [${name}]: ${command} ${args.join(' ')}`);
    const rootPath = path.join(__dirname, '..', '..');

    const proc = spawn(command, args, {
        cwd: rootPath,
        shell: true,
        detached: true, // Allow killing the whole process group
        env: { ...process.env, PYTHONUNBUFFERED: "1" } // Ensure we see logs instantly
    });

    proc.stdout.on('data', (data) => {
        process.stdout.write(`[${name}] ${data}`);
    });

    proc.stderr.on('data', (data) => {
        process.stderr.write(`[${name} ERR] ${data}`);
    });

    proc.on('close', (code) => {
        console.log(`[Electron] Backend [${name}] exited with code ${code}`);
    });

    backendProcesses.push(proc);
}

// --- Terminal Handlers ---
// --- Terminal Handlers (Python PTY Bridge) ---
function setupTerminalHandlers() {

    ipcMain.on('terminal:create', (event, options) => {
        let cwd = options.cwd || path.resolve(__dirname, '..', '..');
        const fs = require('fs');
        if (!fs.existsSync(cwd)) {
            cwd = path.resolve(__dirname, '..', '..');
        }

        // Always recreate the terminal session to ensure a fresh prompt on UI reloads
        if (ptyProcess && typeof ptyProcess.exitCode !== 'number') {
            console.log(`[Electron] Ending previous terminal session at '${activeTerminalCwd}'`);
            try {
                ptyProcess.kill();
            } catch (e) { }
            ptyProcess = null;
        }

        activeTerminalCwd = cwd;
        const bridgePath = path.join(__dirname, 'pty_bridge.py');
        console.log(`[Electron] Spawning Python PTY Bridge: ${bridgePath} in ${cwd}`);

        try {
            // Spawn python script which handles the PTY fork
            ptyProcess = spawn('python3', ['-u', bridgePath], {
                cwd: cwd,
                detached: true,
                env: { ...process.env, TERM: 'xterm-256color', COLUMNS: '120', LINES: '30' },
                stdio: ['pipe', 'pipe', 'pipe']
            });

            console.log(`[Electron] Bridge process created: PID ${ptyProcess.pid}`);

            ptyProcess.on('error', (err) => {
                console.error(`[Electron] Bridge failed to start or encountered an error:`, err);
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', `\r\n\x1b[31m[System Error] Failed to start terminal bridge: ${err.message}\x1b[0m\r\n`);
                }
            });

            // Handle Output
            ptyProcess.stdout.on('data', (data) => {
                const str = data.toString('utf-8');
                // Persist to history buffer (max 50KB)
                if (activeTerminalBuffer.length > 50000) {
                    activeTerminalBuffer = activeTerminalBuffer.slice(-40000); // Keep last 40KB
                }
                activeTerminalBuffer += str;

                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', str);
                }
            });

            ptyProcess.stderr.on('data', (data) => {
                const str = data.toString('utf-8');
                console.error(`[Electron-PTY-Stderr] ${str}`);
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', `\x1b[33m${str}\x1b[0m`);
                }
            });

            ptyProcess.on('close', (code, signal) => {
                console.log(`[Electron] Bridge exited with code ${code}, signal ${signal}`);
                ptyProcess = null;
            });

        } catch (ex) {
            console.error('[Electron] Failed to spawn bridge:', ex);
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:outgoing', `\r\n\x1b[31mError spawning terminal bridge: ${ex.message}\x1b[0m\r\n`);
            }
        }
    });

    ipcMain.on('terminal:incoming', (event, data) => {
        if (ptyProcess && ptyProcess.stdin) {
            try {
                // console.log(`[Electron-Input] Writing ${data.length} bytes to PTY`); // Debug logs
                ptyProcess.stdin.write(data);
            } catch (err) {
                console.error("Write error", err);
            }
        } else {
            console.warn("[Electron] terminal:incoming received but ptyProcess is null or stdin closed.");
        }
    });

    ipcMain.on('terminal:resize', (event, { cols, rows }) => {
        if (ptyProcess) {
            try {
                ptyProcess.resize(cols, rows);
            } catch (e) { }
        }
    });

    ipcMain.handle('terminal:read', async () => {
        console.log('[Electron] terminal:read invoked from Agent');
        // Return the last 10KB of history to avoid overwhelming LLM
        return { success: true, content: activeTerminalBuffer.slice(-10000) || "[No output captured yet]" };
    });
}

// --- File System Handlers ---
function setupFSHandlers() {
    // Open Directory Dialog
    ipcMain.handle('dialog:openDirectory', async () => {
        console.log('[Electron] dialog:openDirectory invoked');
        const { dialog } = require('electron');
        try {
            const result = await dialog.showOpenDialog(mainWindow, {
                properties: ['openDirectory', 'createDirectory']
            });
            console.log('[Electron] Dialog result:', result);
            if (result.canceled) return null;
            return result.filePaths[0];
        } catch (error) {
            console.error('[Electron] dialog:openDirectory error:', error);
            throw error;
        }
    });

    // Shell Operations
    ipcMain.on('shell:reveal', (event, path) => {
        shell.showItemInFolder(path);
    });

    ipcMain.on('shell:openExternal', (event, url) => {
        shell.openExternal(url);
    });

    // Shell Execution for Agent
    ipcMain.handle('shell:exec', async (event, { cmd, cwd }) => {
        console.log(`[Electron] shell:exec '${cmd}' in '${cwd}'`);
        const { exec } = require('child_process');
        return new Promise((resolve) => {
            // Added 60s timeout to prevent hanging on interactive inputs (like python's input())
            exec(cmd, {
                cwd: cwd || undefined,
                maxBuffer: 10 * 1024 * 1024, // Increased to 10MB
                timeout: 60000
            }, (error, stdout, stderr) => {
                if (error) {
                    const isTimeout = error.killed || error.signal === 'SIGTERM';
                    resolve({
                        success: false,
                        error: isTimeout ? "Command timed out after 60s (likely waiting for input)" : error.message,
                        stdout: stdout || '',
                        stderr: stderr || ''
                    });
                } else {
                    resolve({
                        success: true,
                        stdout: stdout || '',
                        stderr: stderr || ''
                    });
                }
            });
        });
    });

    // File Operations
    ipcMain.handle('fs:create', async (event, { type, path: targetPath, content }) => {
        try {
            if (type === 'folder') {
                if (!fs.existsSync(targetPath)) {
                    fs.mkdirSync(targetPath, { recursive: true });
                }
            } else {
                // Ensure parent dir exists
                const parentDir = path.dirname(targetPath);
                if (!fs.existsSync(parentDir)) {
                    fs.mkdirSync(parentDir, { recursive: true });
                }
                fs.writeFileSync(targetPath, content || '', 'utf-8');
            }
            return { success: true };
        } catch (error) {
            console.error('[Electron] fs:create failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:rename', async (event, { oldPath, newPath }) => {
        try {
            if (fs.existsSync(newPath)) {
                throw new Error('Destination already exists');
            }
            fs.renameSync(oldPath, newPath);
            return { success: true };
        } catch (error) {
            console.error('[Electron] fs:rename failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:delete', async (event, targetPath) => {
        try {
            // Use shell.trashItem to move to trash instead of permanent delete
            await shell.trashItem(targetPath);
            return { success: true };
        } catch (error) {
            console.error('[Electron] fs:delete failed', error);
            return { success: false, error: error.message };
        }
    });

    // Simple File I/O for saving
    ipcMain.handle('fs:writeFile', async (event, { path: targetPath, content }) => {
        try {
            const parentDir = path.dirname(targetPath);
            if (!fs.existsSync(parentDir)) {
                fs.mkdirSync(parentDir, { recursive: true });
            }
            fs.writeFileSync(targetPath, content, 'utf-8');
            return { success: true };
        } catch (error) {
            console.error('[Electron] fs:writeFile failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:readFile', async (event, targetPath) => {
        try {
            const content = fs.readFileSync(targetPath, 'utf-8');
            return { success: true, content };
        } catch (error) {
            console.error('[Electron] fs:readFile failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:readDir', async (event, targetPath) => {
        try {
            const items = fs.readdirSync(targetPath, { withFileTypes: true });
            const files = items.map(item => ({
                name: item.name,
                path: path.join(targetPath, item.name),
                type: item.isDirectory() ? 'folder' : (item.name.split('.').pop() || 'file'),
                children: item.isDirectory() ? [] : undefined
            })).filter(item => !item.name.startsWith('.')); // Basic hidden file filter

            // Sort: folders first, then files
            files.sort((a, b) => {
                if (a.type === 'folder' && b.type !== 'folder') return -1;
                if (a.type !== 'folder' && b.type === 'folder') return 1;
                return a.name.localeCompare(b.name);
            });

            return { success: true, files };
        } catch (error) {
            console.error('[Electron] fs:readDir failed', error);
            return { success: false, error: error.message };
        }
    });


    ipcMain.handle('fs:copy', async (event, { src, dest }) => {
        try {
            fs.cpSync(src, dest, { recursive: true });
            return { success: true };
        } catch (error) {
            console.error('[Electron] fs:copy failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:move', async (event, { src, dest }) => {
        try {
            fs.renameSync(src, dest);
            return { success: true };
        } catch (error) {
            console.error('[Electron] fs:move failed', error);
            return { success: false, error: error.message };
        }
    });

    // Advanced Discovery Handlers
    ipcMain.handle('fs:find', async (event, { pattern, root }) => {
        const { spawn } = require('child_process');
        // Fallback to project root if root not provided
        const searchRoot = root || path.join(__dirname, '..', '..');
        console.log(`[Electron] fs:find '${pattern}' in '${searchRoot}'`);

        return new Promise((resolve) => {
            // Find files matching pattern (case-insensitive, ignoring .git)
            const findCmd = process.platform === 'win32' ? 'where /r . *' : 'find . -name "*"';
            // Better: use 'find' with some smart ignores or 'fd' if available
            // For now, let's use a simple recursive JS glob or similar if we want to be cross-platform,
            // but since we are on Mac, let's go with 'find'
            const find = spawn('find', ['.', '-name', `*${pattern}*`, '-not', '-path', '*/.*'], { cwd: searchRoot });

            let stdout = '';
            find.stdout.on('data', data => { stdout += data; });
            find.on('close', () => {
                const files = stdout.split('\n').filter(Boolean).map(f => f.replace(/^\.\//, ''));
                resolve({ success: true, files: files.slice(0, 50) }); // Limit results
            });
            find.on('error', err => resolve({ success: false, error: err.message }));
        });
    });

    ipcMain.handle('fs:viewOutline', async (event, filePath) => {
        const { spawn } = require('child_process');
        const scriptPath = path.join(__dirname, '..', '..', 'scripts', 'file_outline.py');
        console.log(`[Electron] fs:viewOutline for '${filePath}'`);

        return new Promise((resolve) => {
            const proc = spawn('python3', [scriptPath, filePath]);
            let stdout = '';
            proc.stdout.on('data', data => { stdout += data; });
            proc.on('close', () => resolve({ success: true, outline: stdout }));
            proc.on('error', err => resolve({ success: false, error: err.message }));
        });
    });

    ipcMain.handle('fs:grep', async (event, { query, root }) => {
        const { spawn } = require('child_process');
        const searchRoot = root || path.join(__dirname, '..', '..');
        console.log(`[Electron] fs:grep '${query}' in '${searchRoot}'`);

        return new Promise((resolve) => {
            // ripgrep is preferred but grep -r is more universal
            const grep = spawn('grep', ['-r', '-l', '--exclude-dir=.*', query, '.'], { cwd: searchRoot });

            let stdout = '';
            grep.stdout.on('data', data => { stdout += data; });
            grep.on('close', () => {
                const files = stdout.split('\n').filter(Boolean).map(f => f.replace(/^\.\//, ''));
                resolve({ success: true, files: files.slice(0, 50) });
            });
            grep.on('error', err => resolve({ success: false, error: err.message }));
        });
    });
}

app.on('ready', () => {
    console.log('[Electron] App ready, setting up handlers...');
    // Start backends
    startBackend('uv', ['run', 'api.py'], 'API');
    startBackend('uv', ['run', 'python', 'mcp_servers/server_rag.py'], 'RAG');

    setupTerminalHandlers();
    setupFSHandlers();
    createWindow();
});

app.on('window-all-closed', () => {
    // Explicitly quit the app when windows are closed to trigger backend cleanup
    app.quit();
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('will-quit', () => {
    console.log('[Electron] Shutting down backends and terminal sessions...');
    backendProcesses.forEach(proc => {
        if (proc && proc.pid) {
            try {
                // Kill process group (usually works if detached: true)
                process.kill(-proc.pid, 'SIGTERM');
            } catch (e) {
                try { proc.kill(); } catch (e2) { }
            }
        }
    });

    if (ptyProcess && ptyProcess.pid) {
        try {
            process.kill(-ptyProcess.pid, 'SIGTERM');
        } catch (e) {
            try { ptyProcess.kill(); } catch (e2) { }
        }
    }
});
