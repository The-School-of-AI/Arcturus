export interface ElectronAPI {
    send: (channel: string, data: any) => void;
    receive: (channel: string, func: (...args: any[]) => void) => void;
    invoke: (channel: string, ...args: any[]) => Promise<any>;
    removeListener: (channel: string, func: (...args: any[]) => void) => void;
}

declare global {
    interface Window {
        electronAPI: ElectronAPI;
    }
}
