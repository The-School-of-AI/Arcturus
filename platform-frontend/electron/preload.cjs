const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld(
    "electronAPI", {
    invoke: (channel, ...args) => {
        let validChannels = ["dialog:openDirectory", "fs:create", "fs:rename", "fs:delete", "fs:readFile", "fs:writeFile", "fs:copy", "fs:move", "fs:readDir"];
        if (validChannels.includes(channel)) {
            return ipcRenderer.invoke(channel, ...args);
        }
    },
    send: (channel, data) => {
        // whitelist channels
        let validChannels = ["toMain", "terminal:create", "terminal:incoming", "terminal:resize", "shell:reveal", "shell:openExternal"];
        if (validChannels.includes(channel)) {
            console.log(`[Preload] Sending to main: ${channel}`);
            ipcRenderer.send(channel, data);
        } else {
            console.warn(`[Preload] Blocked channel: ${channel}`);
        }
    },
    receive: (channel, func) => {
        let validChannels = ["fromMain", "terminal:outgoing"];
        if (validChannels.includes(channel)) {
            // Deliberately strip event as it includes `sender` 
            ipcRenderer.on(channel, (event, ...args) => func(...args));
        }
    }
}
);
