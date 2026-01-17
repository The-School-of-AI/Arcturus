const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld(
    "electronAPI", {
    invoke: (channel, ...args) => {
        let validChannels = [
            "dialog:openDirectory", "dialog:confirm", "dialog:alert",
            "fs:create", "fs:rename", "fs:delete", "fs:readFile", "fs:writeFile",
            "fs:copy", "fs:move", "fs:readDir", "fs:find", "fs:grep", "fs:viewOutline",
            "fs:isGitignored", "fs:clearGitignoreCache",
            "shell:exec", "shell:spawn", "shell:status", "shell:kill",
            "terminal:read",
            // Browser APIs
            "browser:create-tab", "browser:close-tab", "browser:switch-tab",
            "browser:navigate", "browser:go-back", "browser:go-forward",
            "browser:reload", "browser:get-tabs", "browser:get-selection",
            "browser:set-zoom"
        ];
        if (validChannels.includes(channel)) {
            return ipcRenderer.invoke(channel, ...args);
        }
    },
    send: (channel, data) => {
        // whitelist channels
        let validChannels = [
            "toMain", "terminal:create", "terminal:incoming", "terminal:resize",
            "shell:reveal", "shell:openExternal",
            // Browser APIs
            "browser:set-bounds", "browser:hide-all", "browser:show-active"
        ];
        if (validChannels.includes(channel)) {
            console.log(`[Preload] Sending to main: ${channel}`);
            ipcRenderer.send(channel, data);
        } else {
            console.warn(`[Preload] Blocked channel: ${channel}`);
        }
    },
    receive: (channel, func) => {
        let validChannels = [
            "fromMain", "terminal:outgoing",
            // Browser events
            "browser:did-navigate", "browser:title-updated",
            "browser:loading-changed", "browser:favicon-updated",
            "browser:selection"
        ];
        if (validChannels.includes(channel)) {
            // Deliberately strip event as it includes `sender` 
            ipcRenderer.on(channel, (event, ...args) => func(...args));
        }
    },
    // Remove listener (for cleanup)
    removeListener: (channel, func) => {
        ipcRenderer.removeListener(channel, func);
    },
    confirm: (message) => {
        return ipcRenderer.sendSync('dialog:confirmSync', { message });
    }
}
);
