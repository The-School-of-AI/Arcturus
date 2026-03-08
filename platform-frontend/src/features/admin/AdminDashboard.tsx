import React, { useState } from 'react';
import { Activity, DollarSign, AlertTriangle, Heart } from 'lucide-react';
import { TracesPanel } from './components/TracesPanel';
import { CostPanel } from './components/CostPanel';
import { ErrorsPanel } from './components/ErrorsPanel';
import { HealthPanel } from './components/HealthPanel';
import { cn } from '@/lib/utils';

type TabId = 'traces' | 'cost' | 'errors' | 'health';

export const AdminDashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState<TabId>('traces');

    const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
        { id: 'traces', label: 'Traces', icon: Activity },
        { id: 'cost', label: 'Cost', icon: DollarSign },
        { id: 'errors', label: 'Errors', icon: AlertTriangle },
        { id: 'health', label: 'Health', icon: Heart },
    ];

    return (
        <div className="h-full flex flex-col bg-background text-foreground">
            <div className="border-b border-border px-6 py-4">
                <h1 className="text-xl font-bold uppercase tracking-tighter">Watchtower Admin</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Distributed tracing, cost analytics, error monitoring, and service health
                </p>
            </div>
            <div className="flex border-b border-border">
                {tabs.map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={cn(
                            'px-6 py-3 text-sm font-medium flex items-center gap-2 transition-colors',
                            activeTab === id
                                ? 'text-primary border-b-2 border-primary -mb-px'
                                : 'text-muted-foreground hover:text-foreground'
                        )}
                    >
                        <Icon className="w-4 h-4" />
                        {label}
                    </button>
                ))}
            </div>
            <div className="flex-1 overflow-auto p-6">
                {activeTab === 'traces' && <TracesPanel />}
                {activeTab === 'cost' && <CostPanel />}
                {activeTab === 'errors' && <ErrorsPanel />}
                {activeTab === 'health' && <HealthPanel />}
            </div>
        </div>
    );
};
