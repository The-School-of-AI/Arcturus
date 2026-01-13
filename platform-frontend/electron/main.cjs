const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const isDev = !app.isPackaged;
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

    ipcMain.on('terminal:create', (event, options) => {
        if (ptyProcess && typeof ptyProcess.exitCode !== 'number') {
            console.log('[Electron] Terminal session already active.');
            return;
        }

        const shell = process.env.SHELL || (os.platform() === 'win32' ? 'powershell.exe' : '/bin/zsh');

        // Ensure CWD exists
        let cwd = options.cwd || path.resolve(__dirname, '..', '..');
        const fs = require('fs');
        if (!fs.existsSync(cwd)) {
            console.warn(`[Electron] Requested CWD '${cwd}' does not exist. Falling back to default.`);
            cwd = path.resolve(__dirname, '..', '..');
        }

        console.log(`[Electron] Spawning terminal (Compatibility Mode): Shell='${shell}', CWD='${cwd}'`);

        try {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:outgoing', '\r\n\x1b[33m[System] Terminal running in Compatibility Mode.\r\n(Native PTY module failed to build on this system).\r\nBasic commands (git, npm, python) work. Interactive TTY apps (vim, nano) are disabled.\x1b[0m\r\n\r\n$ ');
            }

            // Spawn standard process with pipes
            ptyProcess = spawn(shell, ['-i'], {
                cwd: cwd,
                env: process.env,
                stdio: ['pipe', 'pipe', 'pipe']
            });

            console.log(`[Electron] Process created: PID ${ptyProcess.pid}`);

            // Handle Output
            ptyProcess.stdout.on('data', (data) => {
                if (mainWindow && !mainWindow.isDestroyed()) {
                    let str = data.toString('utf-8');
                    // Normalize newlines for xterm
                    str = str.replace(/\n/g, '\r\n');
                    mainWindow.webContents.send('terminal:outgoing', str);
                }
            });

            ptyProcess.stderr.on('data', (data) => {
                if (mainWindow && !mainWindow.isDestroyed()) {
                    let str = data.toString('utf-8');
                    str = str.replace(/\n/g, '\r\n');
                    mainWindow.webContents.send('terminal:outgoing', str);
                }
            });

            ptyProcess.on('close', (code) => {
                console.log(`[Electron] Process exited with code ${code}`);
                ptyProcess = null;
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', `\r\n\n[Process terminated with code ${code}]\r\n`);
                }
            });

        } catch (ex) {
            console.error('[Electron] Failed to spawn shell:', ex);
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:outgoing', `\r\n\x1b[31mError spawning terminal: ${ex.message}\x1b[0m\r\n`);
            }
        }
    });

    ipcMain.on('terminal:incoming', (event, data) => {
        if (ptyProcess && ptyProcess.stdin) {
            try {
                // Compatibility Mode: Manually echo input back to xterm
                // because non-PTY shells often disable echo on pipes.
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', data);
                }
                ptyProcess.stdin.write(data);
            } catch (err) {
                console.error("Write error", err);
            }
        }
    });

    ipcMain.on('terminal:resize', (event, { cols, rows }) => {
        // Simple spawn cannot be resized, ignore.
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
