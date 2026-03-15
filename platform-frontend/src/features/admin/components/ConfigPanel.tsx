import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { Settings, RefreshCw, Activity, GitCompare, ChevronDown, ChevronRight } from 'lucide-react';

interface ConfigDiff {
    path: string;
    default: unknown;
    current: unknown;
}

export const ConfigPanel: React.FC = () => {
    const [config, setConfig] = useState<Record<string, unknown> | null>(null);
    const [diffs, setDiffs] = useState<ConfigDiff[]>([]);
    const [loading, setLoading] = useState(true);
    const [showDiff, setShowDiff] = useState(false);
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['models', 'agent']));

    const fetchConfig = useCallback(async () => {
        try {
            const [configRes, diffRes] = await Promise.allSettled([
                axios.get(`${API_BASE}/admin/config`),
                axios.get(`${API_BASE}/admin/config/diff`),
            ]);
            if (configRes.status === 'fulfilled') setConfig(configRes.value.data.config || {});
            if (diffRes.status === 'fulfilled') setDiffs(diffRes.value.data.differences || []);
        } catch (e) {
            console.error('Failed to fetch config', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchConfig();
    }, [fetchConfig]);

    const toggleSection = (key: string) => {
        setExpandedSections((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
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
                    <h2 className="text-sm font-semibold">Configuration</h2>
                    <p className="text-xs text-muted-foreground mt-1">
                        Read-only view of settings.json. Edit via the Settings page.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowDiff(!showDiff)}
                        className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border transition-colors ${
                            showDiff
                                ? 'border-primary text-primary bg-primary/5'
                                : 'border-border text-muted-foreground hover:text-foreground hover:border-foreground/20'
                        }`}
                    >
                        <GitCompare className="w-3.5 h-3.5" />
                        Diff ({diffs.length})
                    </button>
                    <button
                        onClick={fetchConfig}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded border border-border hover:border-foreground/20 transition-colors"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* diff view */}
            {showDiff && diffs.length > 0 && (
                <div className="rounded-lg border border-border overflow-hidden">
                    <div className="bg-muted/50 px-4 py-2 text-xs font-medium">
                        Changes from defaults ({diffs.length})
                    </div>
                    <div className="divide-y divide-border">
                        {diffs.map((d, i) => (
                            <div key={i} className="px-4 py-2 text-xs font-mono">
                                <span className="text-muted-foreground">{d.path}</span>
                                <div className="flex gap-4 mt-1">
                                    <span className="text-red-400">
                                        - {JSON.stringify(d.default)}
                                    </span>
                                    <span className="text-green-400">
                                        + {JSON.stringify(d.current)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {showDiff && diffs.length === 0 && (
                <div className="text-sm text-muted-foreground text-center py-4 border rounded-lg border-border">
                    No differences from defaults.
                </div>
            )}

            {/* config tree */}
            {config && (
                <div className="rounded-lg border border-border divide-y divide-border">
                    {Object.entries(config).map(([key, value]) => {
                        const isObject = typeof value === 'object' && value !== null && !Array.isArray(value);
                        const expanded = expandedSections.has(key);

                        return (
                            <div key={key}>
                                <button
                                    onClick={() => isObject && toggleSection(key)}
                                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium hover:bg-muted/20 transition-colors"
                                >
                                    {isObject ? (
                                        expanded ? (
                                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                        ) : (
                                            <ChevronRight className="w-4 h-4 text-muted-foreground" />
                                        )
                                    ) : (
                                        <Settings className="w-4 h-4 text-muted-foreground" />
                                    )}
                                    <span className="font-mono">{key}</span>
                                    {!isObject && (
                                        <span className="ml-auto text-xs text-muted-foreground font-mono">
                                            {JSON.stringify(value)}
                                        </span>
                                    )}
                                </button>
                                {isObject && expanded && (
                                    <div className="px-4 pb-3">
                                        <pre className="text-xs font-mono text-muted-foreground bg-muted/20 rounded p-3 overflow-auto max-h-64">
                                            {JSON.stringify(value, null, 2)}
                                        </pre>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
