import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { Gauge, Save, RefreshCw, AlertCircle } from 'lucide-react';

interface ThrottleWindow {
    window: string;
    spent_usd: number;
    budget_usd: number;
    remaining_usd: number;
    usage_pct: number;
    throttled: boolean;
}

interface ThrottleData {
    hourly: ThrottleWindow;
    daily: ThrottleWindow;
    allowed: boolean;
    reason: string;
}

const BudgetGauge: React.FC<{ data: ThrottleWindow }> = ({ data }) => {
    const pct = Math.min(data.usage_pct, 100);
    const barColor =
        pct < 60 ? 'bg-green-500' : pct < 85 ? 'bg-amber-500' : 'bg-red-500';

    return (
        <div className="rounded-lg border border-border p-4 space-y-2">
            <div className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize">{data.window} Budget</span>
                <span className="text-xs text-muted-foreground">
                    ${data.spent_usd.toFixed(4)} / ${data.budget_usd.toFixed(2)}
                </span>
            </div>
            <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${pct}%` }}
                />
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
                <span>{pct.toFixed(1)}% used</span>
                <span>${data.remaining_usd.toFixed(4)} remaining</span>
            </div>
            {data.throttled && (
                <div className="text-xs text-red-500 font-medium flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Budget exceeded — new runs blocked (429)
                </div>
            )}
        </div>
    );
};

const DEFAULT_LIMITS = { hourly: 1.0, daily: 5.0 };

export const ThrottlePanel: React.FC = () => {
    const [throttle, setThrottle] = useState<ThrottleData | null>(null);
    const [hourlyBudget, setHourlyBudget] = useState<string>('');
    const [dailyBudget, setDailyBudget] = useState<string>('');
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(true);

    const fetchThrottle = useCallback(async () => {
        try {
            const res = await axios.get(`${API_BASE}/admin/throttle`);
            const data = res.data as ThrottleData;
            setThrottle(data);
            setHourlyBudget(data.hourly.budget_usd.toString());
            setDailyBudget(data.daily.budget_usd.toString());
        } catch (e) {
            console.error('Failed to fetch throttle', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchThrottle();
    }, [fetchThrottle]);

    const saveLimits = async () => {
        const h = parseFloat(hourlyBudget);
        const d = parseFloat(dailyBudget);
        if (isNaN(h) || isNaN(d) || h < 0 || d < 0) return;
        setSaving(true);
        try {
            await axios.put(`${API_BASE}/admin/throttle`, {
                hourly_budget_usd: h,
                daily_budget_usd: d,
            });
            await fetchThrottle();
        } catch (e) {
            console.error('Failed to save throttle', e);
        } finally {
            setSaving(false);
        }
    };

    const applyDefaultLimits = () => {
        setHourlyBudget(DEFAULT_LIMITS.hourly.toString());
        setDailyBudget(DEFAULT_LIMITS.daily.toString());
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center p-12">
                <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-2xl">
            <div className="flex items-center gap-3">
                <Gauge className="w-5 h-5 text-muted-foreground" />
                <div>
                    <h2 className="text-sm font-semibold">Cost Throttle</h2>
                    <p className="text-xs text-muted-foreground mt-0.5">
                        Global hourly/daily budgets. When exceeded, new runs return 429.
                    </p>
                </div>
            </div>

            {/* Usage gauges */}
            {throttle && (
                <div className="grid grid-cols-2 gap-4">
                    <BudgetGauge data={throttle.hourly} />
                    <BudgetGauge data={throttle.daily} />
                </div>
            )}

            {/* Edit form */}
            <div className="rounded-lg border border-border p-4 space-y-4">
                <h3 className="text-sm font-medium">Set Budget Limits</h3>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-xs text-muted-foreground block mb-1">Hourly ($)</label>
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={hourlyBudget}
                            onChange={(e) => setHourlyBudget(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm font-mono"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-muted-foreground block mb-1">Daily ($)</label>
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={dailyBudget}
                            onChange={(e) => setDailyBudget(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm font-mono"
                        />
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={saveLimits}
                        disabled={saving}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-60"
                    >
                        <Save className="w-4 h-4" />
                        {saving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                        onClick={applyDefaultLimits}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-muted-foreground text-sm hover:bg-muted/50"
                    >
                        Reset to defaults
                    </button>
                    <button
                        onClick={fetchThrottle}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-muted-foreground text-sm hover:bg-muted/50"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Refresh
                    </button>
                </div>
            </div>
        </div>
    );
};
