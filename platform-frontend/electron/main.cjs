const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const { spawn } = require('child_process');
const os = require('os');

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
function setupTerminalHandlers() {
    if (!pty) return;

    ipcMain.on('terminal:create', (event, options) => {
        if (ptyProcess) {
            console.log('[Electron] Terminal already exists, using existing session.');
            // event.reply('terminal:outgoing', '\r\nRestored session...\r\n');
            return;
        }

        const shell = process.env.SHELL || (os.platform() === 'win32' ? 'powershell.exe' : 'zsh');
        // Default CWD to project root
        const cwd = path.resolve(__dirname, '..', '..');

        try {
            ptyProcess = pty.spawn(shell, [], {
                name: 'xterm-256color',
                cols: 80,
                rows: 24,
                cwd: cwd,
                env: process.env
            });

            console.log(`[Electron] Pty process created: PID ${ptyProcess.pid}`);

            ptyProcess.onData((data) => {
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', data);
                }
            });

            ptyProcess.onExit(({ exitCode, signal }) => {
                console.log(`[Electron] Pty process exited with code ${exitCode} signal ${signal}`);
                ptyProcess = null;
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', '\r\n\n[Process terminated]\r\n');
                }
            });

        } catch (ex) {
            console.error('[Electron] Failed to spawn pty:', ex);
        }
    });

    ipcMain.on('terminal:incoming', (event, data) => {
        if (ptyProcess) {
            ptyProcess.write(data);
        }
    });

    ipcMain.on('terminal:resize', (event, { cols, rows }) => {
        if (ptyProcess) {
            try {
                ptyProcess.resize(cols, rows);
            } catch (err) {
                console.warn('[Electron] Failed to resize pty:', err);
            }
        }
    });
}

app.on('ready', () => {
    // Start backends
    startBackend('uv', ['run', 'api.py'], 'API');
    startBackend('uv', ['run', 'python', 'mcp_servers/server_rag.py'], 'RAG');

    setupTerminalHandlers();
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
