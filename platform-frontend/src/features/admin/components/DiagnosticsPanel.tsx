import React, { useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import {
    Stethoscope,
    CheckCircle,
    AlertTriangle,
    XCircle,
    Play,
    Gauge,
} from 'lucide-react';

interface DiagnosticCheck {
    check: string;
    status: 'pass' | 'warn' | 'fail';
    message: string;
    suggestion?: string;
}

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

const StatusIcon = ({ status }: { status: string }) => {
    if (status === 'pass') return <CheckCircle className="w-4 h-4 text-green-500" />;
    if (status === 'warn') return <AlertTriangle className="w-4 h-4 text-amber-500" />;
    return <XCircle className="w-4 h-4 text-red-500" />;
};

const statusBg = (status: string) => {
    if (status === 'pass') return 'bg-green-500/10 border-green-500/30 text-green-500';
    if (status === 'warn') return 'bg-amber-500/10 border-amber-500/30 text-amber-500';
    return 'bg-red-500/10 border-red-500/30 text-red-500';
};

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
                <div className="text-xs text-red-500 font-medium">⚠ Budget exceeded — requests throttled</div>
            )}
        </div>
    );
};

export const DiagnosticsPanel: React.FC = () => {
    const [checks, setChecks] = useState<DiagnosticCheck[]>([]);
    const [overall, setOverall] = useState<string | null>(null);
    const [summary, setSummary] = useState<{ pass: number; warn: number; fail: number } | null>(null);
    const [throttle, setThrottle] = useState<ThrottleData | null>(null);
    const [loading, setLoading] = useState(false);
    const [hasRun, setHasRun] = useState(false);

    const runDiagnostics = useCallback(async () => {
        setLoading(true);
        try {
            const [diagRes, throttleRes] = await Promise.allSettled([
                axios.get(`${API_BASE}/admin/diagnostics`),
                axios.get(`${API_BASE}/admin/throttle`),
            ]);

            if (diagRes.status === 'fulfilled') {
                setChecks(diagRes.value.data.checks || []);
                setOverall(diagRes.value.data.overall || null);
                setSummary(diagRes.value.data.summary || null);
            }
            if (throttleRes.status === 'fulfilled') {
                setThrottle(throttleRes.value.data || null);
            }
            setHasRun(true);
        } catch (e) {
            console.error('Diagnostics failed', e);
        } finally {
            setLoading(false);
        }
    }, []);

    return (
        <div className="space-y-6">
            {/* header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Stethoscope className="w-5 h-5 text-muted-foreground" />
                    <div>
                        <h2 className="text-sm font-semibold">Arcturus Doctor</h2>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            Automated health check and system diagnostics
                        </p>
                    </div>
                </div>
                <button
                    onClick={runDiagnostics}
                    disabled={loading}
                    className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-60 transition-opacity"
                >
                    <Play className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    {loading ? 'Running...' : 'Run Doctor'}
                </button>
            </div>

            {!hasRun && !loading && (
                <div className="text-sm text-muted-foreground text-center py-12 border rounded-lg border-border border-dashed">
                    Click "Run Doctor" to start diagnostics
                </div>
            )}

            {/* overall summary */}
            {overall && summary && (
                <div className="flex items-center gap-4">
                    <span
                        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border ${statusBg(overall)}`}
                    >
                        <StatusIcon status={overall} />
                        {overall === 'pass' ? 'All Clear' : overall === 'warn' ? 'Warnings' : 'Issues Found'}
                    </span>
                    <span className="text-xs text-muted-foreground">
                        {summary.pass} pass · {summary.warn} warn · {summary.fail} fail
                    </span>
                </div>
            )}

            {/* throttle / budget gauges */}
            {throttle && (
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <Gauge className="w-4 h-4 text-muted-foreground" />
                        <h3 className="text-sm font-medium">Cost Budget</h3>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <BudgetGauge data={throttle.hourly} />
                        <BudgetGauge data={throttle.daily} />
                    </div>
                </div>
            )}

            {/* checks list */}
            {checks.length > 0 && (
                <div className="rounded-lg border border-border divide-y divide-border">
                    {checks.map((check, i) => (
                        <div key={i} className="px-4 py-3">
                            <div className="flex items-start gap-3">
                                <StatusIcon status={check.status} />
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-mono font-medium">
                                            {check.check}
                                        </span>
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {check.message}
                                    </p>
                                    {check.suggestion && (
                                        <p className="text-xs text-amber-500/80 mt-1">
                                            💡 {check.suggestion}
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
