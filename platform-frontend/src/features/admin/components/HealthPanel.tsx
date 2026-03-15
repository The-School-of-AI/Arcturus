import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import {
    Activity,
    CheckCircle,
    XCircle,
    AlertTriangle,
    RefreshCw,
    Cpu,
    HardDrive,
    MemoryStick,
    Clock,
} from 'lucide-react';

/* ── Types ────────────────────────────────────────────────────────────── */

interface ServiceHealth {
    service: string;
    status: 'ok' | 'degraded' | 'down';
    latency_ms?: number;
    details?: string;
}

interface UptimeEntry {
    service: string;
    uptime_pct: number;
    total_checks: number;
    ok_checks: number;
    degraded_checks: number;
    down_checks: number;
    avg_latency_ms: number | null;
    hours: number;
}

interface ResourceData {
    cpu_pct: number;
    mem_pct: number;
    disk_pct: number;
    mem_used_mb: number;
    mem_total_mb: number;
    disk_used_gb: number;
    disk_total_gb: number;
}

interface HistorySnapshot {
    timestamp: string;
    service: string;
    status: 'ok' | 'degraded' | 'down';
    latency_ms?: number;
    details?: string;
}

/* ── Constants ────────────────────────────────────────────────────────── */

const POLL_INTERVAL_MS = 30_000;

/* ── Helpers ──────────────────────────────────────────────────────────── */

const StatusIcon = ({ status }: { status: string }) => {
    if (status === 'ok') return <CheckCircle className="w-4 h-4 text-green-500" />;
    if (status === 'degraded') return <AlertTriangle className="w-4 h-4 text-amber-500" />;
    return <XCircle className="w-4 h-4 text-red-500" />;
};

const StatusDot = ({ status }: { status: string }) => {
    const color =
        status === 'ok'
            ? 'bg-green-500'
            : status === 'degraded'
              ? 'bg-amber-500'
              : 'bg-red-500';
    return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
};

const statusLabel = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const uptimeColor = (pct: number) => {
    if (pct >= 99) return 'text-green-500';
    if (pct >= 95) return 'text-amber-500';
    return 'text-red-500';
};

const uptimeBg = (pct: number) => {
    if (pct >= 99) return 'bg-green-500/10 border-green-500/30';
    if (pct >= 95) return 'bg-amber-500/10 border-amber-500/30';
    return 'bg-red-500/10 border-red-500/30';
};

const gaugeColor = (pct: number) => {
    if (pct < 60) return 'bg-green-500';
    if (pct < 85) return 'bg-amber-500';
    return 'bg-red-500';
};

/* ── ResourceGauge sub-component ──────────────────────────────────────── */

const ResourceGauge: React.FC<{
    icon: React.ReactNode;
    label: string;
    pct: number;
    detail: string;
}> = ({ icon, label, pct, detail }) => (
    <div className="rounded-lg border border-border p-4 space-y-2">
        <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-medium">
                {icon}
                {label}
            </div>
            <span className="text-xs text-muted-foreground">{detail}</span>
        </div>
        <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
            <div
                className={`h-full rounded-full transition-all duration-500 ${gaugeColor(pct)}`}
                style={{ width: `${Math.min(pct, 100)}%` }}
            />
        </div>
        <div className="text-right text-xs text-muted-foreground">{pct.toFixed(1)}%</div>
    </div>
);

/* ── Main component ───────────────────────────────────────────────────── */

export const HealthPanel: React.FC = () => {
    const [services, setServices] = useState<ServiceHealth[]>([]);
    const [uptimes, setUptimes] = useState<UptimeEntry[]>([]);
    const [resources, setResources] = useState<ResourceData | null>(null);
    const [history, setHistory] = useState<HistorySnapshot[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchAll = useCallback(async () => {
        try {
            const [healthRes, uptimeRes, resourcesRes, historyRes] = await Promise.allSettled([
                axios.get(`${API_BASE}/admin/health`),
                axios.get(`${API_BASE}/admin/health/uptime`, { params: { hours: 24 } }),
                axios.get(`${API_BASE}/admin/health/resources`),
                axios.get(`${API_BASE}/admin/health/history`, {
                    params: { hours: 24, limit: 500 },
                }),
            ]);

            if (healthRes.status === 'fulfilled')
                setServices(healthRes.value.data.services || []);
            if (uptimeRes.status === 'fulfilled')
                setUptimes(uptimeRes.value.data.uptimes || []);
            if (resourcesRes.status === 'fulfilled')
                setResources(resourcesRes.value.data.resources || null);
            if (historyRes.status === 'fulfilled')
                setHistory(historyRes.value.data.snapshots || []);

            setLastUpdated(new Date());
        } catch (e) {
            console.error('Failed to fetch health data', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
        intervalRef.current = setInterval(fetchAll, POLL_INTERVAL_MS);
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [fetchAll]);

    /* Derive incidents: status transitions per service, newest first */
    const incidents = useMemo(() => {
        const sorted = [...history].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
        const changes: HistorySnapshot[] = [];
        const lastSeen: Record<string, string> = {};

        for (const snap of sorted) {
            const prev = lastSeen[snap.service];
            if (prev && prev !== snap.status) {
                changes.push(snap);
            }
            lastSeen[snap.service] = snap.status;
        }
        return changes.slice(0, 20);
    }, [history]);

    /* Group history by service, keep last 30 checks for the timeline dots */
    const historyByService = useMemo(() => {
        const map: Record<string, HistorySnapshot[]> = {};
        for (const snap of history) {
            if (!map[snap.service]) map[snap.service] = [];
            map[snap.service].push(snap);
        }
        for (const key of Object.keys(map)) {
            map[key].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
            if (map[key].length > 30) {
                map[key] = map[key].slice(-30);
            }
        }
        return map;
    }, [history]);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Activity className="w-8 h-8 animate-pulse text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* ── Header: last updated + refresh ── */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock className="w-3.5 h-3.5" />
                    {lastUpdated ? (
                        <span>Last updated: {lastUpdated.toLocaleTimeString()}</span>
                    ) : (
                        <span>Loading...</span>
                    )}
                    <span className="text-muted-foreground/50">
                        &bull; auto-refresh {POLL_INTERVAL_MS / 1000}s
                    </span>
                </div>
                <button
                    onClick={fetchAll}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded border border-border hover:border-foreground/20"
                >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Refresh
                </button>
            </div>

            {/* ── Resource gauges ── */}
            {resources && (
                <div className="grid grid-cols-3 gap-4">
                    <ResourceGauge
                        icon={<Cpu className="w-4 h-4" />}
                        label="CPU"
                        pct={resources.cpu_pct}
                        detail={`${resources.cpu_pct.toFixed(1)}%`}
                    />
                    <ResourceGauge
                        icon={<MemoryStick className="w-4 h-4" />}
                        label="Memory"
                        pct={resources.mem_pct}
                        detail={`${(resources.mem_used_mb / 1024).toFixed(1)} / ${(resources.mem_total_mb / 1024).toFixed(1)} GB`}
                    />
                    <ResourceGauge
                        icon={<HardDrive className="w-4 h-4" />}
                        label="Disk"
                        pct={resources.disk_pct}
                        detail={`${resources.disk_used_gb.toFixed(0)} / ${resources.disk_total_gb.toFixed(0)} GB`}
                    />
                </div>
            )}

            {/* ── Service table with uptime + timeline ── */}
            <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className="text-left p-3 font-medium">Service</th>
                            <th className="text-left p-3 font-medium">Status</th>
                            <th className="text-right p-3 font-medium">Latency</th>
                            <th className="text-center p-3 font-medium">Uptime (24h)</th>
                            <th className="text-center p-3 font-medium">History</th>
                            <th className="text-left p-3 font-medium">Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {services.map((svc) => {
                            const uptime = uptimes.find((u) => u.service === svc.service);
                            const timeline = historyByService[svc.service] || [];
                            return (
                                <tr
                                    key={svc.service}
                                    className="border-t border-border hover:bg-muted/20"
                                >
                                    <td className="p-3 font-mono font-medium text-xs">
                                        {svc.service}
                                    </td>
                                    <td className="p-3">
                                        <span className="flex items-center gap-1.5">
                                            <StatusIcon status={svc.status} />
                                            <span
                                                className={
                                                    svc.status === 'ok'
                                                        ? 'text-green-600 dark:text-green-400'
                                                        : svc.status === 'degraded'
                                                          ? 'text-amber-600 dark:text-amber-400'
                                                          : 'text-red-600 dark:text-red-400'
                                                }
                                            >
                                                {statusLabel(svc.status)}
                                            </span>
                                        </span>
                                    </td>
                                    <td className="p-3 text-right font-mono text-muted-foreground text-xs">
                                        {svc.latency_ms != null ? `${svc.latency_ms}ms` : '-'}
                                    </td>
                                    <td className="p-3 text-center">
                                        {uptime ? (
                                            <span
                                                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${uptimeBg(uptime.uptime_pct)} ${uptimeColor(uptime.uptime_pct)}`}
                                            >
                                                {uptime.uptime_pct.toFixed(1)}%
                                            </span>
                                        ) : (
                                            <span className="text-xs text-muted-foreground">-</span>
                                        )}
                                    </td>
                                    <td className="p-3">
                                        <div
                                            className="flex items-center justify-center gap-0.5"
                                            title="Last 30 checks"
                                        >
                                            {timeline.length > 0 ? (
                                                timeline.map((snap, i) => (
                                                    <StatusDot key={i} status={snap.status} />
                                                ))
                                            ) : (
                                                <span className="text-xs text-muted-foreground">
                                                    -
                                                </span>
                                            )}
                                        </div>
                                    </td>
                                    <td
                                        className="p-3 text-muted-foreground text-xs max-w-[200px] truncate"
                                        title={svc.details ?? ''}
                                    >
                                        {svc.details || '-'}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {services.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                    No health data available.
                </p>
            )}

            {/* ── Incident log ── */}
            {incidents.length > 0 && (
                <div>
                    <h3 className="text-sm font-medium mb-3">
                        Recent Incidents (status changes)
                    </h3>
                    <div className="rounded-lg border border-border divide-y divide-border">
                        {incidents.map((inc, i) => (
                            <div
                                key={i}
                                className="flex items-center gap-3 px-3 py-2 text-xs"
                            >
                                <StatusDot status={inc.status} />
                                <span className="font-mono font-medium w-28">
                                    {inc.service}
                                </span>
                                <span className="text-muted-foreground">
                                    changed to{' '}
                                    <span className="font-medium">
                                        {statusLabel(inc.status)}
                                    </span>
                                </span>
                                <span className="ml-auto text-muted-foreground/70">
                                    {new Date(inc.timestamp).toLocaleString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
