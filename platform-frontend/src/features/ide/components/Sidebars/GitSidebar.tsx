import React, { useState, useEffect, useCallback } from 'react';
import { GitBranch, GitCommit, AlertCircle, Plus, Minus, RefreshCw, Send, Trash2, FileCode, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';

interface GitStatus {
    branch: string;
    staged: string[];
    unstaged: string[];
    untracked: string[];
}

export const GitSidebar: React.FC = () => {
    const { explorerRootPath } = useAppStore();
    const [status, setStatus] = useState<GitStatus | null>(null);
    const [loading, setLoading] = useState(false);
    const [commitMessage, setCommitMessage] = useState('');
    const [error, setError] = useState<string | null>(null);

    const fetchStatus = useCallback(async () => {
        if (!explorerRootPath) return;
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get(`${API_BASE}/git/status`, {
                params: { path: explorerRootPath }
            });
            setStatus(res.data);
        } catch (e: any) {
            setError(e.response?.data?.detail || "Failed to fetch git status");
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [explorerRootPath]);

    useEffect(() => {
        fetchStatus();
    }, [fetchStatus]);

    const handleAction = async (action: 'stage' | 'unstage', fileName: string) => {
        try {
            await axios.post(`${API_BASE}/git/${action}`, {
                path: explorerRootPath,
                file_path: fileName
            });
            fetchStatus();
        } catch (e) {
            console.error(`Git ${action} failed`, e);
        }
    };

    const handleCommit = async () => {
        if (!commitMessage.trim()) return;
        setLoading(true);
        try {
            await axios.post(`${API_BASE}/git/commit`, {
                path: explorerRootPath,
                message: commitMessage
            });
            setCommitMessage('');
            fetchStatus();
        } catch (e: any) {
            setError(e.response?.data?.detail || "Commit failed");
        } finally {
            setLoading(false);
        }
    };

    if (!explorerRootPath) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4 opacity-50">
                <GitBranch className="w-12 h-12 text-muted-foreground" />
                <p className="text-sm">Open a project to use Source Control</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-background/50 backdrop-blur-md">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 shrink-0">
                <div className="flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-primary" />
                    <span className="text-[11px] font-bold tracking-widest uppercase text-muted-foreground">
                        {status?.branch || 'HEAD'}
                    </span>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:bg-white/5"
                    onClick={fetchStatus}
                    disabled={loading}
                >
                    <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
                </Button>
            </div>

            {/* Commit Form */}
            <div className="p-4 space-y-3 border-b border-border/50 shrink-0">
                <textarea
                    value={commitMessage}
                    onChange={(e) => setCommitMessage(e.target.value)}
                    placeholder="Commit message (Ctrl+Enter to commit)"
                    className="w-full min-h-[80px] bg-muted/30 border border-border/50 rounded-lg p-3 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-primary/30 transition-all placeholder:text-muted-foreground/50"
                    onKeyDown={(e) => {
                        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleCommit();
                    }}
                />
                <Button
                    className="w-full h-9 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/20 text-[11px] font-bold tracking-wider"
                    onClick={handleCommit}
                    disabled={loading || !commitMessage.trim() || status?.staged.length === 0}
                >
                    <GitCommit className="w-4 h-4 mr-2" />
                    Commit Submissions
                </Button>
            </div>

            {/* Changes List */}
            <div className="flex-1 overflow-y-auto no-scrollbar py-2">
                {error && (
                    <div className="mx-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] flex gap-2">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{error}</span>
                    </div>
                )}

                {/* Staged Section */}
                {status && status.staged.length > 0 && (
                    <div className="mb-4">
                        <div className="px-4 py-1 flex items-center justify-between group">
                            <span className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-wider">Staged Changes</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">{status.staged.length}</span>
                        </div>
                        {status.staged.map((file) => (
                            <GitNavItem
                                key={file}
                                name={file}
                                state="staged"
                                onAction={() => handleAction('unstage', file)}
                            />
                        ))}
                    </div>
                )}

                {/* Unstaged Section */}
                {status && (status.unstaged.length > 0 || status.untracked.length > 0) && (
                    <div>
                        <div className="px-4 py-1 flex items-center justify-between group">
                            <span className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-wider">Changes</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                                {status.unstaged.length + status.untracked.length}
                            </span>
                        </div>
                        {status.unstaged.map((file) => (
                            <GitNavItem
                                key={file}
                                name={file}
                                state="modified"
                                onAction={() => handleAction('stage', file)}
                            />
                        ))}
                        {status.untracked.map((file) => (
                            <GitNavItem
                                key={file}
                                name={file}
                                state="untracked"
                                onAction={() => handleAction('stage', file)}
                            />
                        ))}
                    </div>
                )}

                {status && status.staged.length === 0 && status.unstaged.length === 0 && status.untracked.length === 0 && !loading && (
                    <div className="flex flex-col items-center justify-center h-48 opacity-30 text-center px-8">
                        <Check className="w-8 h-8 mb-2" />
                        <p className="text-[11px] leading-relaxed">Workspace is clean.<br />No pending changes found.</p>
                    </div>
                )}
            </div>

            {/* Beta Footer */}
            <div className="p-4 border-t border-border/50 bg-muted/10 shrink-0">
                <div className="flex items-center gap-2 text-[9px] text-muted-foreground justify-center uppercase tracking-[0.2em] font-bold opacity-50">
                    <AlertCircle className="w-3 h-3" />
                    <span>Experimental Core</span>
                </div>
            </div>
        </div>
    );
};

const GitNavItem: React.FC<{
    name: string;
    state: 'staged' | 'modified' | 'untracked';
    onAction: () => void;
}> = ({ name, state, onAction }) => {
    return (
        <div className="group flex items-center gap-2 px-4 py-1.5 hover:bg-white/5 transition-colors cursor-default">
            <FileCode className={cn(
                "w-3.5 h-3.5 shrink-0",
                state === 'staged' ? "text-green-400" : state === 'modified' ? "text-amber-400" : "text-primary"
            )} />
            <div className="flex-1 min-w-0">
                <p className="text-[11px] truncate text-foreground/80">{name.split('/').pop()}</p>
                <p className="text-[9px] truncate text-muted-foreground/50">{name.split('/').slice(0, -1).join('/') || './'}</p>
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 hover:bg-primary/20 hover:text-primary transition-all active:scale-95"
                    onClick={(e) => { e.stopPropagation(); onAction(); }}
                >
                    {state === 'staged' ? <Minus className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                </Button>
            </div>
            <span className={cn(
                "text-[9px] font-black uppercase tracking-tighter w-4 text-center",
                state === 'staged' ? "text-green-500/50" : state === 'modified' ? "text-amber-500/50" : "text-primary/50"
            )}>
                {state === 'staged' ? 'A' : state === 'modified' ? 'M' : 'U'}
            </span>
        </div>
    );
};
