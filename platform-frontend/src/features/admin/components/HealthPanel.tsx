import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API_BASE } from '@/lib/api';
import { Activity, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

interface ServiceHealth {
    service: string;
    status: 'ok' | 'degraded' | 'down';
    latency_ms?: number;
    details?: string;
}

export const HealthPanel: React.FC = () => {
    const [services, setServices] = useState<ServiceHealth[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchHealth = async () => {
            try {
                const res = await axios.get(`${API_BASE}/admin/health`);
                setServices(res.data.services || []);
            } catch (e) {
                console.error('Failed to fetch health', e);
            } finally {
                setLoading(false);
            }
        };
        fetchHealth();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Activity className="w-8 h-8 animate-pulse text-muted-foreground" />
            </div>
        );
    }

    const StatusIcon = ({ status }: { status: string }) => {
        if (status === 'ok') return <CheckCircle className="w-5 h-5 text-green-500" />;
        if (status === 'degraded') return <AlertTriangle className="w-5 h-5 text-amber-500" />;
        return <XCircle className="w-5 h-5 text-red-500" />;
    };

    const statusLabel = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

    return (
        <div className="space-y-6">
            <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className="text-left p-3 font-medium">Service</th>
                            <th className="text-left p-3 font-medium">Status</th>
                            <th className="text-right p-3 font-medium">Latency</th>
                            <th className="text-left p-3 font-medium">Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {services.map((svc) => (
                            <tr key={svc.service} className="border-t border-border hover:bg-muted/20">
                                <td className="p-3 font-mono font-medium">{svc.service}</td>
                                <td className="p-3 flex items-center gap-2">
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
                                </td>
                                <td className="p-3 text-right font-mono text-muted-foreground">
                                    {svc.latency_ms != null ? `${svc.latency_ms}ms` : '-'}
                                </td>
                                <td className="p-3 text-muted-foreground text-xs max-w-[300px] truncate" title={svc.details ?? ''}>
                                    {svc.details || '-'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {services.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">No health data available.</p>
            )}
        </div>
    );
};
