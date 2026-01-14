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
                if (mainWindow && !mainWindow.isDestroyed()) {
                    let str = data.toString('utf-8');
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
        // Todo: Implement resize via signal or sideline if needed.
        // For now, the python script hardcodes or inherits.
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
    if (ptyProcess) {
        ptyProcess.kill();
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('will-quit', () => {
    console.log('[Electron] Shutting down backends...');
    backendProcesses.forEach(proc => {
        if (proc) proc.kill();
    });
    if (ptyProcess) {
        try {
            ptyProcess.kill();
        } catch (e) { }
    }
});
