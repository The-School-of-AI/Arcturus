import React, { useEffect, useRef } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';
import { Terminal as TerminalIcon, Plus, Maximize2, X, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/components/theme';
import { useAppStore } from '@/store'; // Import store

export const TerminalPanel: React.FC = () => {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<Terminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);
    const { theme } = useTheme();
    const { explorerRootPath } = useAppStore(); // Get current folder

    useEffect(() => {
        if (!terminalRef.current) return;

        let isDisposed = false;
        let resizeObserver: ResizeObserver | null = null;

        // Initialize xterm
        const term = new Terminal({
            cursorBlink: true,
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            theme: theme === 'dark' ? {
                background: '#18181b', // Matches container bg
                foreground: '#d4d4d8',
                cursor: '#ffffff',
                selectionBackground: '#264f78',
            } : {
                background: '#ffffff',
                foreground: '#000000',
                cursor: '#000000',
                selectionBackground: '#add6ff',
            },
            allowProposedApi: true,
        });

        const fitAddon = new FitAddon();
        const webLinksAddon = new WebLinksAddon();

        term.loadAddon(fitAddon);
        term.loadAddon(webLinksAddon);

        // DELAYED MOUNT: Wait for container to be ready
        const mountTimeout = setTimeout(() => {
            if (isDisposed || !terminalRef.current) return;

            try {
                term.open(terminalRef.current);
                xtermRef.current = term;
                fitAddonRef.current = fitAddon;

                // Initial fit if possible
                if (terminalRef.current.clientWidth > 0 && terminalRef.current.clientHeight > 0) {
                    fitAddon.fit();
                }

                // Focus terminal
                term.focus();

                // Setup ResizeObserver
                resizeObserver = new ResizeObserver(() => {
                    if (isDisposed || !terminalRef.current || !xtermRef.current) return;
                    if (terminalRef.current.clientWidth === 0 || terminalRef.current.clientHeight === 0) return;

                    try {
                        fitAddon.fit();
                        if (window.electronAPI) {
                            const dims = { cols: term.cols, rows: term.rows };
                            window.electronAPI.send('terminal:resize', dims);
                        }
                    } catch (e) {
                        // Ignore resize errors
                    }
                });
                resizeObserver.observe(terminalRef.current);

                // Initial session create
                if (window.electronAPI) {
                    console.log("[Terminal] Creating initial session with cwd:", explorerRootPath);
                    window.electronAPI.send('terminal:create', { cwd: explorerRootPath });
                }
            } catch (e) {
                console.error("[Terminal] Fail to open xterm:", e);
            }
        }, 500); // 500ms delay to ensure layout is settled

        // IPC: Incoming data (user typing)
        term.onData(data => {
            if (window.electronAPI) {
                window.electronAPI.send('terminal:incoming', data);
            }
        });

        // IPC: Outgoing data (pty output)
        if (window.electronAPI) {
            const handleOutgoing = (data: string) => {
                if (!isDisposed && xtermRef.current) {
                    term.write(data);
                }
            };
            window.electronAPI.receive('terminal:outgoing', handleOutgoing);
        }

        return () => {
            isDisposed = true;
            clearTimeout(mountTimeout);
            if (resizeObserver) resizeObserver.disconnect();

            try {
                term.dispose();
            } catch (e) {
                // Ignore disposal errors
            }
            xtermRef.current = null;
            fitAddonRef.current = null;
        };
    }, []); // Run once on mount

    // Update theme dynamically
    useEffect(() => {
        if (xtermRef.current && xtermRef.current.element) {
            try {
                xtermRef.current.options.theme = theme === 'dark' ? {
                    background: '#18181b',
                    foreground: '#d4d4d8',
                    cursor: '#ffffff',
                    selectionBackground: '#264f78',
                } : {
                    background: '#ffffff',
                    foreground: '#000000',
                    cursor: '#000000',
                    selectionBackground: '#add6ff',
                };
            } catch (e) {
                console.warn("Failed to update terminal theme", e);
            }
        }
    }, [theme]);

    // Sync terminal when project changes
    useEffect(() => {
        if (window.electronAPI && explorerRootPath && xtermRef.current) {
            console.log("[Terminal] Project changed, requesting terminal update:", explorerRootPath);
            window.electronAPI.send('terminal:create', { cwd: explorerRootPath });
        }
    }, [explorerRootPath]);

    const handleRefresh = () => {
        if (window.electronAPI) {
            // Create terminal session
            // Pass the current explorer root path as the desired CWD
            console.log("Initial terminal creation request...", explorerRootPath);
            window.electronAPI.send('terminal:create', {
                cwd: explorerRootPath
            }); // Try simple re-create/re-connect
            xtermRef.current?.write('\r\n\x1b[2m[Refreshing terminal connection...]\x1b[0m\r\n');
        }
    };

    return (
        <div className={cn("h-full flex flex-col border-t transition-colors", theme === 'dark' ? "bg-background border-border/50" : "bg-white border-border")}>
            {/* Terminal Header */}
            <div className={cn("h-9 min-h-[36px] flex items-center justify-between px-4 border-b shrink-0", theme === 'dark' ? "border-[#27272a] bg-[#18181b]" : "border-border bg-gray-50")}>
                <div className="flex items-center gap-4">
                    <div className={cn("flex items-center gap-2 text-xs font-medium cursor-pointer transition-colors border-b-2 border-transparent", theme === 'dark' ? "text-[#d4d4d8] hover:text-white border-white" : "text-gray-700 hover:text-black border-black")}>
                        <TerminalIcon className="w-3.5 h-3.5" />
                        <span>TERMINAL</span>
                    </div>
                    <div className={cn("flex items-center gap-2 text-xs font-medium cursor-pointer transition-colors", theme === 'dark' ? "text-[#71717a] hover:text-[#d4d4d8]" : "text-gray-400 hover:text-gray-600")}>
                        <span>OUTPUT</span>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <button
                        onClick={handleRefresh}
                        className={cn("p-1 rounded-md transition-colors", theme === 'dark' ? "hover:bg-[#27272a] text-[#a1a1aa] hover:text-white" : "hover:bg-gray-200 text-gray-500 hover:text-black")}
                        title="Reconnect"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                    <button className={cn("p-1 rounded-md transition-colors", theme === 'dark' ? "hover:bg-[#27272a] text-[#a1a1aa] hover:text-white" : "hover:bg-gray-200 text-gray-500 hover:text-black")}>
                        <Plus className="w-3.5 h-3.5" />
                    </button>
                    <button className={cn("p-1 rounded-md transition-colors", theme === 'dark' ? "hover:bg-[#27272a] text-[#a1a1aa] hover:text-white" : "hover:bg-gray-200 text-gray-500 hover:text-black")}>
                        <Maximize2 className="w-3.5 h-3.5" />
                    </button>
                    <button className={cn("p-1 rounded-md transition-colors", theme === 'dark' ? "hover:bg-[#27272a] text-[#a1a1aa] hover:text-white" : "hover:bg-gray-200 text-gray-500 hover:text-black")}>
                        <X className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* Terminal Body (xterm container) */}
            <div className="flex-1 overflow-hidden relative" style={{ padding: '8px 0 0 12px' }}>
                <div ref={terminalRef} className="h-full w-full" />
            </div>
        </div>
    );
};
