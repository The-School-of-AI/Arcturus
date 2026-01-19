import React, { useState, useEffect, useCallback } from 'react';
import { GitBranch, GitCommit, AlertCircle, Plus, Minus, RefreshCw, Send, Trash2, FileCode, Check, ChevronDown, ChevronRight, ArrowUpRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store';
import { useIdeStore } from '../../store/ideStore';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';

interface GitHistory {
    hash: string;
    message: string;
    author: string;
    date: string;
    branches: string[];
    files: string[];
}

interface GitStatus {
    branch: string;
    staged: string[];
    unstaged: string[];
    untracked: string[];
}

export const GitSidebar: React.FC = () => {
    const { explorerRootPath, openIdeDocument } = useAppStore();
    const { activeGitView, setActiveGitView } = useIdeStore();
    const [userBranch, setUserBranch] = useState<string>('main');
    const [status, setStatus] = useState<GitStatus | null>(null);
    const [history, setHistory] = useState<GitHistory[]>([]);
    const [loading, setLoading] = useState(false);
    const [commitMessage, setCommitMessage] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [expandedCommits, setExpandedCommits] = useState<Set<string>>(new Set());

    const fetchStatus = useCallback(async () => {
        if (!explorerRootPath) return;
        setLoading(true);
        setError(null);
        try {
            const targetBranch = activeGitView === 'arcturus' ? 'arcturus' : userBranch;
            const [statusRes, historyRes] = await Promise.all([
                axios.get(`${API_BASE}/git/status`, { params: { path: explorerRootPath } }).catch(e => e),
                axios.get(`${API_BASE}/git/history`, { params: { path: explorerRootPath, branch: targetBranch } }).catch(e => ({ data: [] }))
            ]);

            if (statusRes.data) {
                setStatus(statusRes.data);
            } else if (statusRes.response?.data?.detail) {
                setError(statusRes.response.data.detail);
            }

            if (historyRes.data) {
                setHistory(historyRes.data);
            }
        } catch (e: any) {
            console.error("Git Fetch Error:", e);
        } finally {
            setLoading(false);
        }
    }, [explorerRootPath, activeGitView, userBranch]);

    // Fetch user branch name
    useEffect(() => {
        if (!explorerRootPath) return;
        axios.get(`${API_BASE}/git/arcturus/branches`, { params: { path: explorerRootPath } })
            .then(res => {
                if (res.data.user_branch) setUserBranch(res.data.user_branch);
            })
            .catch(e => console.error(e));
    }, [explorerRootPath]);

    useEffect(() => {
        fetchStatus();

        const handleRefresh = () => fetchStatus();
        window.addEventListener('arcturus:git-init', handleRefresh);
        return () => window.removeEventListener('arcturus:git-init', handleRefresh);
    }, [fetchStatus]);

    const handleAction = async (action: 'stage' | 'unstage', fileName: string) => {
        try {
            await axios.post(`${API_BASE}/git/${action}`, {
                path: explorerRootPath,
                file_path: fileName
            });
            fetchStatus();
        } catch (e: any) {
            setError(e.response?.data?.detail || `Git ${action} failed`);
        }
    };

    const handleCommit = async () => {
        if (!commitMessage.trim()) return;
        setLoading(true);
        try {
            const isAutoStage = status?.staged.length === 0;
            await axios.post(`${API_BASE}/git/commit`, {
                path: explorerRootPath,
                message: commitMessage,
                stage_all: isAutoStage
            });
            setCommitMessage('');
            fetchStatus();
        } catch (e: any) {
            setError(e.response?.data?.detail || "Commit failed");
        } finally {
            setLoading(false);
        }
    };

    const handleFileClick = async (file: string, isStaged: boolean, commitHash?: string) => {
        try {
            const res = await axios.get(`${API_BASE}/git/diff_content`, {
                params: {
                    path: explorerRootPath,
                    file_path: file,
                    staged: isStaged,
                    commit_hash: commitHash
                }
            });

            const { original, modified, filename } = res.data;

            openIdeDocument({
                id: `git_diff:${commitHash || (isStaged ? 'staged' : 'unstaged')}:${file}`,
                title: `DIFF: ${filename}${commitHash ? ` (${commitHash.substring(0, 7)})` : ''}`,
                type: 'git_diff',
                originalContent: original,
                modifiedContent: modified
            });
        } catch (e: any) {
            setError(e.response?.data?.detail || "Failed to load diff content");
        }
    };

    const toggleCommit = async (hash: string) => {
        const isExpanding = !expandedCommits.has(hash);

        setExpandedCommits(prev => {
            const next = new Set(prev);
            if (next.has(hash)) next.delete(hash);
            else next.add(hash);
            return next;
        });

        // Fetch files on demand if expanding and they aren't loaded yet
        if (isExpanding) {
            const commit = history.find(c => c.hash === hash);
            if (commit && commit.files.length === 0) {
                try {
                    const res = await axios.get(`${API_BASE}/git/commit_files`, {
                        params: { path: explorerRootPath, commit_hash: hash }
                    });
                    if (res.data.files) {
                        setHistory(prev => prev.map(c =>
                            c.hash === hash ? { ...c, files: res.data.files } : c
                        ));
                    }
                } catch (e) {
                    console.error("Failed to fetch commit files:", e);
                }
            }
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

    const totalChanges = (status?.staged.length || 0) + (status?.unstaged.length || 0) + (status?.untracked.length || 0);
    const hasChanges = totalChanges > 0;



    return (
        <div className="h-full flex flex-col bg-transparent">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-muted/20 border-b border-border/50 shrink-0">
                <div className="flex items-center gap-2">
                    <GitBranch className="w-3.5 h-3.5 text-primary" />
                    <span className="text-[10px] font-bold tracking-widest uppercase text-muted-foreground">
                        {status?.branch || 'HEAD'}
                    </span>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 hover:bg-white/5"
                    onClick={fetchStatus}
                    disabled={loading}
                >
                    <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
                </Button>
            </div>

            {/* Arcturus / User Branch Toggle */}
            <div className="flex items-center gap-1 px-3 py-2 border-b border-border/30 bg-muted/10">
                <button
                    onClick={() => setActiveGitView('arcturus')}
                    className={cn(
                        "flex-1 flex items-center justify-center gap-1.5 px-2 py-1 rounded text-[10px] font-bold transition-all",
                        activeGitView === 'arcturus'
                            ? "bg-primary/20 text-primary border border-primary/30"
                            : "text-muted-foreground hover:bg-white/5"
                    )}
                >
                    <span>Arcturus</span>
                    {hasChanges && activeGitView === 'arcturus' && (
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                    )}
                </button>
                <button
                    onClick={() => setActiveGitView('user')}
                    className={cn(
                        "flex-1 flex items-center justify-center gap-1.5 px-2 py-1 rounded text-[10px] font-bold transition-all",
                        activeGitView === 'user'
                            ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                            : "text-muted-foreground hover:bg-white/5"
                    )}
                >
                    <span>User</span>
                    <ArrowUpRight className="w-2.5 h-2.5" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto scrollbar-thin">
                {/* COMMIT SECTION */}
                <div className="p-3 space-y-2 border-b border-border/10">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/60">Changes</span>
                    </div>

                    <div className="relative group/input">
                        <textarea
                            value={commitMessage}
                            onChange={(e) => setCommitMessage(e.target.value)}
                            placeholder={`Message (Cmd+Enter to commit on "${status?.branch || 'master'}")`}
                            className="w-full min-h-[60px] bg-muted/40 border border-border/30 rounded-md p-2 text-[11px] resize-none focus:outline-none focus:ring-1 focus:ring-primary/20 transition-all placeholder:text-muted-foreground/40 leading-relaxed"
                            onKeyDown={(e) => {
                                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleCommit();
                            }}
                        />
                    </div>

                    <Button
                        className={cn(
                            "w-full h-8 text-[11px] font-bold tracking-wider transition-all",
                            hasChanges ? "bg-primary text-primary-foreground hover:bg-primary/90" : "bg-muted/50 text-muted-foreground/40 cursor-not-allowed"
                        )}
                        onClick={handleCommit}
                        disabled={loading || !commitMessage.trim() || !hasChanges}
                    >
                        <Check className="w-3.5 h-3.5 mr-2" />
                        Commit
                    </Button>
                </div>

                {error && (
                    <div className="mx-3 mt-3 p-2 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] flex gap-2">
                        <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                        <span className="break-all">{error}</span>
                    </div>
                )}

                {/* CHANGES LIST */}
                <div className="py-2">
                    {/* Staged Section */}
                    {status && status.staged.length > 0 && (
                        <div className="mb-2">
                            <div className="px-3 py-1 flex items-center justify-between group cursor-pointer hover:bg-white/5">
                                <div className="flex items-center gap-1">
                                    <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
                                    <span className="text-[9px] font-bold text-muted-foreground/70 uppercase tracking-widest">Staged Changes</span>
                                </div>
                                <span className="text-[9px] bg-primary/20 text-primary px-1 rounded-sm">{status.staged.length}</span>
                            </div>
                            {status.staged.map((file: string) => (
                                <GitNavItem
                                    key={file}
                                    name={file}
                                    state="staged"
                                    onClick={() => handleFileClick(file, true)}
                                    onAction={() => handleAction('unstage', file)}
                                />
                            ))}
                        </div>
                    )}

                    {/* Unstaged Section */}
                    {status && (status.unstaged.length > 0 || status.untracked.length > 0) && (
                        <div>
                            <div className="px-3 py-1 flex items-center justify-between group cursor-pointer hover:bg-white/5">
                                <div className="flex items-center gap-1">
                                    <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
                                    <span className="text-[9px] font-bold text-muted-foreground/70 uppercase tracking-widest">Changes</span>
                                </div>
                                <span className="text-[9px] bg-muted/50 text-muted-foreground/60 px-1 rounded-sm">
                                    {status.unstaged.length + status.untracked.length}
                                </span>
                            </div>
                            {status.unstaged.map((file: string) => (
                                <GitNavItem
                                    key={file}
                                    name={file}
                                    state="modified"
                                    onClick={() => handleFileClick(file, false)}
                                    onAction={() => handleAction('stage', file)}
                                />
                            ))}
                            {status.untracked.map((file: string) => (
                                <GitNavItem
                                    key={file}
                                    name={file}
                                    state="untracked"
                                    onClick={() => handleFileClick(file, false)}
                                    onAction={() => handleAction('stage', file)}
                                />
                            ))}
                        </div>
                    )}

                    {!hasChanges && !loading && (
                        <div className="flex flex-col items-center justify-center p-8 opacity-20 text-center">
                            <Check className="w-8 h-8 mb-2" />
                            <p className="text-[10px] tracking-tight uppercase font-bold">Workspace Clean</p>
                        </div>
                    )}
                </div>

                {/* GRAPH / HISTORY SECTION */}
                <div className="mt-4 border-t border-border/10 pt-4 pb-8">
                    <div className="px-4 mb-3 flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">Graph</span>
                    </div>

                    <div className="relative ml-4">
                        {/* Continuous Vertical Line */}
                        {history.length > 0 && (
                            <div className="absolute left-[5px] top-2 bottom-4 w-[1px] bg-primary/30 z-0" />
                        )}

                        <div className="space-y-0 text-[11px]">
                            {history.map((commit: GitHistory, idx: number) => {
                                const isExpanded = expandedCommits.has(commit.hash);
                                return (
                                    <div key={commit.hash} className="mb-1">
                                        <div
                                            onClick={() => toggleCommit(commit.hash)}
                                            className="group relative flex items-start gap-4 py-2 hover:bg-white/5 cursor-pointer transition-colors max-w-full pr-4"
                                        >
                                            {/* Commit Dot (Solid) */}
                                            <div className="relative shrink-0 w-[11px] h-full flex flex-col items-center">
                                                <div className={cn(
                                                    "w-2.5 h-2.5 rounded-full z-10 mt-[3px] shadow-[0_0_8px_rgba(var(--primary),0.3)]",
                                                    idx === 0 ? "bg-primary scale-110 ring-4 ring-primary/20" : "bg-primary/60"
                                                )} />
                                            </div>

                                            <div className="flex-1 min-w-0">
                                                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mb-1">
                                                    <span className="font-bold text-foreground/90 truncate max-w-[80%] leading-tight capitalize">
                                                        {commit.message}
                                                    </span>

                                                    {/* Branch Pills */}
                                                    {commit.branches.map(branch => (
                                                        <div
                                                            key={branch}
                                                            className={cn(
                                                                "text-[9px] px-1.5 py-0.5 rounded-full font-bold flex items-center gap-1 shrink-0",
                                                                branch.includes('master') || branch.includes('main')
                                                                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                                                    : "bg-muted text-muted-foreground/70"
                                                            )}
                                                        >
                                                            <GitBranch className="w-2.5 h-2.5" />
                                                            {branch}
                                                        </div>
                                                    ))}
                                                </div>

                                                <div className="flex items-center gap-2 text-[9px] text-muted-foreground/50">
                                                    <span className="font-medium text-muted-foreground/70">{commit.author}</span>
                                                    <span>•</span>
                                                    <span>{commit.date}</span>
                                                    <span>•</span>
                                                    <span className="font-mono uppercase opacity-60 group-hover:opacity-100 transition-opacity">{commit.hash}</span>
                                                </div>
                                            </div>
                                            <ChevronDown className={cn("w-3 h-3 text-muted-foreground/30 transition-transform", isExpanded ? "" : "-rotate-90")} />
                                        </div>

                                        {/* Files list when expanded */}
                                        {isExpanded && (
                                            <div className="ml-[11px] border-l border-primary/20 pl-4 py-1 space-y-0.5">
                                                {commit.files.map(file => (
                                                    <GitNavItem
                                                        key={file}
                                                        name={file}
                                                        state="modified"
                                                        onClick={() => handleFileClick(file, false, commit.hash)}
                                                        onAction={() => { }} // No action for history files
                                                    />
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}

                            {history.length === 0 && !loading && (
                                <div className="py-8 text-center opacity-30 italic text-[10px] mr-4">
                                    No commit history yet
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Beta Footer */}
            <div className="px-4 py-2 border-t border-border/50 bg-muted/5 shrink-0">
                <div className="flex items-center gap-2 text-[9px] text-muted-foreground/40 justify-center uppercase tracking-[0.2em] font-bold">
                    <span>Arcturus SCM v2</span>
                </div>
            </div>
        </div>
    );
};

const GitNavItem: React.FC<{
    name: string;
    state: 'staged' | 'modified' | 'untracked';
    onClick: () => void;
    onAction: () => void;
}> = ({ name, state, onClick, onAction }) => {
    return (
        <div
            onClick={onClick}
            className="group flex items-center gap-2 px-3 py-1 hover:bg-white/5 transition-all cursor-pointer select-none overflow-hidden"
        >
            <FileCode className={cn(
                "w-3 h-3 shrink-0",
                state === 'staged' ? "text-green-400" : state === 'modified' ? "text-amber-400" : "text-blue-400"
            )} />
            <div className="flex-1 min-w-0">
                <p className="text-[10px] truncate font-bold text-foreground/80">{name.split(/[/\\]/).pop()}</p>
                <p className="text-[8px] truncate text-muted-foreground/40">{name.split(/[/\\]/).slice(0, -1).join('/') || './'}</p>
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 hover:bg-primary/20 hover:text-primary transition-all active:scale-95"
                    onClick={(e) => { e.stopPropagation(); onAction(); }}
                >
                    {state === 'staged' ? <Minus className="w-2.5 h-2.5" /> : <Plus className="w-2.5 h-2.5" />}
                </Button>
            </div>
            <span className={cn(
                "text-[8px] font-black uppercase tracking-tighter w-3 text-center shrink-0",
                state === 'staged' ? "text-green-500/50" : state === 'modified' ? "text-amber-500/50" : "text-blue-500/50"
            )}>
                {state === 'staged' ? 'A' : state === 'modified' ? 'M' : 'U'}
            </span>
        </div>
    );
};
