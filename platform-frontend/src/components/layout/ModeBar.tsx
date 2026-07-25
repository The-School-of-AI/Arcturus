import React from 'react';
import { Compass, Flame, Focus, Bug } from 'lucide-react';
import { useAppStore } from '@/store';
import type { UIMode } from '@/store';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

const MODES: { id: UIMode; label: string; icon: any; shortcut: string; description: string }[] = [
    { id: 'explore', label: 'Explore', icon: Compass, shortcut: 'E', description: 'Browse runs, calm view' },
    { id: 'execute', label: 'Execute', icon: Flame, shortcut: 'X', description: 'Active graph, live logs' },
    { id: 'focus', label: 'Focus', icon: Focus, shortcut: 'F', description: 'Single agent, minimal UI' },
    { id: 'debug', label: 'Debug', icon: Bug, shortcut: 'D', description: 'Deep logs, timings' },
];

const MODE_COLORS: Record<UIMode, string> = {
    explore: 'text-mode-explore bg-mode-explore/10 border-mode-explore/30',
    execute: 'text-mode-execute bg-mode-execute/10 border-mode-execute/30',
    focus: 'text-mode-focus bg-mode-focus/10 border-mode-focus/30',
    debug: 'text-mode-debug bg-mode-debug/10 border-mode-debug/30',
};

const MODE_DOT: Record<UIMode, string> = {
    explore: 'bg-mode-explore',
    execute: 'bg-mode-execute',
    focus: 'bg-mode-focus',
    debug: 'bg-mode-debug',
};

export const ModeBar: React.FC = () => {
    const uiMode = useAppStore(state => state.uiMode);
    const setUIMode = useAppStore(state => state.setUIMode);

    return (
        <div className="flex items-center gap-0.5 p-0.5 rounded-full bg-surface-1/80 border border-border/40 backdrop-blur-sm">
            {MODES.map((mode) => {
                const Icon = mode.icon;
                const isActive = uiMode === mode.id;

                return (
                    <Tooltip key={mode.id} delayDuration={0}>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => setUIMode(mode.id)}
                                className={cn(
                                    "relative flex items-center gap-1.5 px-2.5 py-1 rounded-full text-2xs font-semibold uppercase tracking-wider transition-all duration-200",
                                    isActive
                                        ? cn("border", MODE_COLORS[mode.id])
                                        : "text-muted-foreground hover:text-foreground border border-transparent hover:bg-accent/50"
                                )}
                            >
                                <Icon className="w-3 h-3" />
                                <span className="hidden sm:inline">{mode.label}</span>
                                {isActive && (
                                    <span className={cn(
                                        "absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full",
                                        MODE_DOT[mode.id]
                                    )} />
                                )}
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs">
                            <span>{mode.description}</span>
                        </TooltipContent>
                    </Tooltip>
                );
            })}
        </div>
    );
};
