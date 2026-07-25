import React, { useCallback, useEffect, useState } from 'react';
import {
    X, Loader2, Bell, User, Cloud,
    ShieldCheck, Command, Compass, Flame, Focus, Bug
} from 'lucide-react';
import { useAppStore } from '@/store';
import type { UIMode } from '@/store';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { ThemeToggle } from '@/components/theme';
import { ArcturusLogo } from '@/components/common/ArcturusLogo';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Kbd } from '@/components/ui/kbd';

// ── Mode config ──────────────────────────────────────────────────────────────

const MODE_CONFIG: Record<UIMode, { label: string; icon: any; colorClass: string }> = {
    explore: { label: 'Explore', icon: Compass, colorClass: 'text-mode-explore' },
    execute: { label: 'Execute', icon: Flame, colorClass: 'text-mode-execute' },
    focus: { label: 'Focus', icon: Focus, colorClass: 'text-mode-focus' },
    debug: { label: 'Debug', icon: Bug, colorClass: 'text-mode-debug' },
};

export const StatusStrip: React.FC = () => {
    const {
        currentRun, uiMode,
        unreadCount, isInboxOpen, setIsInboxOpen,
        authStatus, authUserFirstName, authUserEmail,
        isAuthModalOpen, setIsAuthModalOpen,
    } = useAppStore();

    const [privacyMode, setPrivacyMode] = useState<boolean | null>(null);
    const [privacyLoading, setPrivacyLoading] = useState(false);

    const fetchPrivacy = useCallback(async () => {
        try {
            const res = await fetch('http://localhost:8000/api/voice/privacy');
            if (res.ok) {
                const data = await res.json();
                setPrivacyMode(data.privacy_mode ?? false);
            }
        } catch { /* backend not ready */ }
    }, []);

    const togglePrivacy = async () => {
        if (privacyLoading || privacyMode === null) return;
        setPrivacyLoading(true);
        try {
            const res = await fetch('http://localhost:8000/api/voice/privacy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !privacyMode }),
            });
            if (res.ok) {
                const data = await res.json();
                setPrivacyMode(data.privacy_mode);
            }
        } catch (e) {
            console.error('Privacy toggle failed', e);
        } finally {
            setPrivacyLoading(false);
        }
    };

    useEffect(() => { fetchPrivacy(); }, [fetchPrivacy]);

    const handleStop = async () => {
        if (!currentRun) return;
        try {
            await api.stopRun(currentRun.id);
        } catch (e) {
            console.error("Failed to stop run:", e);
        }
    };

    const modeInfo = MODE_CONFIG[uiMode];
    const ModeIcon = modeInfo.icon;

    return (
        <>
            {/* Running agent — top edge progress bar */}
            {currentRun?.status === 'running' && (
                <div className="h-0.5 bg-primary/20 relative overflow-hidden shrink-0 z-50">
                    <div className="absolute inset-y-0 left-0 w-1/3 bg-primary animate-[ticker_1.5s_ease-in-out_infinite]" />
                </div>
            )}

            <header className="h-8 flex items-center justify-between px-4 shrink-0 z-50 drag-region status-strip">
                {/* Left — Brand + Mode pill */}
                <div className="flex items-center gap-2.5 pl-16 no-drag">
                    <div
                        className="flex items-center gap-1.5 cursor-pointer"
                        onClick={() => window.location.reload()}
                    >
                        <ArcturusLogo className="w-4 h-4" />
                        <span className="text-xs font-bold tracking-tight text-foreground">
                            Arcturus
                        </span>
                    </div>

                    {/* Mode indicator pill */}
                    <div className={cn(
                        "flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-semibold uppercase tracking-wider transition-colors duration-300",
                        "bg-surface-2 border border-border/50",
                        modeInfo.colorClass
                    )}>
                        <ModeIcon className="w-3 h-3" />
                        <span>{modeInfo.label}</span>
                    </div>

                    {/* Running status — compact inline */}
                    {currentRun?.status === 'running' && (
                        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-mode-execute/10 border border-mode-execute/20 animate-content-in">
                            <span className="w-1.5 h-1.5 bg-mode-execute rounded-full animate-pulse" />
                            <span className="text-2xs font-semibold text-mode-execute uppercase tracking-tight">Running</span>
                            <button onClick={handleStop} className="ml-0.5 p-0.5 hover:bg-mode-execute/20 rounded text-mode-execute/80">
                                <X className="w-2.5 h-2.5" />
                            </button>
                        </div>
                    )}
                </div>

                {/* Right — Compact controls */}
                <div className="flex items-center gap-1 no-drag">
                    {/* Command Palette hint */}
                    <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => {
                                    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }));
                                }}
                                className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-surface-1/50 border border-border/40 hover:bg-surface-2 transition-colors text-muted-foreground hover:text-foreground"
                            >
                                <Command className="w-2.5 h-2.5" />
                                <Kbd className="text-[9px]">K</Kbd>
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>Command palette</TooltipContent>
                    </Tooltip>

                    {/* Privacy toggle */}
                    <button
                        onClick={togglePrivacy}
                        disabled={privacyLoading || privacyMode === null}
                        title={privacyMode ? 'Privacy Mode (Local)' : 'Cloud Mode'}
                        className={cn(
                            'p-1 rounded-md transition-all duration-150',
                            privacyMode === false
                                ? 'text-info hover:bg-info-muted'
                                : privacyMode === true
                                    ? 'text-success hover:bg-success-muted'
                                    : 'text-muted-foreground hover:bg-accent',
                            (privacyLoading || privacyMode === null) && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        {privacyLoading ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                        ) : privacyMode === false ? (
                            <Cloud className="w-3 h-3" />
                        ) : (
                            <ShieldCheck className="w-3 h-3" />
                        )}
                    </button>

                    {/* Auth */}
                    <button
                        onClick={() => setIsAuthModalOpen(true)}
                        className="p-1 rounded-md hover:bg-accent transition-colors"
                    >
                        <div className={cn(
                            "w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold",
                            authStatus === 'logged_in'
                                ? "bg-primary/15 text-primary"
                                : "bg-surface-3 text-muted-foreground"
                        )}>
                            {authStatus === 'logged_in'
                                ? (authUserFirstName?.[0] || authUserEmail?.[0] || 'U').toUpperCase()
                                : <User className="w-2.5 h-2.5" />}
                        </div>
                    </button>

                    {/* Inbox */}
                    <button
                        onClick={() => setIsInboxOpen(!isInboxOpen)}
                        className={cn(
                            "relative p-1 rounded-md transition-all",
                            isInboxOpen
                                ? "bg-primary/10 text-primary"
                                : "hover:bg-accent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <Bell className="w-3 h-3" />
                        {unreadCount > 0 && (
                            <span className="absolute top-0.5 right-0.5 w-1 h-1 bg-primary rounded-full" />
                        )}
                    </button>

                    {/* Theme */}
                    <ThemeToggle />
                </div>
            </header>
        </>
    );
};
