import React, { useEffect, useRef } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';
import { Terminal as TerminalIcon, Plus, Maximize2, X, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/components/theme';
import { useAppStore } from '@/store';

export const TerminalPanel: React.FC = () => {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<Terminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);
    const { theme } = useTheme();
    const themeRef = useRef(theme);
    const { explorerRootPath } = useAppStore();

    // Keep themeRef in sync
    useEffect(() => {
        themeRef.current = theme;
        if (xtermRef.current) {
            xtermRef.current.options.theme = {
                background: '#00000000',
                foreground: theme === 'dark' ? '#d4d4d8' : '#000000',
                cursor: theme === 'dark' ? '#ffffff' : '#000000',
                selectionBackground: theme === 'dark' ? '#264f78' : '#add6ff',
            };
        }
    }, [theme]);

    useEffect(() => {
        if (!terminalRef.current) return;

        let isDisposed = false;
        let resizeObserver: ResizeObserver | null = null;

        // Create terminal immediately
        const term = new Terminal({
            cursorBlink: true,
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            allowProposedApi: true,
            allowTransparency: true,
            theme: {
                background: '#00000000',
                foreground: themeRef.current === 'dark' ? '#d4d4d8' : '#000000',
                cursor: themeRef.current === 'dark' ? '#ffffff' : '#000000',
                selectionBackground: themeRef.current === 'dark' ? '#264f78' : '#add6ff',
            }
        });

        // Assign refs IMMEDIATELY so other effects can operate on it
        xtermRef.current = term;

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        fitAddonRef.current = fitAddon;

        term.loadAddon(new WebLinksAddon());

        // Mount to DOM with slight delay to ensure container layout
        const mountTimeout = setTimeout(() => {
            if (isDisposed || !terminalRef.current) return;
            try {
                // Ensure theme is fresh before open (in case it changed during timeout)
                term.options.theme = {
                    background: '#00000000',
                    foreground: themeRef.current === 'dark' ? '#d4d4d8' : '#000000',
                    cursor: themeRef.current === 'dark' ? '#ffffff' : '#000000',
                    selectionBackground: themeRef.current === 'dark' ? '#264f78' : '#add6ff',
                };

                term.open(terminalRef.current);
                fitAddon.fit();
                term.focus();

                resizeObserver = new ResizeObserver(() => {
                    if (!isDisposed && xtermRef.current) {
                        try { fitAddon.fit(); } catch (e) { /* ignore */ }
                    }
                });
                resizeObserver.observe(terminalRef.current);

                if (window.electronAPI) {
                    window.electronAPI.send('terminal:create', { cwd: explorerRootPath });
                }
            } catch (e) { console.error("Xterm open fail", e); }
        }, 100); // Reduced delay since we are safer now

        term.onData(data => window.electronAPI?.send('terminal:incoming', data));

        if (window.electronAPI) {
            window.electronAPI.receive('terminal:outgoing', (data: string) => {
                if (!isDisposed && xtermRef.current) term.write(data);
            });
        }

        return () => {
            isDisposed = true;
            clearTimeout(mountTimeout);
            if (resizeObserver) resizeObserver.disconnect();
            term.dispose();
            xtermRef.current = null;
        };
    }, []); // Run once on mount

    const handleRefresh = () => {
        window.electronAPI?.send('terminal:create', { cwd: explorerRootPath });
    };

    return (
        <div className={cn(
            "h-full w-full flex flex-col overflow-hidden transition-colors border-t border-border/50",
            theme === 'dark' ? "bg-background/95" : "bg-white"
        )}>
            <div className={cn("h-9 flex items-center justify-between px-4 border-b shrink-0", theme === 'dark' ? "border-border/50 bg-[#1e1e1e]/50" : "border-border bg-gray-50")}>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 text-xs font-bold text-primary">
                        <TerminalIcon className="w-3.5 h-3.5" />
                        <span>TERMINAL</span>
                    </div>
                </div>
                <button onClick={handleRefresh} className="p-1 hover:bg-muted rounded-md"><RefreshCw className="w-3.5 h-3.5 text-muted-foreground" /></button>
            </div>
            <div ref={terminalRef} className="flex-1 w-full h-full p-2 bg-transparent overflow-hidden" />
        </div>
    );
};
