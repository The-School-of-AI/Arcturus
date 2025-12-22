import React, { useState } from 'react';
import { Play, Settings, Box, Database } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { SettingsModal } from '@/features/settings/SettingsModal';

export const Header: React.FC = () => {
    const { currentRun } = useAppStore(); // Removed unused 'theme'
    const [settingsOpen, setSettingsOpen] = useState(false);

    return (
        <>
            <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
            <header className="h-14 border-b border-border bg-charcoal-900 flex items-center justify-between px-4 shrink-0 shadow-sm z-50">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-primary font-bold text-lg tracking-tight">
                        <Box className="w-6 h-6 animate-pulse" />
                        <span>Agentic<span className="text-foreground">Platform</span></span>
                    </div>

                    <div className="h-6 w-px bg-border mx-2" />

                    {currentRun ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span className="font-medium text-foreground">{currentRun.name}</span>
                            <span className={cn(
                                "px-2 py-0.5 rounded-full text-xs font-medium uppercase tracking-wider",
                                currentRun.status === 'running' && "bg-yellow-500/20 text-yellow-500 animate-pulse",
                                currentRun.status === 'completed' && "bg-green-500/20 text-green-500",
                                currentRun.status === 'failed' && "bg-red-500/20 text-red-500",
                            )}>
                                {currentRun.status}
                            </span>
                        </div>
                    ) : (
                        <span className="text-sm text-muted-foreground italic">Select or create a run...</span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" className="h-8 gap-2 text-muted-foreground hover:text-foreground">
                        <Database className="w-4 h-4" />
                        <span className="text-xs">Gemini-1.5-Pro</span>
                    </Button>

                    <Button variant="outline" size="sm" className="h-8 border-primary/20 hover:border-primary text-primary hover:bg-primary/10 transition-all">
                        <Play className="w-3 h-3 mr-1.5 fill-current" />
                        Run
                    </Button>

                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 hover:bg-primary/10 hover:text-primary"
                        onClick={() => setSettingsOpen(true)}
                    >
                        <Settings className="w-4 h-4" />
                    </Button>
                </div>
            </header>
        </>
    );
};
