import React, { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api';
import axios from 'axios';
import { Activity, ExternalLink, AlertCircle } from 'lucide-react';

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

export const TracesPanel: React.FC = () => {
    const [traces, setTraces] = useState<Trace[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchTraces = async () => {
            try {
                const res = await axios.get(`${API_BASE}/admin/traces`, { params: { limit: 50 } });
                setTraces(res.data.traces || []);
            } catch (e) {
                console.error('Failed to fetch traces', e);
            } finally {
                setLoading(false);
            }
        };
        fetchTraces();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Activity className="w-8 h-8 animate-pulse text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-foreground">Recent Traces</h3>
                <a
                    href="http://localhost:16686"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                    Open Jaeger <ExternalLink className="w-3 h-3" />
                </a>
            </div>
            <div className="rounded-lg border border-border overflow-x-auto">
                <table className="w-full text-sm min-w-[800px]">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className="text-left p-2 font-medium">Trace ID</th>
                            <th className="text-left p-2 font-medium">Session ID</th>
                            <th className="text-left p-2 font-medium">Start</th>
                            <th className="text-right p-2 font-medium">Duration</th>
                            <th className="text-right p-2 font-medium">Cost</th>
                            <th className="text-right p-2 font-medium">Input Tokens</th>
                            <th className="text-right p-2 font-medium">Output Tokens</th>
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
                                <td className="p-2 text-right font-mono text-xs">
                                    {formatCost(t.cost_usd)}
                                </td>
                                <td className="p-2 text-right font-mono text-xs">
                                    {formatTokens(t.input_tokens)}
                                </td>
                                <td className="p-2 text-right font-mono text-xs">
                                    {formatTokens(t.output_tokens)}
                                </td>
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
    );
};
