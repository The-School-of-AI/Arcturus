/**
 * Blocks.so Components - Free shadcn/ui blocks adapted for App Builder
 * Source: https://blocks.so/
 * 
 * These are adapted from blocks.so to work as draggable App Builder cards
 * with dynamic data binding via the data prop.
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, ArrowRight } from 'lucide-react';

// ============================================================================
// STATS-01: Stats with Trending
// Source: https://blocks.so/stats#stats-01
// ============================================================================

interface StatItem {
    name: string;
    value: string;
    change: string;
    changeType: 'positive' | 'negative' | 'neutral';
}

interface StatsTrendingCardProps {
    title?: string;
    data?: {
        stats?: StatItem[];
    };
    config?: {
        showTitle?: boolean;
        showChange?: boolean;
    };
    style?: any;
}

const defaultStats: StatItem[] = [
    { name: 'Profit', value: '$287,654', change: '+8.32%', changeType: 'positive' },
    { name: 'Late payments', value: '$9,435', change: '-12.64%', changeType: 'negative' },
    { name: 'Pending orders', value: '$173,229', change: '+2.87%', changeType: 'positive' },
];

export const StatsTrendingCard: React.FC<StatsTrendingCardProps> = ({
    title = 'Key Metrics',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const showChange = config.showChange !== false;
    const stats = data.stats || defaultStats;

    return (
        <div className="h-full flex flex-col p-4">
            {showTitle && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-2">
                    <TrendingUp className="w-3.5 h-3.5 text-primary" />
                    {title}
                </h3>
            )}
            <div className="grid grid-cols-1 gap-3 flex-1">
                {stats.map((stat, index) => (
                    <div
                        key={index}
                        className="p-3 rounded-lg bg-black/30 border border-white/10"
                    >
                        <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-medium text-muted-foreground">{stat.name}</span>
                            {showChange && (
                                <span className={cn(
                                    "text-xs font-medium",
                                    stat.changeType === 'positive' ? "text-green-400" :
                                        stat.changeType === 'negative' ? "text-red-400" : "text-muted-foreground"
                                )}>
                                    {stat.change}
                                </span>
                            )}
                        </div>
                        <div className="text-xl font-bold text-foreground">{stat.value}</div>
                    </div>
                ))}
            </div>
        </div>
    );
};

// ============================================================================
// STATS-03: Stats with Card Layout
// Source: https://blocks.so/stats#stats-03
// ============================================================================

interface StatsGridCardProps {
    title?: string;
    data?: {
        stats?: StatItem[];
    };
    config?: {
        showTitle?: boolean;
        columns?: 2 | 3 | 4;
    };
    style?: any;
}

const defaultGridStats: StatItem[] = [
    { name: 'Unique visitors', value: '10,450', change: '-12.5%', changeType: 'negative' },
    { name: 'Bounce rate', value: '56.1%', change: '+1.8%', changeType: 'positive' },
    { name: 'Visit duration', value: '5.2min', change: '+19.7%', changeType: 'positive' },
    { name: 'Conversion rate', value: '3.2%', change: '-2.4%', changeType: 'negative' },
];

export const StatsGridCard: React.FC<StatsGridCardProps> = ({
    title = 'Analytics Overview',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const columns = config.columns || 2;
    const stats = data.stats || defaultGridStats;

    return (
        <div className="h-full flex flex-col p-4">
            {showTitle && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    {title}
                </h3>
            )}
            <div className={cn(
                "grid gap-3 flex-1",
                columns === 2 && "grid-cols-2",
                columns === 3 && "grid-cols-3",
                columns === 4 && "grid-cols-4"
            )}>
                {stats.map((item, index) => (
                    <Card key={index} className="p-4 py-3 bg-black/30 border-white/10">
                        <CardContent className="p-0">
                            <dt className="text-xs font-medium text-muted-foreground">{item.name}</dt>
                            <dd className="mt-1 flex items-baseline space-x-2">
                                <span className="text-2xl font-semibold text-foreground">{item.value}</span>
                                <span className={cn(
                                    "text-xs font-medium",
                                    item.changeType === 'positive' ? "text-green-400" :
                                        item.changeType === 'negative' ? "text-red-400" : "text-muted-foreground"
                                )}>
                                    {item.change}
                                </span>
                            </dd>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};

// ============================================================================
// STATS-06: Stats with Status Badges
// Source: https://blocks.so/stats#stats-06
// ============================================================================

interface StatusStatItem {
    name: string;
    value: string;
    status: 'success' | 'warning' | 'error' | 'info';
    statusText: string;
}

interface StatsStatusCardProps {
    title?: string;
    data?: {
        stats?: StatusStatItem[];
    };
    config?: {
        showTitle?: boolean;
    };
    style?: any;
}

const defaultStatusStats: StatusStatItem[] = [
    { name: 'API Uptime', value: '99.9%', status: 'success', statusText: 'Operational' },
    { name: 'Response Time', value: '142ms', status: 'success', statusText: 'Normal' },
    { name: 'Error Rate', value: '0.4%', status: 'warning', statusText: 'Elevated' },
    { name: 'Active Users', value: '2,847', status: 'info', statusText: 'Online' },
];

const statusStyles = {
    success: 'bg-green-500/15 text-green-400 border-0',
    warning: 'bg-amber-500/15 text-amber-400 border-0',
    error: 'bg-red-500/15 text-red-400 border-0',
    info: 'bg-blue-500/15 text-blue-400 border-0',
};

export const StatsStatusCard: React.FC<StatsStatusCardProps> = ({
    title = 'System Status',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const stats = data.stats || defaultStatusStats;

    return (
        <div className="h-full flex flex-col p-4">
            {showTitle && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    {title}
                </h3>
            )}
            <div className="grid grid-cols-2 gap-3 flex-1">
                {stats.map((item, index) => (
                    <div key={index} className="p-3 rounded-lg bg-black/30 border border-white/10">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium text-muted-foreground">{item.name}</span>
                            <Badge variant="outline" className={statusStyles[item.status]}>
                                {item.statusText}
                            </Badge>
                        </div>
                        <div className="text-2xl font-bold text-foreground">{item.value}</div>
                    </div>
                ))}
            </div>
        </div>
    );
};

// ============================================================================
// SIMPLE TABLE CARD
// Adapted from blocks.so/tables with simplified structure
// ============================================================================

interface SimpleTableRow {
    cells: string[];
    status?: 'success' | 'warning' | 'error' | 'default';
}

interface SimpleTableCardProps {
    title?: string;
    data?: {
        headers?: string[];
        rows?: SimpleTableRow[];
    };
    config?: {
        showTitle?: boolean;
        striped?: boolean;
    };
    style?: any;
}

const defaultTableData = {
    headers: ['Task', 'Status', 'Due Date'],
    rows: [
        { cells: ['User Authentication', 'In Progress', '2024-03-25'], status: 'warning' as const },
        { cells: ['Dashboard UI', 'Completed', '2024-03-20'], status: 'success' as const },
        { cells: ['API Optimization', 'Pending', '2024-03-22'], status: 'default' as const },
    ]
};

export const SimpleTableCard: React.FC<SimpleTableCardProps> = ({
    title = 'Tasks',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const striped = config.striped !== false;
    const headers = data.headers || defaultTableData.headers;
    const rows = data.rows || defaultTableData.rows;

    return (
        <div className="h-full flex flex-col">
            {showTitle && (
                <div className="px-4 py-3 border-b border-white/10">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {title}
                    </h3>
                </div>
            )}
            <div className="flex-1 overflow-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-white/10">
                            {headers.map((header, i) => (
                                <th key={i} className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                                    {header}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, rowIndex) => (
                            <tr
                                key={rowIndex}
                                className={cn(
                                    "border-b border-white/5",
                                    striped && rowIndex % 2 === 1 && "bg-white/5"
                                )}
                            >
                                {row.cells.map((cell, cellIndex) => (
                                    <td key={cellIndex} className="px-4 py-3 text-sm text-foreground">
                                        {cellIndex === 1 && row.status ? (
                                            <Badge
                                                variant="outline"
                                                className={cn(
                                                    "border-0",
                                                    row.status === 'success' && "bg-green-500/15 text-green-400",
                                                    row.status === 'warning' && "bg-amber-500/15 text-amber-400",
                                                    row.status === 'error' && "bg-red-500/15 text-red-400",
                                                    row.status === 'default' && "bg-gray-500/15 text-gray-400"
                                                )}
                                            >
                                                {cell}
                                            </Badge>
                                        ) : cell}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

// ============================================================================
// LINKS CARD (from blocks.so stats-05)
// ============================================================================

interface LinkItem {
    name: string;
    value: string;
    href?: string;
}

interface StatsLinksCardProps {
    title?: string;
    data?: {
        links?: LinkItem[];
    };
    config?: {
        showTitle?: boolean;
    };
    style?: any;
}

const defaultLinks: LinkItem[] = [
    { name: 'Active Projects', value: '12', href: '#' },
    { name: 'Open Issues', value: '47', href: '#' },
    { name: 'Pull Requests', value: '8', href: '#' },
    { name: 'Deployments', value: '156', href: '#' },
];

export const StatsLinksCard: React.FC<StatsLinksCardProps> = ({
    title = 'Quick Links',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const links = data.links || defaultLinks;

    return (
        <div className="h-full flex flex-col p-4">
            {showTitle && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    {title}
                </h3>
            )}
            <div className="flex flex-col gap-2 flex-1">
                {links.map((link, index) => (
                    <div
                        key={index}
                        className="flex items-center justify-between p-3 rounded-lg bg-black/30 border border-white/10 hover:bg-white/5 cursor-pointer transition-colors group"
                    >
                        <div>
                            <span className="text-sm font-medium text-foreground">{link.name}</span>
                            <span className="ml-2 text-xl font-bold text-primary">{link.value}</span>
                        </div>
                        <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                ))}
            </div>
        </div>
    );
};
