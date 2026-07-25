import React, { useCallback, useEffect, useState } from 'react';
import {
    Circle, X, Loader2, Bell, User, ChevronDown, Cloud,
    ShieldCheck, Volume2, FolderOpen, Command
} from 'lucide-react';
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { ThemeToggle } from '@/components/theme';
import { ArcturusLogo } from '@/components/common/ArcturusLogo';
import { StatsModal } from '@/components/stats/StatsModal';
import { SpacesModal } from '@/components/sidebar/SpacesModal';
import { AuthModal } from '@/components/auth/AuthModal';
import { Kbd } from '@/components/ui/kbd';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { EchoDropdown } from './EchoDropdown';

// ── Tab display names for breadcrumb ─────────────────────────────────────────
const TAB_LABELS: Record<string, string> = {
    runs: 'Agent Runs',
    rag: 'RAG Documents',
    notes: 'Notes',
    remme: 'Memory Vault',
    graph: 'Knowledge Graph',
    explorer: 'Explorer',
    apps: 'App Builder',
    news: 'News Feed',
    settings: 'Settings',
    skills: 'Skill Store',
    ide: 'IDE',
    scheduler: 'Scheduler',
    console: 'Mission Control',
    echo: 'Echo',
    studio: 'Forge',
    canvas: 'Canvas',
    admin: 'Admin',
    swarm: 'Swarm',
};

export const Header: React.FC = () => {
    const {
        currentRun, sidebarTab, spaces,
        isSpacesModalOpen, setIsSpacesModalOpen,
        currentSpaceId,
        unreadCount, isInboxOpen, setIsInboxOpen,
        authStatus, authUserFirstName, authUserEmail, isAuthModalOpen, setIsAuthModalOpen,
        gitSummary, fetchGitSummary,
    } = useAppStore();

    const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');
    const [isStatsOpen, setIsStatsOpen] = useState(false);

    // ── Privacy Mode ─────────────────────────────────────────────────────────
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

    useEffect(() => { const t = setTimeout(fetchPrivacy, 2000); return () => clearTimeout(t); }, [fetchPrivacy]);

    // ── Persona Selection ────────────────────────────────────────────────────
    const [personas, setPersonas] = useState<Record<string, { voice_name: string; rate: string; pitch: string; volume: string; description: string }> | null>(null);
    const [activePersona, setActivePersona] = useState<string | null>(null);
    const [personaChanging, setPersonaChanging] = useState(false);

    const fetchPersonas = useCallback(async () => {
        try {
            const res = await fetch('http://localhost:8000/api/voice/personas');
            if (res.ok) {
                const data = await res.json();
                setPersonas(data.personas ?? null);
                setActivePersona(data.active ?? null);
            }
        } catch { /* backend not ready */ }
    }, []);

    const changePersona = async (name: string) => {
        if (personaChanging || !personas || name === activePersona) return;
        setPersonaChanging(true);
        try {
            const res = await fetch('http://localhost:8000/api/voice/persona', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ persona: name }),
            });
            if (res.ok) {
                setActivePersona(name);
            }
        } catch (e) {
            console.error('Persona change failed', e);
        } finally {
            setPersonaChanging(false);
        }
    };

    useEffect(() => { const t = setTimeout(fetchPersonas, 2000); return () => clearTimeout(t); }, [fetchPersonas]);

    // Ollama status check (deferred — not critical for initial render)
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
        const t = setTimeout(checkOllama, 3000);
        const interval = setInterval(checkOllama, 30000);
        return () => { clearTimeout(t); clearInterval(interval); };
    }, []);

    // Git status for IDE tab
    useEffect(() => {
        if (sidebarTab === 'ide') {
            fetchGitSummary();
            const interval = setInterval(fetchGitSummary, 5000);
            return () => clearInterval(interval);
        }
    }, [sidebarTab, fetchGitSummary]);

    const handleStop = async () => {
        if (!currentRun) return;
        try {
            await api.stopRun(currentRun.id);
        } catch (e) {
            console.error("Failed to stop run:", e);
        }
    };

    const currentSpaceName = currentSpaceId
        ? (spaces.find(s => s.space_id === currentSpaceId)?.name || 'Space')
        : 'Global';

    return (
        <>
            {/* Running agent — top edge progress bar */}
            {currentRun?.status === 'running' && (
                <div className="h-0.5 bg-primary/20 relative overflow-hidden shrink-0 z-50">
                    <div className="absolute inset-y-0 left-0 w-1/3 bg-primary animate-[ticker_1.5s_ease-in-out_infinite]" />
                </div>
            )}

            <header className="h-10 border-b border-border flex items-center justify-between px-4 shrink-0 z-50 drag-region bg-background">
                {/* Left — Brand + Breadcrumb */}
                <div className="flex items-center gap-3 pl-16">
                    <div
                        className="flex items-center gap-1.5 cursor-pointer no-drag"
                        onClick={() => window.location.reload()}
                    >
                        <ArcturusLogo className="w-6 h-6" />
                        <span className="hidden sm:inline text-sm font-bold tracking-tight text-foreground">
                            Arcturus
                        </span>
                    </div>

                    <span className="text-border text-sm">/</span>

                    {/* Breadcrumb — current context */}
                    <span className="text-sm text-muted-foreground font-medium">
                        {TAB_LABELS[sidebarTab] || sidebarTab}
                    </span>

                    {/* IDE git status inline */}
                    {sidebarTab === 'ide' && gitSummary && (
                        <span className={cn(
                            "text-2xs font-mono px-1.5 py-0.5 rounded",
                            gitSummary.staged > 0
                                ? "text-success bg-success-muted"
                                : (gitSummary.unstaged + gitSummary.untracked) > 0
                                    ? "text-warning bg-warning-muted"
                                    : "text-muted-foreground bg-surface-2"
                        )}>
                            {gitSummary.staged > 0
                                ? `${gitSummary.staged} staged`
                                : (gitSummary.unstaged + gitSummary.untracked) > 0
                                    ? `${gitSummary.unstaged + gitSummary.untracked} changes`
                                    : 'clean'}
                        </span>
                    )}

                    {/* Running status — compact inline */}
                    {currentRun?.status === 'running' && (
                        <div className="flex items-center gap-1.5 ml-2 px-2 py-0.5 rounded-full bg-warning-muted border border-warning/20 no-drag animate-content-in">
                            <span className="w-1.5 h-1.5 bg-warning rounded-full animate-pulse" />
                            <span className="text-2xs font-semibold text-warning uppercase tracking-tight">Running</span>
                            <button onClick={handleStop} className="ml-0.5 p-0.5 hover:bg-warning/20 rounded text-warning/80">
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                    )}
                </div>

                {/* Right — Compact controls */}
                <div className="flex items-center gap-1.5 no-drag">
                    {/* Echo Voice — global access */}
                    <EchoDropdown />

                    {/* Command Palette hint */}
                    <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => {
                                    // Dispatch Cmd+K to open command palette
                                    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }));
                                }}
                                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface-1 border border-border hover:bg-surface-2 transition-colors text-muted-foreground hover:text-foreground"
                            >
                                <Command className="w-3 h-3" />
                                <span className="text-xs">Search</span>
                                <Kbd>K</Kbd>
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>Open command palette</TooltipContent>
                    </Tooltip>

                    <div className="w-px h-5 bg-border mx-1" />

                    {/* Space selector — compact pill */}
                    <button
                        onClick={() => setIsSpacesModalOpen(true)}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md hover:bg-accent transition-colors"
                        title="Manage Spaces"
                    >
                        <FolderOpen className="w-3.5 h-3.5 text-muted-foreground" />
                        <span className="text-xs font-medium text-muted-foreground max-w-[80px] truncate">
                            {currentSpaceName}
                        </span>
                    </button>

                    {/* Privacy toggle — minimal */}
                    <button
                        onClick={togglePrivacy}
                        disabled={privacyLoading || privacyMode === null}
                        title={privacyMode ? 'Privacy Mode (Local)' : 'Cloud Mode'}
                        className={cn(
                            'flex items-center gap-1 px-2 py-1 rounded-md transition-all duration-150',
                            privacyMode === false
                                ? 'text-info hover:bg-info-muted'
                                : privacyMode === true
                                    ? 'text-success hover:bg-success-muted'
                                    : 'text-muted-foreground hover:bg-accent',
                            (privacyLoading || privacyMode === null) && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        {privacyLoading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : privacyMode === false ? (
                            <Cloud className="w-3.5 h-3.5" />
                        ) : (
                            <ShieldCheck className="w-3.5 h-3.5" />
                        )}
                    </button>

                    {/* Persona selector — only when cloud mode */}
                    {personas && Object.keys(personas).length > 0 && !privacyMode && (
                        <div className="relative flex items-center rounded-md hover:bg-accent transition-colors">
                            <Volume2 className="w-3 h-3 ml-2 text-muted-foreground shrink-0" />
                            <select
                                value={activePersona ?? ''}
                                onChange={e => changePersona(e.target.value)}
                                disabled={personaChanging}
                                className={cn(
                                    'appearance-none bg-transparent border-none outline-none',
                                    'text-xs font-medium pl-1 pr-5 py-1 cursor-pointer',
                                    'text-muted-foreground hover:text-foreground transition-colors',
                                    personaChanging && 'cursor-not-allowed'
                                )}
                            >
                                {Object.entries(personas).map(([key, cfg]) => (
                                    <option key={key} value={key} title={cfg.description}>
                                        {key.charAt(0).toUpperCase() + key.slice(1)}
                                    </option>
                                ))}
                            </select>
                            <div className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground">
                                {personaChanging
                                    ? <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                    : <ChevronDown className="w-2.5 h-2.5" />}
                            </div>
                        </div>
                    )}

                    {/* Ollama status — minimal dot */}
                    <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-accent transition-colors cursor-default">
                                <Circle className={cn(
                                    "w-2 h-2 fill-current",
                                    ollamaStatus === 'online' && "text-success",
                                    ollamaStatus === 'offline' && "text-destructive",
                                    ollamaStatus === 'checking' && "text-warning animate-pulse"
                                )} />
                                <span className="text-xs text-muted-foreground">Ollama</span>
                            </div>
                        </TooltipTrigger>
                        <TooltipContent>
                            Ollama: {ollamaStatus}
                        </TooltipContent>
                    </Tooltip>

                    <div className="w-px h-5 bg-border mx-1" />

                    {/* Auth — avatar-style */}
                    <button
                        onClick={() => setIsAuthModalOpen(true)}
                        className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-accent transition-colors"
                    >
                        <div className={cn(
                            "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold",
                            authStatus === 'logged_in'
                                ? "bg-primary/15 text-primary"
                                : "bg-surface-3 text-muted-foreground"
                        )}>
                            {authStatus === 'logged_in'
                                ? (authUserFirstName?.[0] || authUserEmail?.[0] || 'U').toUpperCase()
                                : <User className="w-3 h-3" />}
                        </div>
                    </button>

                    {/* Inbox */}
                    <button
                        onClick={() => setIsInboxOpen(!isInboxOpen)}
                        className={cn(
                            "relative p-1.5 rounded-md transition-all",
                            isInboxOpen
                                ? "bg-primary/10 text-primary"
                                : "hover:bg-accent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <Bell className="w-4 h-4" />
                        {unreadCount > 0 && (
                            <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-primary rounded-full" />
                        )}
                    </button>

                    {/* Theme */}
                    <ThemeToggle />
                </div>
            </header>

            <StatsModal isOpen={isStatsOpen} onClose={() => setIsStatsOpen(false)} />
            <SpacesModal isOpen={isSpacesModalOpen} onClose={() => setIsSpacesModalOpen(false)} />
            <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
        </>
    );
};
