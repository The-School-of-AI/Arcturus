import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { Database, RefreshCw, Trash2, Activity, CheckCircle, XCircle, HardDrive, Zap } from 'lucide-react';

interface CacheEntry {
    name: string;
    description: string;
    flushable: boolean;
    files?: number;
    size_mb?: number;
    sessions?: number;
    /** Semantic cache: entries, hits, misses, hit_rate, enabled */
    entries?: number;
    max_entries?: number;
    hits?: number;
    misses?: number;
    hit_rate?: number;
    enabled?: boolean;
}

export const CachePanel: React.FC = () => {
    const [caches, setCaches] = useState<CacheEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [flushing, setFlushing] = useState<string | null>(null);
    const [flushResult, setFlushResult] = useState<{ name: string; message: string } | null>(null);

    const fetchCaches = useCallback(async () => {
        try {
            const res = await axios.get(`${API_BASE}/admin/cache`);
            setCaches(res.data.caches || []);
        } catch (e) {
            console.error('Failed to fetch caches', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchCaches();
    }, [fetchCaches]);

    const flushCache = async (name: string) => {
        setFlushing(name);
        setFlushResult(null);
        try {
            const res = await axios.post(`${API_BASE}/admin/cache/${name}/flush`);
            setFlushResult({ name, message: res.data.message || 'Flushed successfully' });
            await fetchCaches();
        } catch (e: unknown) {
            const detail = axios.isAxiosError(e) ? e.response?.data?.detail : 'Flush failed';
            setFlushResult({ name, message: String(detail) });
        } finally {
            setFlushing(null);
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
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-sm font-semibold">Cache Management</h2>
                    <p className="text-xs text-muted-foreground mt-1">
                        View cache status and flush where safe. Settings and semantic_cache are flushable.
                    </p>
                </div>
                <button
                    onClick={fetchCaches}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded border border-border hover:border-foreground/20 transition-colors"
                >
                    <RefreshCw className="w-3.5 h-3.5" />
                </button>
            </div>

            {flushResult && (
                <div className="flex items-center gap-2 p-3 rounded-lg border border-border bg-muted/20 text-sm">
                    <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
                    <span>
                        <span className="font-mono font-medium">{flushResult.name}</span>
                        {' — '}
                        {flushResult.message}
                    </span>
                </div>
            )}

            <div className="rounded-lg border border-border divide-y divide-border">
                {caches.map((cache) => (
                    <div
                        key={cache.name}
                        className="flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors"
                    >
                        <div className="flex items-center gap-3">
                            <Database className="w-5 h-5 text-muted-foreground shrink-0" />
                            <div>
                                <span className="text-sm font-mono font-medium">{cache.name}</span>
                                <p className="text-xs text-muted-foreground mt-0.5">{cache.description}</p>
                                <div className="flex items-center gap-3 mt-1 flex-wrap">
                                    {cache.files !== undefined && (
                                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                                            <HardDrive className="w-3 h-3" />
                                            {cache.files} files, {cache.size_mb} MB
                                        </span>
                                    )}
                                    {cache.sessions !== undefined && (
                                        <span className="text-xs text-muted-foreground">
                                            {cache.sessions} active sessions
                                        </span>
                                    )}
                                    {cache.entries !== undefined && (
                                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                                            <Zap className="w-3 h-3" />
                                            {cache.entries}/{cache.max_entries ?? 128} entries · {cache.hits ?? 0} hits, {cache.misses ?? 0} misses
                                            {typeof cache.hit_rate === 'number' && (
                                                <span className="text-green-500/80"> · {(cache.hit_rate * 100).toFixed(1)}% hit rate</span>
                                            )}
                                            {cache.enabled === false && (
                                                <span className="text-amber-500"> (disabled)</span>
                                            )}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            {cache.flushable ? (
                                <button
                                    onClick={() => flushCache(cache.name)}
                                    disabled={flushing === cache.name}
                                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 disabled:opacity-40 transition-colors"
                                >
                                    {flushing === cache.name ? (
                                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                    ) : (
                                        <Trash2 className="w-3.5 h-3.5" />
                                    )}
                                    Flush
                                </button>
                            ) : (
                                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <XCircle className="w-3.5 h-3.5" />
                                    Not flushable
                                </span>
                            )}
                        </div>
                    </div>
                ))}
                {caches.length === 0 && (
                    <div className="text-sm text-muted-foreground text-center py-8">
                        No caches detected.
                    </div>
                )}
            </div>
        </div>
    );
};
