import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { DollarSign, TrendingUp } from 'lucide-react';

interface CostSummary {
    total_cost_usd: number;
    trace_count: number;
    by_agent: Record<string, number>;
    by_model: Record<string, number>;
    by_trace?: { trace_id: string; cost_usd: number }[];
    hours: number;
}

export const CostPanel: React.FC = () => {
    const [data, setData] = useState<CostSummary | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchCost = async () => {
            try {
                const res = await axios.get(`${API_BASE}/admin/cost/summary`, {
                    params: { hours: 24, group_by: 'trace' },
                });
                setData(res.data);
            } catch (e) {
                console.error('Failed to fetch cost summary', e);
            } finally {
                setLoading(false);
            }
        };
        fetchCost();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <DollarSign className="w-8 h-8 animate-pulse text-muted-foreground" />
            </div>
        );
    }

    if (!data) {
        return <p className="text-sm text-muted-foreground p-4">Failed to load cost data.</p>;
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-border p-4 bg-muted/20">
                    <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
                        <DollarSign className="w-4 h-4" />
                        Total Cost (24h)
                    </div>
                    <p className="text-2xl font-bold text-foreground mt-1">
                        ${data.total_cost_usd.toFixed(6)}
                    </p>
                </div>
                <div className="rounded-lg border border-border p-4 bg-muted/20">
                    <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-wider">
                        <TrendingUp className="w-4 h-4" />
                        Traces with LLM
                    </div>
                    <p className="text-2xl font-bold text-foreground mt-1">{data.trace_count}</p>
                </div>
            </div>

            {Object.keys(data.by_agent).length > 0 && (
                <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">By Agent</h4>
                    <div className="rounded-lg border border-border overflow-hidden">
                        <table className="w-full text-sm">
                            <tbody>
                                {Object.entries(data.by_agent).map(([agent, cost]) => (
                                    <tr key={agent} className="border-t border-border first:border-t-0">
                                        <td className="p-2">{agent}</td>
                                        <td className="p-2 text-right font-mono">${cost.toFixed(6)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {Object.keys(data.by_model).length > 0 && (
                <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase mb-2">By Model</h4>
                    <div className="rounded-lg border border-border overflow-hidden">
                        <table className="w-full text-sm">
                            <tbody>
                                {Object.entries(data.by_model).map(([model, cost]) => (
                                    <tr key={model} className="border-t border-border first:border-t-0">
                                        <td className="p-2">{model}</td>
                                        <td className="p-2 text-right font-mono">${cost.toFixed(6)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {data.total_cost_usd === 0 && data.trace_count === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">No cost data in the last 24 hours.</p>
            )}
        </div>
    );
};
