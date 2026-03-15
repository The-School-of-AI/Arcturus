import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { AlertTriangle } from 'lucide-react';

interface ErrorSummary {
    error_count: number;
    by_agent: Record<string, { count: number; sample_trace_ids: string[] }>;
    hours: number;
}

export const ErrorsPanel: React.FC = () => {
    const [data, setData] = useState<ErrorSummary | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchErrors = async () => {
            try {
                const res = await axios.get(`${API_BASE}/admin/errors/summary`, { params: { hours: 24 } });
                setData(res.data);
            } catch (e) {
                console.error('Failed to fetch errors summary', e);
            } finally {
                setLoading(false);
            }
        };
        fetchErrors();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <AlertTriangle className="w-8 h-8 animate-pulse text-muted-foreground" />
            </div>
        );
    }

    if (!data) {
        return <p className="text-sm text-muted-foreground p-4">Failed to load error data.</p>;
    }

    return (
        <div className="space-y-6">
            <div className="rounded-lg border border-border p-4 bg-muted/20">
                <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
                    <AlertTriangle className="w-4 h-4" />
                    Total Errors (24h)
                </div>
                <p className="text-2xl font-bold text-foreground mt-1">{data.error_count}</p>
            </div>

            {Object.keys(data.by_agent).length > 0 ? (
                <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">By Agent / Span</h4>
                    <div className="rounded-lg border border-border overflow-hidden">
                        <table className="w-full text-sm">
                            <thead className="bg-muted/50">
                                <tr>
                                    <th className="text-left p-2 font-medium">Agent / Span</th>
                                    <th className="text-right p-2 font-medium">Count</th>
                                    <th className="text-left p-2 font-medium">Sample Traces</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.entries(data.by_agent).map(([agent, info]) => (
                                    <tr key={agent} className="border-t border-border">
                                        <td className="p-2">{agent}</td>
                                        <td className="p-2 text-right font-mono">{info.count}</td>
                                        <td className="p-2">
                                            <div className="flex flex-wrap gap-1">
                                                {info.sample_trace_ids.slice(0, 3).map((tid) => (
                                                    <span
                                                        key={tid}
                                                        className="font-mono text-xs text-muted-foreground truncate max-w-[80px]"
                                                        title={tid}
                                                    >
                                                        {tid.slice(0, 8)}…
                                                    </span>
                                                ))}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
                <p className="text-sm text-muted-foreground text-center py-4">No errors in the last 24 hours.</p>
            )}
        </div>
    );
};
