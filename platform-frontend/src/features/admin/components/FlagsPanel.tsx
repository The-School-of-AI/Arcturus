import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { ToggleLeft, ToggleRight, Plus, Trash2, RefreshCw, Zap, Activity } from 'lucide-react';

interface FeatureFlag {
    name: string;
    enabled: boolean;
    lifecycle: boolean;
}

export const FlagsPanel: React.FC = () => {
    const [flags, setFlags] = useState<FeatureFlag[]>([]);
    const [loading, setLoading] = useState(true);
    const [toggling, setToggling] = useState<string | null>(null);
    const [newFlagName, setNewFlagName] = useState('');
    const [showAddForm, setShowAddForm] = useState(false);

    const fetchFlags = useCallback(async () => {
        try {
            const res = await axios.get(`${API_BASE}/admin/flags`);
            setFlags(res.data.flags || []);
        } catch (e) {
            console.error('Failed to fetch flags', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchFlags();
    }, [fetchFlags]);

    const toggleFlag = async (name: string, enabled: boolean) => {
        setToggling(name);
        try {
            await axios.put(`${API_BASE}/admin/flags/${name}`, { enabled });
            await fetchFlags();
        } catch (e) {
            console.error('Failed to toggle flag', e);
        } finally {
            setToggling(null);
        }
    };

    const deleteFlag = async (name: string) => {
        try {
            await axios.delete(`${API_BASE}/admin/flags/${name}`);
            await fetchFlags();
        } catch (e) {
            console.error('Failed to delete flag', e);
        }
    };

    const addFlag = async () => {
        if (!newFlagName.trim()) return;
        try {
            await axios.put(`${API_BASE}/admin/flags/${newFlagName.trim()}`, { enabled: true });
            setNewFlagName('');
            setShowAddForm(false);
            await fetchFlags();
        } catch (e) {
            console.error('Failed to add flag', e);
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
            {/* header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-sm font-semibold">Feature Flags</h2>
                    <p className="text-xs text-muted-foreground mt-1">
                        Toggle features on/off. Lifecycle flags control background services.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowAddForm(!showAddForm)}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-border hover:border-foreground/20 transition-colors"
                    >
                        <Plus className="w-3.5 h-3.5" />
                        Add Flag
                    </button>
                    <button
                        onClick={fetchFlags}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded border border-border hover:border-foreground/20 transition-colors"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* add form */}
            {showAddForm && (
                <div className="flex items-center gap-2 p-3 rounded-lg border border-border bg-muted/20">
                    <input
                        type="text"
                        value={newFlagName}
                        onChange={(e) => setNewFlagName(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addFlag()}
                        placeholder="flag_name (snake_case)"
                        className="flex-1 text-sm bg-transparent border border-border rounded px-3 py-1.5 outline-none focus:border-primary"
                    />
                    <button
                        onClick={addFlag}
                        disabled={!newFlagName.trim()}
                        className="text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-40 transition-opacity"
                    >
                        Create
                    </button>
                </div>
            )}

            {/* flag list */}
            <div className="rounded-lg border border-border divide-y divide-border">
                {flags.map((flag) => (
                    <div
                        key={flag.name}
                        className="flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors"
                    >
                        <div className="flex items-center gap-3">
                            <button
                                onClick={() => toggleFlag(flag.name, !flag.enabled)}
                                disabled={toggling === flag.name}
                                className="transition-colors"
                            >
                                {flag.enabled ? (
                                    <ToggleRight className="w-7 h-7 text-green-500" />
                                ) : (
                                    <ToggleLeft className="w-7 h-7 text-muted-foreground" />
                                )}
                            </button>
                            <div>
                                <span className="text-sm font-mono font-medium">{flag.name}</span>
                                {flag.lifecycle && (
                                    <span className="ml-2 inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/30">
                                        <Zap className="w-3 h-3" />
                                        lifecycle
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <span
                                className={`text-xs font-medium ${flag.enabled ? 'text-green-500' : 'text-muted-foreground'}`}
                            >
                                {flag.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                            <button
                                onClick={() => deleteFlag(flag.name)}
                                className="text-muted-foreground hover:text-red-500 transition-colors"
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                ))}
                {flags.length === 0 && (
                    <div className="text-sm text-muted-foreground text-center py-8">
                        No feature flags configured.
                    </div>
                )}
            </div>
        </div>
    );
};
