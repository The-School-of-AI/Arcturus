const { contextBridge, ipcRenderer } = require('electron');

// Preload script for browser WebContentsView pages
// Allows text selection capture and communication with main app

contextBridge.exposeInMainWorld('arcturusBridge', {
    // Get the currently selected text
    getSelection: () => {
        const selection = window.getSelection();
        return selection ? selection.toString() : '';
    },

    // Send selected text to main process
    sendSelection: (text) => {
        ipcRenderer.send('browser:selection', { text });
    }
});

// Auto-send selection on mouseup for "Add to Context" feature
document.addEventListener('mouseup', () => {
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : '';
    if (text && text.length > 0) {
        // Notify parent about selection (main process will forward to renderer)
        ipcRenderer.send('browser:selection', { text });
    }
});
