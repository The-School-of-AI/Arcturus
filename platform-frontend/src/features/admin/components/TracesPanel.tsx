import React, { useEffect, useState, useCallback } from 'react';
import { API_BASE } from '@/lib/api';
import axios from 'axios';
import { Activity, ExternalLink, AlertCircle, RefreshCw, Trash2, Download, ChevronDown, ChevronRight } from 'lucide-react';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';

const JAEGER_UI_BASE = 'http://localhost:16686';

function formatCost(val: unknown): string {
    const n = Number(val);
    if (Number.isNaN(n) || n <= 0) return '-';
    return `$${n.toFixed(6)}`;
}

function formatTokens(val: unknown): string {
    const n = Number(val);
    if (Number.isNaN(n) || n <= 0) return '-';
    return n.toLocaleString();
}

interface Trace {
    trace_id: string;
    session_id?: string | null;
    start_time: string;
    duration_ms: number;
    has_error: boolean;
    span_count: number;
    cost_usd?: number;
    input_tokens?: number;
    output_tokens?: number;
}

interface Session {
    session_id: string;
    start_time: string;
    end_time: string;
    span_count: number;
    total_cost_usd: number;
    agents: string[];
}

const SessionsSection: React.FC = () => {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [loading, setLoading] = useState(true);
    const [expanded, setExpanded] = useState(true);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [deletingAll, setDeletingAll] = useState(false);
    const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);
    const { flags } = useFeatureFlags();
    const costEnabled = flags.cost_tracking !== false;

    const fetchSessions = useCallback(async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/admin/sessions`, {
                params: { hours: 720, limit: 100 },
            });
            setSessions(res.data.sessions || []);
        } catch (e) {
            console.error('Failed to fetch sessions', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    const handleExport = async (sessionId: string) => {
        try {
            const res = await axios.get(`${API_BASE}/admin/data/${sessionId}`);
            const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `session_${sessionId}.json`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('Failed to export session', e);
        }
    };

    const handleDelete = async (sessionId: string) => {
        if (!window.confirm(`Delete all data for session ${sessionId}? This cannot be undone.`)) return;
        setDeletingId(sessionId);
        try {
            await axios.delete(`${API_BASE}/admin/data/${sessionId}`);
            setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
        } catch (e) {
            console.error('Failed to delete session', e);
        } finally {
            setDeletingId(null);
        }
    };

    const handleDeleteAll = async () => {
        if (!confirmDeleteAll) {
            setConfirmDeleteAll(true);
            return;
        }
        setDeletingAll(true);
        setConfirmDeleteAll(false);
        try {
            await axios.delete(`${API_BASE}/admin/data`);
            setSessions([]);
        } catch (e) {
            console.error('Failed to delete all watchtower data', e);
        } finally {
            setDeletingAll(false);
        }
    };

    const formatTimestamp = (ts: string) => {
        try {
            return new Date(ts).toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return ts;
        }
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="flex items-center gap-1.5 text-sm font-semibold text-foreground hover:text-primary transition-colors"
                >
                    {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    Sessions
                    <span className="text-xs font-normal text-muted-foreground ml-1">({sessions.length})</span>
                </button>
                <div className="flex items-center gap-2">
                    {confirmDeleteAll && (
                        <span className="text-xs text-red-400 mr-1">Click again to confirm</span>
                    )}
                    <button
                        onClick={handleDeleteAll}
                        disabled={deletingAll || sessions.length === 0}
                        className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 px-2 py-1.5 rounded border border-red-500/30 hover:border-red-400/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        onBlur={() => setConfirmDeleteAll(false)}
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                        {deletingAll ? 'Deleting...' : 'Delete All'}
                    </button>
                    <button
                        onClick={fetchSessions}
                        disabled={loading}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded border border-border hover:border-foreground/20 transition-colors"
                    >
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {expanded && (
                <>
                    {loading ? (
                        <div className="flex items-center justify-center p-6">
                            <Activity className="w-6 h-6 animate-pulse text-muted-foreground" />
                        </div>
                    ) : sessions.length === 0 ? (
                        <div className="text-sm text-muted-foreground text-center py-6 border rounded-lg border-border">
                            No sessions found.
                        </div>
                    ) : (
                        <div className="rounded-lg border border-border overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                    <thead>
                                        <tr className="bg-muted/50 text-muted-foreground">
                                            <th className="text-left px-3 py-2 font-medium">Session ID</th>
                                            <th className="text-left px-3 py-2 font-medium">Start</th>
                                            <th className="text-right px-3 py-2 font-medium">Spans</th>
                                            {costEnabled && <th className="text-right px-3 py-2 font-medium">Cost</th>}
                                            <th className="text-left px-3 py-2 font-medium">Agents</th>
                                            <th className="text-center px-3 py-2 font-medium">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {sessions.map((s) => (
                                            <tr key={s.session_id} className="hover:bg-muted/10 transition-colors">
                                                <td className="px-3 py-2 font-mono truncate max-w-[160px]" title={s.session_id}>
                                                    {s.session_id}
                                                </td>
                                                <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                                                    {formatTimestamp(s.start_time)}
                                                </td>
                                                <td className="px-3 py-2 text-right font-mono">{s.span_count}</td>
                                                {costEnabled && <td className="px-3 py-2 text-right font-mono">{formatCost(s.total_cost_usd)}</td>}
                                                <td className="px-3 py-2 text-muted-foreground max-w-[200px] truncate" title={s.agents.join(', ')}>
                                                    {s.agents.length > 0 ? s.agents.join(', ') : '-'}
                                                </td>
                                                <td className="px-3 py-2 text-center">
                                                    <div className="flex items-center justify-center gap-1.5">
                                                        <button
                                                            onClick={() => handleExport(s.session_id)}
                                                            className="p-1 text-muted-foreground hover:text-primary transition-colors rounded"
                                                            title="Export session data"
                                                        >
                                                            <Download className="w-3.5 h-3.5" />
                                                        </button>
                                                        <button
                                                            onClick={() => handleDelete(s.session_id)}
                                                            disabled={deletingId === s.session_id}
                                                            className="p-1 text-muted-foreground hover:text-red-400 transition-colors rounded disabled:opacity-40"
                                                            title="Delete session data"
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            <div className="bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground border-t border-border">
                                {sessions.length} session(s)
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export const TracesPanel: React.FC = () => {
    const [traces, setTraces] = useState<Trace[]>([]);
    const [loading, setLoading] = useState(true);
    const [purging, setPurging] = useState(false);
    const [confirmPurge, setConfirmPurge] = useState(false);
    const { flags } = useFeatureFlags();
    const costEnabled = flags.cost_tracking !== false;

    const fetchTraces = useCallback(async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/admin/traces`, { params: { limit: 50 } });
            setTraces(res.data.traces || []);
        } catch (e) {
            console.error('Failed to fetch traces', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchTraces();
    }, [fetchTraces]);

    const handlePurgeOrphans = async () => {
        if (!confirmPurge) {
            setConfirmPurge(true);
            return;
        }
        setPurging(true);
        setConfirmPurge(false);
        try {
            await axios.delete(`${API_BASE}/admin/traces/orphans`);
            await fetchTraces();
        } catch (e) {
            console.error('Failed to purge orphan traces', e);
        } finally {
            setPurging(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Activity className="w-8 h-8 animate-pulse text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <SessionsSection />

            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-foreground">Recent Traces</h3>
                    <div className="flex items-center gap-2">
                        {confirmPurge && (
                            <span className="text-xs text-red-400 mr-1">Click again to confirm</span>
                        )}
                        <button
                            onClick={handlePurgeOrphans}
                            disabled={purging}
                            className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 px-2 py-1.5 rounded border border-red-500/30 hover:border-red-400/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                            onBlur={() => setConfirmPurge(false)}
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                            {purging ? 'Purging...' : 'Purge Orphan Traces'}
                        </button>
                        <button
                            onClick={fetchTraces}
                            disabled={loading}
                            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded border border-border hover:border-foreground/20 transition-colors"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                        </button>
                        <a
                            href="http://localhost:16686"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-primary hover:underline flex items-center gap-1"
                        >
                            Open Jaeger <ExternalLink className="w-3 h-3" />
                        </a>
                    </div>
                </div>
                <div className="rounded-lg border border-border overflow-x-auto">
                    <table className="w-full text-sm min-w-[800px]">
                        <thead className="bg-muted/50">
                            <tr>
                                <th className="text-left p-2 font-medium">Trace ID</th>
                                <th className="text-left p-2 font-medium">Session ID</th>
                                <th className="text-left p-2 font-medium">Start</th>
                                <th className="text-right p-2 font-medium">Duration</th>
                                {costEnabled && <th className="text-right p-2 font-medium">Cost</th>}
                                {costEnabled && <th className="text-right p-2 font-medium">Input Tokens</th>}
                                {costEnabled && <th className="text-right p-2 font-medium">Output Tokens</th>}
                                <th className="text-center p-2 font-medium">Spans</th>
                                <th className="text-center p-2 font-medium">Error</th>
                            </tr>
                        </thead>
                        <tbody>
                            {traces.map((t) => (
                                <tr key={t.trace_id} className="border-t border-border hover:bg-muted/30">
                                    <td className="p-2 font-mono text-xs max-w-[140px]" title={t.trace_id}>
                                        <a
                                            href={`${JAEGER_UI_BASE}/trace/${t.trace_id}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-primary hover:underline truncate block flex items-center gap-1"
                                        >
                                            {t.trace_id}
                                            <ExternalLink className="w-3 h-3 shrink-0 inline" />
                                        </a>
                                    </td>
                                    <td className="p-2 font-mono text-xs truncate max-w-[100px] text-muted-foreground" title={t.session_id ?? ''}>
                                        {t.session_id || '-'}
                                    </td>
                                    <td className="p-2 text-muted-foreground text-xs">
                                        {t.start_time ? new Date(t.start_time).toLocaleString() : '-'}
                                    </td>
                                    <td className="p-2 text-right font-mono text-xs">{Math.round(t.duration_ms)}ms</td>
                                    {costEnabled && (
                                        <td className="p-2 text-right font-mono text-xs">
                                            {formatCost(t.cost_usd)}
                                        </td>
                                    )}
                                    {costEnabled && (
                                        <td className="p-2 text-right font-mono text-xs">
                                            {formatTokens(t.input_tokens)}
                                        </td>
                                    )}
                                    {costEnabled && (
                                        <td className="p-2 text-right font-mono text-xs">
                                            {formatTokens(t.output_tokens)}
                                        </td>
                                    )}
                                    <td className="p-2 text-center">{t.span_count}</td>
                                    <td className="p-2 text-center">
                                        {t.has_error ? (
                                            <AlertCircle className="w-4 h-4 text-red-500 inline" />
                                        ) : (
                                            <span className="text-muted-foreground">-</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {traces.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">No traces in the last 24 hours.</p>
                )}
            </div>
        </div>
    );
};
