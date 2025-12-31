import React, { useEffect, useState } from 'react';
import { Box, Square, Circle } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { ThemeToggle } from '@/components/theme';

const TAB_LABELS: Record<string, string> = {
    runs: 'Runs',
    rag: 'RAG Documents',
    mcp: 'MCP Servers',
    remme: 'Remme Memory',
    explorer: 'Code Explorer',
    apps: 'App Builder',
    news: 'News Feed',
    learn: 'Learning'
};

export const Header: React.FC = () => {
    const { currentRun, sidebarTab } = useAppStore();
    const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');

    // Check Ollama status on mount and periodically
    useEffect(() => {
        const checkOllama = async () => {
            try {
                const response = await fetch('http://127.0.0.1:11434/api/tags', {
                    method: 'GET',
                    signal: AbortSignal.timeout(2000)
                });
                setOllamaStatus(response.ok ? 'online' : 'offline');
            } catch {
                setOllamaStatus('offline');
            }
        };

        checkOllama();
        const interval = setInterval(checkOllama, 30000); // Check every 30s
        return () => clearInterval(interval);
    }, []);

    const handleStop = async () => {
        if (!currentRun) return;
        try {
            await api.stopRun(currentRun.id);
        } catch (e) {
            console.error("Failed to stop run:", e);
        }
    };

    return (
        <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0 shadow-sm z-50">
            <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-primary font-bold text-lg tracking-tight">
                    <Box className="w- h-6 animate-pulse" />
                    <span>Arcturus<span className="text-foreground">Platform</span></span>
                </div>

                <div className="h-6 w-px bg-border mx-2" />

                {/* Active Tab Name */}
                <span className="text-sm font-medium text-foreground">
                    {TAB_LABELS[sidebarTab] || sidebarTab}
                </span>

                {/* Show run status segment ONLY in Runs tab or when running in background (without name) */}
                {currentRun && (sidebarTab === 'runs' || currentRun.status === 'running') && (
                    <>
                        <div className="h-4 w-px bg-border mx-1" />
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span className={cn(
                                "px-2 py-0.5 rounded-full text-xs font-medium uppercase tracking-wider",
                                currentRun.status === 'running' && "bg-yellow-500/20 text-yellow-500 animate-pulse",
                                currentRun.status === 'completed' && "bg-green-500/20 text-green-500",
                                currentRun.status === 'failed' && "bg-red-500/20 text-red-500",
                            )}>
                                {currentRun.status}
                            </span>
                        </div>
                    </>
                )}
            </div>

            <div className="flex items-center gap-2">
                {/* Ollama Status Indicator */}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted/50">
                    <Circle
                        className={cn(
                            "w-2.5 h-2.5 fill-current",
                            ollamaStatus === 'online' && "text-green-500",
                            ollamaStatus === 'offline' && "text-red-500",
                            ollamaStatus === 'checking' && "text-yellow-500 animate-pulse"
                        )}
                    />
                    <span className="text-xs text-muted-foreground">Ollama</span>
                </div>

                <ThemeToggle />

                {/* Stop button only when running */}
                {currentRun?.status === 'running' && (
                    <Button
                        variant="destructive"
                        size="sm"
                        className="h-8 gap-2 transition-all"
                        onClick={handleStop}
                    >
                        <Square className="w-3 h-3 fill-current" />
                        Stop
                    </Button>
                )}
            </div>
        </header>
    );
};
