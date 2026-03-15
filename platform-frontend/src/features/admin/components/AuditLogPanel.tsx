import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { Activity, RefreshCw, Filter, Trash2, Download } from 'lucide-react';

interface AuditEntry {
    timestamp: string;
    actor: string;
    action: string;
    resource: string;
    old_value: unknown;
    new_value: unknown;
    context: Record<string, unknown>;
}

const ACTION_COLORS: Record<string, string> = {
    feature_toggle: 'text-blue-400',
    feature_delete: 'text-red-400',
    cache_flush: 'text-yellow-400',
    throttle_update: 'text-orange-400',
    data_export: 'text-green-400',
    data_delete: 'text-red-500',
};

const ACTION_OPTIONS = [
    { value: '', label: 'All Actions' },
    { value: 'feature_toggle', label: 'Feature Toggle' },
    { value: 'feature_delete', label: 'Feature Delete' },
    { value: 'cache_flush', label: 'Cache Flush' },
    { value: 'throttle_update', label: 'Throttle Update' },
    { value: 'data_export', label: 'Data Export' },
    { value: 'data_delete', label: 'Data Delete' },
];

export const AuditLogPanel: React.FC = () => {
    const [entries, setEntries] = useState<AuditEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionFilter, setActionFilter] = useState('');
    const [hours, setHours] = useState(24);

    const fetchAudit = useCallback(async () => {
        setLoading(true);
        try {
            const params: Record<string, string | number> = { hours, limit: 100 };
            if (actionFilter) params.action = actionFilter;
            const res = await axios.get(`${API_BASE}/admin/audit`, { params });
            setEntries(res.data.entries || []);
        } catch (e) {
            console.error('Failed to fetch audit log', e);
        } finally {
            setLoading(false);
        }
    }, [hours, actionFilter]);

    useEffect(() => {
        fetchAudit();
    }, [fetchAudit]);

    const formatTimestamp = (ts: string) => {
        try {
            const d = new Date(ts);
            return d.toLocaleString(undefined, {
                month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit',
            });
        } catch {
            return ts;
        }
    };

    const formatValue = (v: unknown): string => {
        if (v === null || v === undefined) return '—';
        if (typeof v === 'boolean') return v ? 'true' : 'false';
        if (typeof v === 'object') return JSON.stringify(v);
        return String(v);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Activity className="w-8 h-8 animate-pulse text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-sm font-semibold">Audit Log</h2>
                    <p className="text-xs text-muted-foreground mt-1">
                        All state-changing admin actions logged with actor, action, and values
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={actionFilter}
                        onChange={(e) => setActionFilter(e.target.value)}
                        className="text-xs bg-background border border-border rounded px-2 py-1.5 text-foreground"
                    >
                        {ACTION_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                    <select
                        value={hours}
                        onChange={(e) => setHours(Number(e.target.value))}
                        className="text-xs bg-background border border-border rounded px-2 py-1.5 text-foreground"
                    >
                        <option value={1}>1h</option>
                        <option value={6}>6h</option>
                        <option value={24}>24h</option>
                        <option value={168}>7d</option>
                    </select>
                    <button
                        onClick={fetchAudit}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded border border-border hover:border-foreground/20 transition-colors"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* entries table */}
            {entries.length === 0 ? (
                <div className="text-sm text-muted-foreground text-center py-8 border rounded-lg border-border">
                    <Filter className="w-6 h-6 mx-auto mb-2 opacity-50" />
                    No audit entries found for the selected time window.
                </div>
            ) : (
                <div className="rounded-lg border border-border overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                            <thead>
                                <tr className="bg-muted/50 text-muted-foreground">
                                    <th className="text-left px-4 py-2.5 font-medium">Time</th>
                                    <th className="text-left px-4 py-2.5 font-medium">Actor</th>
                                    <th className="text-left px-4 py-2.5 font-medium">Action</th>
                                    <th className="text-left px-4 py-2.5 font-medium">Resource</th>
                                    <th className="text-left px-4 py-2.5 font-medium">Old → New</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {entries.map((entry, i) => (
                                    <tr key={i} className="hover:bg-muted/10 transition-colors">
                                        <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">
                                            {formatTimestamp(entry.timestamp)}
                                        </td>
                                        <td className="px-4 py-2.5 font-mono">
                                            {entry.actor}
                                        </td>
                                        <td className={`px-4 py-2.5 font-mono font-medium ${ACTION_COLORS[entry.action] || 'text-foreground'}`}>
                                            {entry.action === 'data_delete' && <Trash2 className="w-3 h-3 inline mr-1" />}
                                            {entry.action === 'data_export' && <Download className="w-3 h-3 inline mr-1" />}
                                            {entry.action}
                                        </td>
                                        <td className="px-4 py-2.5 font-mono text-muted-foreground max-w-[200px] truncate">
                                            {entry.resource}
                                        </td>
                                        <td className="px-4 py-2.5 font-mono max-w-[300px]">
                                            <span className="text-red-400">{formatValue(entry.old_value)}</span>
                                            <span className="text-muted-foreground mx-1">→</span>
                                            <span className="text-green-400">{formatValue(entry.new_value)}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="bg-muted/30 px-4 py-2 text-xs text-muted-foreground border-t border-border">
                        {entries.length} entries in last {hours}h
                    </div>
                </div>
            )}
        </div>
    );
};
