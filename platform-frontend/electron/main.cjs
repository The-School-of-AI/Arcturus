const { app, BrowserWindow, WebContentsView, ipcMain, dialog, shell, Menu } = require('electron');
// Set App Name early for MacOS Dock/Menu
app.name = "Arcturus";
app.setName("Arcturus");
process.title = "Arcturus";

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
    console.error("[Arcturus] Failed to load node-pty. Terminal features will be disabled.", e);
}

let mainWindow;
let backendProcesses = [];
let backgroundProcesses = new Map(); // pid -> { process, stdout: '', stderr: '', startTime: number }

const iconPath = isDev
    ? path.join(__dirname, '../public/icon.png')
    : path.join(__dirname, '../dist/icon.png');

// Terminal state
let ptyProcess = null;
let activeTerminalCwd = null;
let activeTerminalBuffer = ""; // Store terminal history

// Browser View state (WebContentsView-based browser)
let browserViews = new Map(); // tabId -> { view: WebContentsView, url: string, title: string }
let activeBrowserTabId = null;
let browserViewBounds = { x: 0, y: 0, width: 800, height: 600 };
let browserTabCounter = 0;

function createWindow() {

    // Set Dock Icon for macOS
    if (process.platform === 'darwin') {
        app.dock.setIcon(iconPath);
    }

    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        icon: iconPath,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.cjs'),
            webviewTag: true,
        },
        titleBarStyle: 'hiddenInset',
        trafficLightPosition: { x: 12, y: 12 }, // Optional: adjust slightly if needed
        backgroundColor: '#0b0f1a', // Matching your theme
        title: "Arcturus"
    });

    if (process.platform === 'darwin') {
        app.setAboutPanelOptions({
            applicationName: "Arcturus",
            applicationVersion: "0.0.1",
            copyright: "Copyright © 2026 Arcturus",
            iconPath: iconPath
        });
    }

    const startUrl = isDev
        ? 'http://localhost:5173'
        : `file://${path.join(__dirname, '../dist/index.html')}`;

    console.log(`[Arcturus] Loading URL: ${startUrl}`);
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
    console.log(`[Arcturus] Spawning Backend [${name}]: ${command} ${args.join(' ')}`);
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
        console.log(`[Arcturus] Backend [${name}] exited with code ${code}`);
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
            console.log(`[Arcturus] Ending previous terminal session at '${activeTerminalCwd}'`);
            try {
                ptyProcess.kill();
            } catch (e) { }
            ptyProcess = null;
        }

        activeTerminalCwd = cwd;
        const bridgePath = path.join(__dirname, 'pty_bridge.py');
        console.log(`[Arcturus] Spawning Python PTY Bridge: ${bridgePath} in ${cwd}`);

        try {
            // Spawn python script which handles the PTY fork
            ptyProcess = spawn('python3', ['-u', bridgePath], {
                cwd: cwd,
                detached: true,
                env: { ...process.env, TERM: 'xterm-256color', COLUMNS: '120', LINES: '30' },
                stdio: ['pipe', 'pipe', 'pipe']
            });

            console.log(`[Arcturus] Bridge process created: PID ${ptyProcess.pid}`);

            ptyProcess.on('error', (err) => {
                console.error(`[Arcturus] Bridge failed to start or encountered an error:`, err);
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
                console.error(`[Arcturus-PTY-Stderr] ${str}`);
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('terminal:outgoing', `\x1b[33m${str}\x1b[0m`);
                }
            });

            ptyProcess.on('close', (code, signal) => {
                console.log(`[Arcturus] Bridge exited with code ${code}, signal ${signal}`);
                ptyProcess = null;
            });

        } catch (ex) {
            console.error('[Arcturus] Failed to spawn bridge:', ex);
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('terminal:outgoing', `\r\n\x1b[31mError spawning terminal bridge: ${ex.message}\x1b[0m\r\n`);
            }
        }
    });

    ipcMain.on('terminal:incoming', (event, data) => {
        if (ptyProcess && ptyProcess.stdin) {
            try {
                // console.log(`[Arcturus-Input] Writing ${data.length} bytes to PTY`); // Debug logs
                ptyProcess.stdin.write(data);
            } catch (err) {
                console.error("Write error", err);
            }
        } else {
            console.warn("[Arcturus] terminal:incoming received but ptyProcess is null or stdin closed.");
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
        console.log('[Arcturus] terminal:read invoked from Agent');
        // Return the last 10KB of history to avoid overwhelming LLM
        return { success: true, content: activeTerminalBuffer.slice(-10000) || "[No output captured yet]" };
    });
}

// --- File System Handlers ---
function setupFSHandlers() {
    // Open Directory Dialog
    ipcMain.handle('dialog:openDirectory', async () => {
        console.log('[Arcturus] dialog:openDirectory invoked');
        const { dialog } = require('electron');
        try {
            const result = await dialog.showOpenDialog(mainWindow, {
                properties: ['openDirectory', 'createDirectory']
            });
            console.log('[Arcturus] Dialog result:', result);
            if (result.canceled) return null;
            return result.filePaths[0];
        } catch (error) {
            console.error('[Arcturus] dialog:openDirectory error:', error);
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

    // Helper to validate and resolve CWD
    const validateCwd = (requestedCwd) => {
        const rootPath = path.resolve(__dirname, '..', '..'); // Project Root
        const targetCwd = requestedCwd ? path.resolve(requestedCwd) : rootPath;

        // Strict Security Check: Enforce CWD is within Project Root
        if (!targetCwd.startsWith(rootPath)) {
            console.warn(`[Arcturus] Security Block: Attempted CWD escape to ${targetCwd}`);
            return { valid: false, reason: "Access denied: Execution outside project root is prohibited." };
        }
        return { valid: true, path: targetCwd };
    };

    ipcMain.handle('shell:exec', async (event, { cmd, cwd }) => {
        const cwdValidation = validateCwd(cwd);
        if (!cwdValidation.valid) return { success: false, error: cwdValidation.reason };

        console.log(`[Arcturus] shell:exec '${cmd}' in '${cwdValidation.path}'`);
        const { exec } = require('child_process');
        return new Promise((resolve) => {
            exec(cmd, {
                cwd: cwdValidation.path,
                maxBuffer: 10 * 1024 * 1024,
                timeout: 60000
            }, (error, stdout, stderr) => {
                if (error) {
                    const isTimeout = error.killed || error.signal === 'SIGTERM';
                    resolve({
                        success: false,
                        error: isTimeout ? "Command timed out after 60s" : error.message,
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

    // NEW: Background Spawn with PID tracking
    ipcMain.handle('shell:spawn', async (event, { cmd, cwd }) => {
        const cwdValidation = validateCwd(cwd);
        if (!cwdValidation.valid) return { success: false, error: cwdValidation.reason };

        const { spawn } = require('child_process');
        console.log(`[Arcturus] shell:spawn '${cmd}' in '${cwdValidation.path}'`);

        try {
            const [command, ...args] = cmd.split(' '); // Simple split, might need better parsing for quoted args
            // Better to use shell: true to support pipes/redirections if cmd is complex, 
            // but for safety usually single command preferred. 
            // However, run_command might send complex strings. 
            // Let's use shell: true for consistency with exec, but be careful.

            const proc = spawn(cmd, [], {
                cwd: cwdValidation.path,
                shell: true,
                detached: false
            });

            const pid = proc.pid;
            const procState = {
                pid,
                stdout: '',
                stderr: '',
                status: 'running',
                startTime: Date.now(),
                exitCode: null
            };

            // Buffer handling (Circular-ish limit implemented simply)
            const appendLog = (type, data) => {
                const str = data.toString();
                if (procState[type].length > 50000) procState[type] = procState[type].slice(-40000);
                procState[type] += str;
            };

            proc.stdout.on('data', d => appendLog('stdout', d));
            proc.stderr.on('data', d => appendLog('stderr', d));

            proc.on('close', (code) => {
                procState.status = 'done';
                procState.exitCode = code;
                console.log(`[Arcturus] BG Process ${pid} finished with ${code}`);
                // Auto-cleanup after 1 hour if not checked? 
                // For now, keep it in memory until app restart is fine for modest usage.
            });

            proc.on('error', (err) => {
                procState.status = 'error';
                procState.stderr += `\nSystem Error: ${err.message}`;
            });

            backgroundProcesses.set(pid.toString(), procState);
            return { success: true, pid: pid.toString(), status: 'running' };

        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('shell:status', async (event, pid) => {
        const proc = backgroundProcesses.get(pid?.toString());
        if (!proc) return { success: false, error: "Process not found or expired" };

        return {
            success: true,
            status: proc.status,
            exitCode: proc.exitCode,
            stdout: proc.stdout,
            stderr: proc.stderr
        };
    });

    ipcMain.handle('shell:kill', async (event, pid) => {
        const procData = backgroundProcesses.get(pid?.toString());
        if (!procData) return { success: false, error: "Process not found" };

        try {
            process.kill(parseInt(pid), 'SIGTERM');
            return { success: true };
        } catch (e) {
            return { success: false, error: e.message };
        }
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
            console.error('[Arcturus] fs:create failed', error);
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
            console.error('[Arcturus] fs:rename failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:delete', async (event, targetPath) => {
        try {
            // Use shell.trashItem to move to trash instead of permanent delete
            await shell.trashItem(targetPath);
            return { success: true };
        } catch (error) {
            console.error('[Arcturus] fs:delete failed', error);
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
            console.error('[Arcturus] fs:writeFile failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:readFile', async (event, targetPath) => {
        try {
            const content = fs.readFileSync(targetPath, 'utf-8');
            return { success: true, content };
        } catch (error) {
            console.error('[Arcturus] fs:readFile failed', error);
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
            console.error('[Arcturus] fs:readDir failed', error);
            return { success: false, error: error.message };
        }
    });


    ipcMain.handle('fs:copy', async (event, { src, dest }) => {
        try {
            fs.cpSync(src, dest, { recursive: true });
            return { success: true };
        } catch (error) {
            console.error('[Arcturus] fs:copy failed', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:move', async (event, { src, dest }) => {
        try {
            fs.renameSync(src, dest);
            return { success: true };
        } catch (error) {
            console.error('[Arcturus] fs:move failed', error);
            return { success: false, error: error.message };
        }
    });

    // Advanced Discovery Handlers
    ipcMain.handle('fs:find', async (event, { pattern, root }) => {
        const { spawn } = require('child_process');
        // Fallback to project root if root not provided
        const searchRoot = root || path.join(__dirname, '..', '..');
        console.log(`[Arcturus] fs:find '${pattern}' in '${searchRoot}'`);

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
        console.log(`[Arcturus] fs:viewOutline for '${filePath}'`);

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
        console.log(`[Arcturus] fs:grep '${query}' in '${searchRoot}'`);

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

function setupDialogHandlers() {
    ipcMain.handle('dialog:confirm', async (event, { message, title, type = 'question' }) => {
        const { nativeImage } = require('electron');
        const icon = nativeImage.createFromPath(iconPath);

        const result = await dialog.showMessageBox(mainWindow, {
            type,
            title: title || 'Confirmation',
            message: message,
            buttons: ['Cancel', 'OK'],
            defaultId: 1,
            cancelId: 0,
            icon: icon
        });

        return result.response === 1;
    });

    ipcMain.handle('dialog:alert', async (event, { message, title, type = 'info' }) => {
        const { nativeImage } = require('electron');
        const icon = nativeImage.createFromPath(iconPath);

        await dialog.showMessageBox(mainWindow, {
            type,
            title: title || 'Alert',
            message: message,
            buttons: ['OK'],
            icon: icon
        });
    });

    ipcMain.on('dialog:confirmSync', (event, { message, title, type = 'question' }) => {
        const { nativeImage } = require('electron');
        const icon = nativeImage.createFromPath(iconPath);

        const response = dialog.showMessageBoxSync(mainWindow, {
            type,
            title: title || 'Confirmation',
            message: message,
            buttons: ['Cancel', 'OK'],
            defaultId: 1,
            cancelId: 0,
            icon: icon
        });

        event.returnValue = response === 1;
    });
}

// --- Browser View Handlers (WebContentsView-based browser) ---
function setupBrowserHandlers() {
    const preloadBrowserPath = path.join(__dirname, 'preload-browser.cjs');

    // Helper to update view bounds
    const updateActiveBrowserViewBounds = () => {
        if (activeBrowserTabId && browserViews.has(activeBrowserTabId)) {
            const { view } = browserViews.get(activeBrowserTabId);
            view.setBounds(browserViewBounds);
        }
    };

    // Create a new browser tab
    ipcMain.handle('browser:create-tab', async (event, url) => {
        const tabId = `tab-${++browserTabCounter}`;
        console.log(`[Arcturus] Creating browser tab ${tabId} with URL: ${url}`);

        const view = new WebContentsView({
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                sandbox: true,
                preload: preloadBrowserPath,
                // Shared session for all browser tabs
                partition: 'persist:arcturus-browser'
            }
        });

        // Set initial bounds
        view.setBounds(browserViewBounds);

        // Store view data
        browserViews.set(tabId, {
            view,
            url: url || 'about:blank',
            title: 'New Tab',
            loading: false,
            canGoBack: false,
            canGoForward: false
        });

        // Wire up WebContents events
        const wc = view.webContents;

        wc.on('did-start-loading', () => {
            const data = browserViews.get(tabId);
            if (data) data.loading = true;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('browser:loading-changed', { tabId, loading: true });
            }
        });

        wc.on('did-stop-loading', () => {
            const data = browserViews.get(tabId);
            if (data) data.loading = false;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('browser:loading-changed', { tabId, loading: false });
            }
        });

        wc.on('did-navigate', (e, navUrl) => {
            const data = browserViews.get(tabId);
            if (data) {
                data.url = navUrl;
                data.canGoBack = wc.canGoBack();
                data.canGoForward = wc.canGoForward();
            }
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('browser:did-navigate', {
                    tabId,
                    url: navUrl,
                    canGoBack: wc.canGoBack(),
                    canGoForward: wc.canGoForward()
                });
            }
        });

        wc.on('did-navigate-in-page', (e, navUrl) => {
            const data = browserViews.get(tabId);
            if (data) {
                data.url = navUrl;
                data.canGoBack = wc.canGoBack();
                data.canGoForward = wc.canGoForward();
            }
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('browser:did-navigate', {
                    tabId,
                    url: navUrl,
                    canGoBack: wc.canGoBack(),
                    canGoForward: wc.canGoForward()
                });
            }
        });

        wc.on('page-title-updated', (e, title) => {
            const data = browserViews.get(tabId);
            if (data) data.title = title;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('browser:title-updated', { tabId, title });
            }
        });

        wc.on('page-favicon-updated', (e, favicons) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('browser:favicon-updated', { tabId, favicon: favicons[0] || null });
            }
        });

        // Handle new window requests (popups, OAuth, etc.)
        wc.setWindowOpenHandler(({ url: popupUrl }) => {
            // Open OAuth and similar in the same tab
            wc.loadURL(popupUrl);
            return { action: 'deny' };
        });

        // Load URL
        if (url) {
            wc.loadURL(url);
        }

        // Add to window and activate
        mainWindow.contentView.addChildView(view);

        // Hide any previous active tab
        if (activeBrowserTabId && browserViews.has(activeBrowserTabId)) {
            const prevView = browserViews.get(activeBrowserTabId).view;
            mainWindow.contentView.removeChildView(prevView);
        }

        activeBrowserTabId = tabId;
        updateActiveBrowserViewBounds();

        return { tabId, url: url || 'about:blank', title: 'New Tab' };
    });

    // Close a browser tab
    ipcMain.handle('browser:close-tab', async (event, tabId) => {
        console.log(`[Arcturus] Closing browser tab ${tabId}`);
        if (!browserViews.has(tabId)) return { success: false, error: 'Tab not found' };

        const { view } = browserViews.get(tabId);

        // Remove from window
        try {
            mainWindow.contentView.removeChildView(view);
        } catch (e) { }

        // Destroy webContents
        view.webContents.close();
        browserViews.delete(tabId);

        // Activate another tab if this was the active one
        if (activeBrowserTabId === tabId) {
            activeBrowserTabId = null;
            const remaining = Array.from(browserViews.keys());
            if (remaining.length > 0) {
                const newActiveId = remaining[remaining.length - 1];
                activeBrowserTabId = newActiveId;
                const { view: newView } = browserViews.get(newActiveId);
                mainWindow.contentView.addChildView(newView);
                updateActiveBrowserViewBounds();
            }
        }

        return { success: true, activeTabId: activeBrowserTabId };
    });

    // Switch to a different tab
    ipcMain.handle('browser:switch-tab', async (event, tabId) => {
        console.log(`[Arcturus] Switching to browser tab ${tabId}`);
        if (!browserViews.has(tabId)) return { success: false, error: 'Tab not found' };

        // Hide current
        if (activeBrowserTabId && browserViews.has(activeBrowserTabId)) {
            const prevView = browserViews.get(activeBrowserTabId).view;
            try {
                mainWindow.contentView.removeChildView(prevView);
            } catch (e) { }
        }

        // Show new
        activeBrowserTabId = tabId;
        const { view, url, title, canGoBack, canGoForward } = browserViews.get(tabId);
        mainWindow.contentView.addChildView(view);
        updateActiveBrowserViewBounds();

        return { success: true, tabId, url, title, canGoBack, canGoForward };
    });

    // Navigate to a URL
    ipcMain.handle('browser:navigate', async (event, { tabId, url }) => {
        console.log(`[Arcturus] Navigating tab ${tabId} to ${url}`);
        if (!browserViews.has(tabId)) return { success: false, error: 'Tab not found' };

        const { view } = browserViews.get(tabId);
        view.webContents.loadURL(url);
        return { success: true };
    });

    // Go back
    ipcMain.handle('browser:go-back', async (event, tabId) => {
        if (!browserViews.has(tabId)) return { success: false };
        const { view } = browserViews.get(tabId);
        if (view.webContents.canGoBack()) {
            view.webContents.goBack();
            return { success: true };
        }
        return { success: false };
    });

    // Go forward
    ipcMain.handle('browser:go-forward', async (event, tabId) => {
        if (!browserViews.has(tabId)) return { success: false };
        const { view } = browserViews.get(tabId);
        if (view.webContents.canGoForward()) {
            view.webContents.goForward();
            return { success: true };
        }
        return { success: false };
    });

    // Reload
    ipcMain.handle('browser:reload', async (event, tabId) => {
        if (!browserViews.has(tabId)) return { success: false };
        const { view } = browserViews.get(tabId);
        view.webContents.reload();
        return { success: true };
    });

    // Set browser view bounds (called from renderer when container resizes)
    ipcMain.on('browser:set-bounds', (event, bounds) => {
        browserViewBounds = bounds;
        updateActiveBrowserViewBounds();
    });

    // Hide all browser views (when switching away from News tab)
    ipcMain.on('browser:hide-all', () => {
        browserViews.forEach(({ view }) => {
            try {
                mainWindow.contentView.removeChildView(view);
            } catch (e) { }
        });
    });

    // Show the active browser view (when returning to News tab)
    ipcMain.on('browser:show-active', () => {
        if (activeBrowserTabId && browserViews.has(activeBrowserTabId)) {
            const { view } = browserViews.get(activeBrowserTabId);
            try {
                mainWindow.contentView.addChildView(view);
                updateActiveBrowserViewBounds();
            } catch (e) { }
        }
    });

    // Get all tabs info
    ipcMain.handle('browser:get-tabs', async () => {
        const tabs = [];
        browserViews.forEach((data, tabId) => {
            tabs.push({
                tabId,
                url: data.url,
                title: data.title,
                loading: data.loading,
                active: tabId === activeBrowserTabId
            });
        });
        return tabs;
    });

    // Get selected text from active tab
    ipcMain.handle('browser:get-selection', async (event, tabId) => {
        if (!browserViews.has(tabId)) return { success: false, text: '' };
        const { view } = browserViews.get(tabId);
        try {
            const text = await view.webContents.executeJavaScript('window.getSelection().toString()');
            return { success: true, text: text || '' };
        } catch (e) {
            return { success: false, text: '' };
        }
    });

    // Set zoom level for a tab
    ipcMain.handle('browser:set-zoom', async (event, { tabId, zoomFactor }) => {
        if (!browserViews.has(tabId)) return { success: false };
        const { view } = browserViews.get(tabId);
        try {
            view.webContents.setZoomFactor(zoomFactor);
            return { success: true };
        } catch (e) {
            return { success: false };
        }
    });

    // Handle window resize - update all view bounds
    if (mainWindow) {
        mainWindow.on('resize', () => {
            updateActiveBrowserViewBounds();
        });

        // Hide browser views when DevTools is opened (so DevTools isn't covered)
        mainWindow.webContents.on('devtools-opened', () => {
            browserViews.forEach(({ view }) => {
                try {
                    mainWindow.contentView.removeChildView(view);
                } catch (e) { }
            });
        });

        // Show browser views when DevTools is closed
        mainWindow.webContents.on('devtools-closed', () => {
            if (activeBrowserTabId && browserViews.has(activeBrowserTabId)) {
                const { view } = browserViews.get(activeBrowserTabId);
                try {
                    mainWindow.contentView.addChildView(view);
                    updateActiveBrowserViewBounds();
                } catch (e) { }
            }
        });
    }
}

app.on('ready', () => {
    console.log('[Arcturus] App ready, setting up handlers...');

    // Set Menu for macOS to show "Arcturus" instead of "Electron"
    const template = [
        {
            label: "Arcturus",
            submenu: [
                { role: 'about' },
                { type: 'separator' },
                { role: 'services' },
                { type: 'separator' },
                { role: 'hide' },
                { role: 'hideOthers' },
                { role: 'unhide' },
                { type: 'separator' },
                { role: 'quit' }
            ]
        },
        {
            label: 'Edit',
            submenu: [
                { role: 'undo' },
                { role: 'redo' },
                { type: 'separator' },
                { role: 'cut' },
                { role: 'copy' },
                { role: 'paste' },
                { role: 'selectAll' }
            ]
        },
        {
            label: 'View',
            submenu: [
                { role: 'reload' },
                { role: 'forceReload' },
                { role: 'toggleDevTools' },
                { type: 'separator' },
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' },
                { type: 'separator' },
                { role: 'togglefullscreen' }
            ]
        },
        {
            role: 'window',
            submenu: [
                { role: 'minimize' },
                { role: 'zoom' },
                { role: 'close' }
            ]
        }
    ];
    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);

    // Start backends
    startBackend('uv', ['run', 'api.py'], 'API');
    startBackend('uv', ['run', 'python', 'mcp_servers/server_rag.py'], 'RAG');

    setupTerminalHandlers();
    setupFSHandlers();
    setupDialogHandlers();
    createWindow();
    setupBrowserHandlers(); // Must be after createWindow so mainWindow is available
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

const treeKill = require('tree-kill');

app.on('will-quit', () => {
    console.log('[Arcturus] Shutting down backends and terminal sessions...');

    // Kill backend services
    backendProcesses.forEach(proc => {
        if (proc && proc.pid) {
            console.log(`[Arcturus] Killing backend process ${proc.pid}`);
            treeKill(proc.pid, 'SIGKILL', (err) => {
                if (err) console.error(`[Arcturus] Failed to kill process ${proc.pid}`, err);
            });
        }
    });

    // Kill background shell tasks
    backgroundProcesses.forEach((proc, pidKey) => {
        if (proc && proc.pid && proc.status === 'running') {
            console.log(`[Arcturus] Killing background task ${proc.pid}`);
            treeKill(proc.pid, 'SIGKILL');
        }
    });

    // Kill PTY
    if (ptyProcess && ptyProcess.pid) {
        console.log(`[Arcturus] Killing PTY ${ptyProcess.pid}`);
        try {
            // ptyProcess from node-pty might need standard kill or tree-kill
            // tree-kill is safer
            treeKill(ptyProcess.pid, 'SIGKILL');
        } catch (e) {
            console.error('[Arcturus] Failed to kill PTY', e);
        }
    }
});
