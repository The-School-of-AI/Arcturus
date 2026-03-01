// features/swarm/AgentPeekPanel.tsx
// Right inspector panel — mirrors WorkspacePanel in the Runs view.
// Primary: task metadata (title, status, deps, result) from the Zustand store.
// Secondary: live conversation log from /peek, when available.

import React, { useEffect, useState, useRef } from 'react';
import { X, Zap, CheckCircle2, Loader2, XCircle, Clock, FileText, MessageSquare, Terminal, Eye, Globe, Code } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useSwarmStore } from './useSwarmStore';
import { swarmApi } from './swarmApi';
import type { AgentLogEntry } from './types';

const PanelTab: React.FC<{ label: string; active: boolean; onClick: () => void; icon: React.ReactNode }> = ({ label, active, onClick, icon }) => (
    <button
        onClick={onClick}
        className={cn(
            "flex-1 flex items-center justify-center gap-2 py-3 text-[10px] font-bold uppercase tracking-tighter transition-all relative border-b border-border/50",
            active ? "text-primary bg-primary/5" : "text-muted-foreground hover:text-foreground"
        )}
    >
        {icon}
        {label}
        {active && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />}
    </button>
);

export const AgentPeekPanel: React.FC = () => {
    const activeRunId = useSwarmStore(s => s.activeRunId);
    const selectedAgentId = useSwarmStore(s => s.selectedAgentId);
    const setSelectedAgent = useSwarmStore(s => s.setSelectedAgent);
    const setInterventionOpen = useSwarmStore(s => s.setInterventionOpen);
    const tasks = useSwarmStore(s => s.tasks);

    const [log, setLog] = useState<AgentLogEntry[]>([]);
    const [tab, setTab] = useState<'overview' | 'output' | 'log' | 'web' | 'preview' | 'code' | 'stats'>('overview');
    const bottomRef = useRef<HTMLDivElement>(null);

    const selectedTask = tasks.find(t => t.assigned_to === selectedAgentId);
    const isActive = selectedTask?.status === 'in_progress';

    const parseResult = (r: string | null | undefined) => {
        if (!r) return null;
        try {
            return JSON.parse(r);
        } catch {
            try {
                // Safely convert Python dict string to JS object inside iframe or func
                const cleaned = r.replace(/\bTrue\b/g, 'true')
                    .replace(/\bFalse\b/g, 'false')
                    .replace(/\bNone\b/g, 'null');
                return new Function("return " + cleaned)();
            } catch {
                return null;
            }
        }
    };

    const parsedResult = parseResult(selectedTask?.result);
    const isCodeAgent = ['retrieveragent', 'thinkeragent', 'coderagent', 'distilleragent'].some(a => selectedTask?.assigned_to.toLowerCase().includes(a));

    const displayTokens = (typeof parsedResult?.total_tokens === 'number' ? parsedResult.total_tokens : null)
        ?? ((typeof parsedResult?.input_tokens === 'number' && typeof parsedResult?.output_tokens === 'number') ? (parsedResult.input_tokens + parsedResult.output_tokens) : null)
        ?? selectedTask?.token_used
        ?? 0;

    const displayCost = (typeof parsedResult?.cost === 'number' ? parsedResult.cost : null)
        ?? selectedTask?.cost_usd
        ?? 0;

    // Fetch conversation log
    useEffect(() => {
        if (!activeRunId || !selectedAgentId) { setLog([]); return; }
        const fetchLog = async () => {
            try {
                const entries = await swarmApi.peekAgent(activeRunId, selectedAgentId);
                setLog(entries);
            } catch { /* ignore */ }
        };
        fetchLog();
        if (!isActive) return;
        const interval = setInterval(fetchLog, 2000);
        return () => clearInterval(interval);
    }, [activeRunId, selectedAgentId, isActive]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [log]);

    // Reset tab when agent changes
    useEffect(() => { setTab('overview'); }, [selectedAgentId]);

    if (!selectedAgentId || !selectedTask) return null;

    return (
        <div className="h-full flex flex-col transition-all duration-300 relative bg-background">

            {/* Header matches WorkspacePanel perfectly */}
            <div className="p-4 border-b border-border glass backdrop-blur z-10 flex flex-col gap-2">
                <div className="flex items-center gap-2">
                    <div className={cn(
                        "w-2 h-2 rounded-full",
                        selectedTask.status === 'completed' ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]" :
                            selectedTask.status === 'failed' ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]" :
                                "bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.4)]"
                    )} />
                    <div className="flex flex-col min-w-0">
                        <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-foreground leading-none truncate">
                            {selectedAgentId}
                        </span>
                        <span className="text-[9px] text-muted-foreground font-medium uppercase tracking-widest mt-1 opacity-70">
                            {selectedTask.status}
                        </span>
                    </div>

                    <div className="ml-auto flex items-center gap-1 shrink-0">
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-primary hover:bg-primary/10"
                            title="Intervene" onClick={() => setInterventionOpen(true)}>
                            <Zap className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-red-500 hover:bg-red-500/10"
                            onClick={() => setSelectedAgent(null)}>
                            <X className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </div>

                {/* Truncated Prompt Header (like in WorkspacePanel) */}
                <div className="text-xs text-muted-foreground line-clamp-2 font-medium border-l-2 border-primary/20 pl-2 mt-2">
                    {selectedTask.title}
                </div>
            </div>

            {/* Tab bar — OVERVIEW / OUTPUT / LOG / WEB / PREVIEW */}
            <div className="flex items-center border-b border-border px-2 shrink-0">
                <PanelTab label="Overview" active={tab === 'overview'} onClick={() => setTab('overview')} icon={<Terminal className="w-3 h-3" />} />
                <PanelTab
                    label={isCodeAgent ? "Code" : "Output"}
                    active={tab === 'code'}
                    onClick={() => setTab('code')}
                    icon={isCodeAgent ? <Code className="w-3 h-3" /> : <Terminal className="w-3 h-3" />}
                />
                <PanelTab label="Log" active={tab === 'log'} onClick={() => setTab('log')} icon={<MessageSquare className="w-3 h-3" />} />
                <PanelTab label="Web" active={tab === 'web'} onClick={() => setTab('web')} icon={<Globe className="w-3 h-3" />} />
                <PanelTab label="Preview" active={tab === 'preview'} onClick={() => setTab('preview')} icon={<Eye className="w-3 h-3" />} />
                <PanelTab label="Stats" active={tab === 'stats'} onClick={() => setTab('stats')} icon={<Terminal className="w-3 h-3" />} />
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative">
                {tab === 'overview' && (
                    <div className="p-4 space-y-6 overflow-y-auto h-full font-mono text-sm select-text">

                        {/* Section: Task Title (replaces User Query style) */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between pb-2 border-b border-border/50">
                                <div className="flex items-center gap-2">
                                    <Terminal className="w-3 h-3 text-primary" />
                                    <span className="text-[10px] font-bold uppercase tracking-widest text-foreground">Task Goal</span>
                                </div>
                            </div>
                            <div className="p-3 bg-slate-50 dark:bg-muted/50 rounded-lg text-foreground/90 leading-relaxed text-[11px] border border-border/50 select-text">
                                {selectedTask.title}
                            </div>
                        </div>

                        {/* Section: I/O Context */}
                        <div className="grid grid-cols-2 gap-2 select-none">
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1 italic opacity-70">Inputs (Reads)</div>
                                <div className="flex flex-wrap gap-1">
                                    {selectedTask.dependencies?.length ? selectedTask.dependencies.map((r: string) => (
                                        <span key={r} className="text-[9px] px-1.5 py-0.5 bg-blue-500/5 text-blue-600 dark:text-blue-400 border border-blue-500/20 rounded font-bold uppercase select-text">
                                            {r}
                                        </span>
                                    )) : <span className="text-[10px] text-muted-foreground italic">None</span>}
                                </div>
                            </div>
                            <div className="space-y-1">
                                <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest mb-1 italic opacity-70">Outputs (Writes)</div>
                                <div className="flex flex-wrap gap-1">
                                    {selectedTask.result ? (
                                        <span className="text-[9px] px-1.5 py-0.5 bg-green-500/5 text-green-600 dark:text-green-400 border border-green-500/20 rounded font-bold uppercase select-text">
                                            Result Generated
                                        </span>
                                    ) : <span className="text-[10px] text-muted-foreground italic">Pending</span>}
                                </div>
                            </div>
                        </div>

                        {/* Section: Performance */}
                        <div className="p-3 bg-slate-50 dark:bg-muted/50 rounded-lg flex items-center justify-between border border-border/50 select-none">
                            <div className="flex items-center gap-2">
                                <Clock className="w-3.5 h-3.5 text-primary" />
                                <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-tighter">Tokens</span>
                                <span className="text-xs text-foreground font-mono font-bold">
                                    {displayTokens.toLocaleString()}
                                </span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-tighter">Cost</span>
                                <span className="text-xs text-emerald-600 dark:text-emerald-400 font-mono font-bold">
                                    ${displayCost.toFixed(6)}
                                </span>
                            </div>
                        </div>

                        {/* Section: Execution Output */}
                        <div className="space-y-2">
                            <div className="flex items-center gap-2 pb-2 border-b border-border/50">
                                <Terminal className="w-3 h-3 text-primary" />
                                <span className="text-[10px] font-bold uppercase tracking-widest text-foreground">Execution Output</span>
                            </div>
                            {selectedTask.result ? (
                                <div className="space-y-1 select-text">
                                    {(() => {
                                        if (!parsedResult) {
                                            return (
                                                <div className="text-[10px] text-muted-foreground italic pl-2 opacity-50 py-2">
                                                    No formatted keys to display here.
                                                </div>
                                            );
                                        }
                                        return (
                                            <div className="mt-2 space-y-1">
                                                {parsedResult.status && (
                                                    <div className="flex flex-col gap-1 mb-2">
                                                        <div className="text-[10px] text-muted-foreground uppercase opacity-70 select-none">STATUS</div>
                                                        <div className="text-foreground/80 lowercase text-[11px] font-mono">{parsedResult.status}</div>
                                                    </div>
                                                )}
                                                {parsedResult.type && (
                                                    <div className="flex flex-col gap-1 mb-2">
                                                        <div className="text-[10px] text-muted-foreground uppercase opacity-70 select-none">TYPE</div>
                                                        <div className="text-foreground/80 text-[11px] font-mono">{parsedResult.type}</div>
                                                    </div>
                                                )}
                                                {parsedResult.executed_model && (
                                                    <div className="flex justify-between text-[11px] py-1 border-b border-border/50 bg-primary/5 px-1 rounded">
                                                        <span className="text-primary font-bold select-none">model</span>
                                                        <span className="text-foreground font-bold truncate max-w-[150px]">{parsedResult.executed_model}</span>
                                                    </div>
                                                )}
                                                {Object.entries(parsedResult).slice(0, 5).map(([k, v]) => {
                                                    if (typeof v === 'object' || String(v).length > 200 || ['status', 'type', 'executed_model'].includes(k)) return null;
                                                    return (
                                                        <div key={k} className="flex justify-between text-[11px] py-0.5 border-b border-border/50">
                                                            <span className="text-muted-foreground select-none">{k}</span>
                                                            <span className="text-foreground truncate max-w-[200px] font-mono">{String(v)}</span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        );
                                    })()}
                                </div>
                            ) : (
                                <p className="text-xs text-muted-foreground italic opacity-50 pl-2">
                                    No output generated yet...
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {tab === 'code' && (
                    <div className="h-full overflow-y-auto p-4 space-y-6 select-text">
                        {(() => {
                            if (!selectedTask.result) {
                                return (
                                    <div className="text-xs text-muted-foreground italic opacity-50 pl-2">
                                        No data available yet...
                                    </div>
                                );
                            }

                            if (!parsedResult) {
                                return (
                                    <div className="space-y-4">
                                        <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest flex items-center gap-2 mb-2">
                                            <Terminal className="w-3 h-3" />
                                            RAW OUTPUT
                                        </div>
                                        <div className="rounded-lg overflow-hidden border border-border/20 bg-background/40 p-3 text-xs font-mono text-foreground/90 overflow-x-auto whitespace-pre-wrap leading-relaxed shadow-inner">
                                            {selectedTask.result}
                                        </div>
                                    </div>
                                );
                            }

                            const codeKeys = Object.keys(parsedResult).filter(k => k === 'code_variants' || k === 'code' || (typeof parsedResult[k] === 'string' && parsedResult[k].includes('\n') && parsedResult[k].includes('def ')));
                            const dataKeys = Object.keys(parsedResult).filter(k => !codeKeys.includes(k) && !['status', 'type', 'executed_model', 'input_tokens', 'output_tokens', 'cost', 'total_tokens'].includes(k));

                            return (
                                <div className="space-y-4">
                                    {codeKeys.length > 0 && (
                                        <div className="border border-border rounded-lg overflow-hidden bg-muted/30">
                                            <div className="px-4 py-3 bg-primary/10 border-b border-border flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    <span className="text-sm font-bold text-primary uppercase tracking-wider">CODE OUTPUT</span>
                                                </div>
                                            </div>
                                            <div className="p-4 space-y-3">
                                                {codeKeys.map(key => (
                                                    <div key={key} className="rounded-lg overflow-hidden border border-border/50 bg-background/50">
                                                        <div className="px-3 py-1.5 bg-muted/50 border-b border-border/50 flex items-center justify-between">
                                                            <span className="text-[10px] font-mono font-bold text-muted-foreground">{key}</span>
                                                        </div>
                                                        <pre className="p-3 text-xs font-mono text-foreground/90 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                                                            {typeof parsedResult[key] === 'object' ? JSON.stringify(parsedResult[key], null, 2) : String(parsedResult[key])}
                                                        </pre>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {dataKeys.length > 0 && (
                                        <div className="p-4 space-y-3">
                                            <div className="text-[10px] uppercase text-muted-foreground font-bold tracking-widest flex items-center gap-2">
                                                <Terminal className="w-3 h-3" />
                                                Output Data
                                            </div>
                                            {dataKeys.map(key => (
                                                <div key={key} className="space-y-2">
                                                    <div className="text-[9px] text-muted-foreground font-mono uppercase font-bold tracking-wider">
                                                        {key}
                                                    </div>
                                                    <div className="rounded-lg overflow-hidden border border-border/20 bg-background/40 p-3 text-xs font-mono text-foreground/90 overflow-x-auto whitespace-pre-wrap leading-relaxed shadow-inner">
                                                        {typeof parsedResult[key] === 'object' ? (
                                                            <pre className="text-foreground/80">{JSON.stringify(parsedResult[key], null, 2)}</pre>
                                                        ) : (
                                                            <div className="text-foreground/80">{String(parsedResult[key])}</div>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })()}
                    </div>
                )}

                {tab === 'stats' && (
                    <div className="p-4 font-mono text-xs space-y-4 overflow-y-auto h-full select-text">
                        <div className="text-green-400 font-bold border-b border-border pb-2 mb-2 select-none">
                            # Node Execution Details
                        </div>
                        <div className="flex flex-col gap-1 border-l-2 border-primary/30 pl-3 py-1 bg-muted/50 rounded-r hover:bg-muted transition-colors">
                            <div className="text-[10px] text-muted-foreground uppercase tracking-widest opacity-70 select-none">STATUS</div>
                            <div className="text-foreground whitespace-pre-wrap break-words font-mono">{selectedTask.status}</div>
                        </div>
                        <div className="flex flex-col gap-1 border-l-2 border-primary/30 pl-3 py-1 bg-muted/50 rounded-r hover:bg-muted transition-colors">
                            <div className="text-[10px] text-muted-foreground uppercase tracking-widest opacity-70 select-none">TYPE</div>
                            <div className="text-foreground whitespace-pre-wrap break-words font-mono">{selectedTask.assigned_to}</div>
                        </div>

                        <div className="mt-4 pt-4 border-t border-border">
                            <div className="text-yellow-400 font-bold mb-2 select-none"># Results</div>
                            {parsedResult && parsedResult.executed_model && (
                                <div className="flex justify-between border-b border-border/50 py-1 bg-primary/5 px-1 rounded">
                                    <span className="text-primary font-bold select-none">model</span>
                                    <span className="text-foreground font-bold">{parsedResult.executed_model}</span>
                                </div>
                            )}
                            <div className="flex justify-between border-b border-border/50 py-1 text-[11px]">
                                <span className="text-muted-foreground select-none">tokens (used)</span>
                                <span className="text-foreground font-mono">{displayTokens}</span>
                            </div>
                            <div className="flex justify-between border-b border-border/50 py-1 text-[11px]">
                                <span className="text-muted-foreground select-none">cost (usd)</span>
                                <span className="text-foreground font-mono">{displayCost.toFixed(6)}</span>
                            </div>
                            {parsedResult && ['input_tokens', 'output_tokens'].map(k => {
                                if (parsedResult[k] !== undefined) {
                                    return (
                                        <div key={k} className="flex justify-between border-b border-border/50 py-1 text-[11px]">
                                            <span className="text-muted-foreground select-none">{k}</span>
                                            <span className="text-foreground font-mono">{String(parsedResult[k])}</span>
                                        </div>
                                    );
                                }
                                return null;
                            })}
                        </div>
                    </div>
                )}

                {tab === 'log' && (
                    <div className="h-full overflow-y-auto p-4 space-y-2">
                        {log.length === 0 ? (
                            <div className="flex flex-col items-center justify-center pt-16 text-muted-foreground opacity-50">
                                <MessageSquare className="w-8 h-8 mb-2 opacity-20" />
                                <p className="text-xs text-center">
                                    {isActive ? 'Waiting for agent activity…' : 'No conversation log available.'}
                                </p>
                            </div>
                        ) : (
                            log.map((entry, i) => (
                                <div key={i}
                                    className={cn(
                                        'p-3 rounded-xl border',
                                        entry.role === 'assistant'
                                            ? 'bg-primary/5 text-foreground border-primary/20'
                                            : entry.role === 'system'
                                                ? 'bg-muted/30 text-muted-foreground italic border-transparent'
                                                : 'bg-muted/50 text-foreground ml-6 border-border/50',
                                    )}>
                                    <span className={cn(
                                        'block text-[9px] font-bold uppercase tracking-widest mb-1.5',
                                        entry.role === 'assistant' ? 'text-primary' : 'text-muted-foreground',
                                    )}>
                                        {entry.role}
                                    </span>
                                    <p className="whitespace-pre-wrap break-words text-[11px] leading-relaxed font-mono">
                                        {entry.content}
                                    </p>
                                </div>
                            ))
                        )}
                        <div ref={bottomRef} className="pb-4" />
                    </div>
                )}

                {tab === 'web' && (
                    <div className="h-full flex flex-col p-4 bg-muted/10 items-center justify-center text-muted-foreground">
                        <Globe className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm font-medium">Web Explorer API</p>
                        <p className="text-xs opacity-70">URLs scraped by this agent will appear here.</p>
                    </div>
                )}

                {tab === 'preview' && (
                    <div className="h-full p-6 overflow-auto bg-card select-text">
                        {(() => {
                            let formatContent: string | null = null;
                            let contentType: 'html' | 'markdown' = 'markdown';

                            const cleanContent = (value: string) => {
                                return value
                                    .replace(/\\n/g, '\n')
                                    .replace(/\\t/g, '\t')
                                    .replace(/\\'/g, "'")
                                    .replace(/\\"/g, '"');
                            };

                            const isHtml = (value: string) => {
                                return value.includes('<div') || value.includes('<h1') ||
                                    value.includes('<p>') || value.includes('<html') ||
                                    value.includes('<table') || value.includes('<ul');
                            };

                            try {
                                let r = selectedTask.result;
                                if (r) {
                                    if (typeof r === 'string' && r.trim().startsWith('{') && r.trim().endsWith('}')) {
                                        r = r.replace(/'/g, '"').replace(/True/g, 'true').replace(/False/g, 'false').replace(/None/g, 'null');
                                    }
                                    const parsed = typeof r === 'string' ? JSON.parse(r) : r;

                                    if (parsed && typeof parsed === 'object') {
                                        // PASS 1: Look for any key containing HTML content
                                        for (const [key, value] of Object.entries(parsed)) {
                                            if (typeof value === 'string' && value.length > 100 && isHtml(value)) {
                                                formatContent = cleanContent(value);
                                                contentType = 'html';
                                                break;
                                            }
                                        }

                                        // PASS 2: If no HTML found, look for keys starting with 'formatted_'
                                        if (!formatContent) {
                                            const formattedKeys = Object.keys(parsed).filter(k => k.startsWith('formatted_'));
                                            for (const key of formattedKeys) {
                                                const value = parsed[key as keyof typeof parsed];
                                                if (typeof value === 'string' && value.length > 50) {
                                                    const cleaned = cleanContent(value);
                                                    formatContent = cleaned;
                                                    contentType = isHtml(cleaned) ? 'html' : 'markdown';
                                                    break;
                                                }
                                            }
                                        }

                                        // PASS 3: Fallback to markdown/content keys
                                        if (!formatContent) {
                                            const fallbackKeys = ['markdown_report', 'markdown', 'report', 'content', 'result'];
                                            for (const key of fallbackKeys) {
                                                const value = parsed[key as keyof typeof parsed];
                                                if (typeof value === 'string' && value.trim()) {
                                                    formatContent = cleanContent(value);
                                                    contentType = isHtml(formatContent) ? 'html' : 'markdown';
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                }
                            } catch {
                                // If parsing fails, try raw string
                                if (selectedTask.result && typeof selectedTask.result === 'string') {
                                    formatContent = cleanContent(selectedTask.result);
                                    contentType = isHtml(formatContent) ? 'html' : 'markdown';
                                }
                            }

                            if (formatContent) {
                                return (
                                    <div className="preview-content bg-muted p-6 rounded-lg border border-border select-text">
                                        <style>{`
                                            .preview-content h1 { font-size: 1.75rem; font-weight: bold; color: hsl(var(--primary)); margin-bottom: 1rem; }
                                            .preview-content h2 { font-size: 1.5rem; font-weight: bold; color: hsl(var(--primary)); margin-top: 1.5rem; margin-bottom: 0.75rem; border-bottom: 1px solid hsl(var(--border)); padding-bottom: 0.5rem; }
                                            .preview-content h3 { font-size: 1.25rem; font-weight: bold; color: hsl(var(--foreground)); margin-top: 1rem; margin-bottom: 0.5rem; }
                                            .preview-content h4 { font-size: 1.1rem; font-weight: 600; color: hsl(var(--muted-foreground)); margin-top: 0.75rem; margin-bottom: 0.5rem; }
                                            .preview-content p { color: hsl(var(--muted-foreground)); line-height: 1.6; margin-bottom: 0.75rem; }
                                            .preview-content ul, .preview-content ol { color: hsl(var(--muted-foreground)); padding-left: 1.5rem; margin-bottom: 1rem; }
                                            .preview-content li { margin-bottom: 0.25rem; }
                                            .preview-content table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
                                            .preview-content th { background: hsl(var(--muted)); color: hsl(var(--primary)); padding: 0.75rem; text-align: left; border: 1px solid hsl(var(--border)); font-weight: 600; }
                                            .preview-content td { padding: 0.75rem; border: 1px solid hsl(var(--border)); color: hsl(var(--muted-foreground)); }
                                            .preview-content tr:nth-child(even) td { background: hsl(var(--background)); }
                                            .preview-content strong, .preview-content b { color: hsl(var(--primary)); font-weight: 600; }
                                            .preview-content i, .preview-content em { color: hsl(var(--muted-foreground)); font-style: italic; }
                                            .preview-content a { color: #60a5fa; text-decoration: underline; }
                                            .preview-content code { background: hsl(var(--background)); padding: 0.2rem 0.4rem; border-radius: 4px; color: hsl(var(--primary)); border: 1px solid hsl(var(--border)); }
                                            .preview-content pre { background: hsl(var(--background)); padding: 1rem; border-radius: 8px; overflow-x: auto; border: 1px solid hsl(var(--border)); }
                                            .preview-content blockquote { border-left: 3px solid hsl(var(--primary)); padding-left: 1rem; color: hsl(var(--muted-foreground)); font-style: italic; }
                                            .preview-content .report { color: hsl(var(--foreground)); }
                                        `}</style>
                                        {contentType === 'html' ? (
                                            <div dangerouslySetInnerHTML={{ __html: formatContent }} />
                                        ) : (
                                            <div className="whitespace-pre-wrap">{formatContent}</div>
                                        )}
                                    </div>
                                );
                            }

                            return (
                                <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-4">
                                    <Eye className="w-12 h-12 opacity-30" />
                                    <div>
                                        <p className="text-sm font-medium">No formatted Output</p>
                                        <p className="text-xs opacity-70">Agent did not produce Markdown or HTML content.</p>
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                )}


            </div>
        </div >
    );
};
