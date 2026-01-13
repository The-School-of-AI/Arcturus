const { app, BrowserWindow } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.cjs'),
            webviewTag: true,
        },
        backgroundColor: '#000000',
    });

    const startUrl = isDev
        ? 'http://localhost:5555'
        : `file://${path.join(__dirname, '../dist/index.html')}`;

    mainWindow.loadURL(startUrl);

    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startBackend() {
    console.log('Starting backend...');
    // We go up one level to find the root where uv should be run
    const rootPath = path.join(__dirname, '..', '..');

    // Starting server_rag.py via uv
    pythonProcess = spawn('uv', ['run', 'python', 'mcp_servers/server_rag.py'], {
        cwd: rootPath,
        shell: true
    });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`Backend stdout: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`Backend stderr: ${data}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Backend process exited with code ${code}`);
    });
}

app.on('ready', () => {
    startBackend();
    createWindow();
});

app.on('window-all-closed', () => {
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
    if (pythonProcess) {
        pythonProcess.kill();
    }
});
