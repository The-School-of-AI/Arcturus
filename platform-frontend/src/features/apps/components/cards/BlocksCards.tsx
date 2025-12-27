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
                        className="p-3 rounded-lg bg-muted border border-border"
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
                    <Card key={index} className="p-4 py-3 bg-muted border-border">
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
                    <div key={index} className="p-3 rounded-lg bg-muted border border-border">
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

    // Normalize rows - handle both [{cells: [...]}] and [[...]] formats
    const rawRows = data.rows || defaultTableData.rows;
    const rows = rawRows.map((row: any) => {
        if (Array.isArray(row)) {
            return { cells: row, status: 'default' as const };
        }
        return row;
    });

    return (
        <div className="h-full flex flex-col">
            {showTitle && (
                <div className="px-4 py-3 border-b border-border">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {title}
                    </h3>
                </div>
            )}
            <div className="flex-1 overflow-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-border">
                            {headers.map((header: string, i: number) => (
                                <th key={i} className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase">
                                    {header}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row: any, rowIndex: number) => (
                            <tr
                                key={rowIndex}
                                className={cn(
                                    "border-b border-border/50",
                                    striped && rowIndex % 2 === 1 && "bg-muted/50"
                                )}
                            >
                                {(row.cells || []).map((cell: string, cellIndex: number) => (
                                    <td key={cellIndex} className="px-4 py-3 text-sm text-foreground">
                                        {cellIndex === 1 && row.status ? (
                                            <Badge
                                                variant="outline"
                                                className={cn(
                                                    "border-0",
                                                    row.status === 'success' && "bg-green-500/15 text-green-400",
                                                    row.status === 'warning' && "bg-amber-500/15 text-amber-400",
                                                    row.status === 'error' && "bg-red-500/15 text-red-400",
                                                    row.status === 'default' && "bg-gray-500/15 text-muted-foreground"
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
                        className="flex items-center justify-between p-3 rounded-lg bg-muted border border-border hover:bg-muted/50 cursor-pointer transition-colors group"
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


// ============================================================================
// STATS-01 CARD: Horizontal Stats Row (adapted from blocks.so stats-01)
// ============================================================================

interface Stats01Stat {
    name: string;
    value: string;
    change: string;
    changeType: 'positive' | 'negative';
}

interface Stats01CardProps {
    title?: string;
    data?: {
        stats?: Stats01Stat[];
    };
    config?: {
        showTitle?: boolean;
    };
    style?: any;
}

const defaultStats01: Stats01Stat[] = [
    { name: 'Profit', value: '$287,654', change: '+8.32%', changeType: 'positive' },
    { name: 'Late payments', value: '$9,435', change: '-12.64%', changeType: 'negative' },
    { name: 'Pending orders', value: '$173,229', change: '+2.87%', changeType: 'positive' },
    { name: 'Operating costs', value: '$52,891', change: '-5.73%', changeType: 'negative' },
];

export const Stats01Card: React.FC<Stats01CardProps> = ({
    title = 'Financial Overview',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const stats = data?.stats || defaultStats01;

    return (
        <div className="h-full flex flex-col">
            {showTitle && (
                <div className="px-4 py-3 border-b border-border">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {title}
                    </h3>
                </div>
            )}
            <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-px bg-border/30 rounded-lg overflow-hidden">
                {stats.map((stat, index) => (
                    <div key={index} className="p-4 bg-background flex flex-col">
                        <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-medium text-muted-foreground">{stat.name}</span>
                            <span className={cn(
                                "text-xs font-medium",
                                stat.changeType === 'positive' ? "text-green-400" : "text-red-400"
                            )}>
                                {stat.change}
                            </span>
                        </div>
                        <div className="text-2xl font-bold text-foreground mt-auto">{stat.value}</div>
                    </div>
                ))}
            </div>
        </div>
    );
};


// ============================================================================
// USAGE STATS CARD: Progress bars for usage (adapted from blocks.so stats-12)
// ============================================================================

interface UsageItem {
    name: string;
    current: string;
    limit: string;
    percentage: number;
}

interface UsageStatsCardProps {
    title?: string;
    data?: {
        items?: UsageItem[];
        subtitle?: string;
    };
    config?: {
        showTitle?: boolean;
    };
    style?: any;
}

const defaultUsageItems: UsageItem[] = [
    { name: 'API Requests', current: '358K', limit: '1M', percentage: 35.8 },
    { name: 'Storage', current: '3.07 GB', limit: '10 GB', percentage: 30.7 },
    { name: 'Bandwidth', current: '4.98 GB', limit: '100 GB', percentage: 5.0 },
    { name: 'Users', current: '24', limit: '50', percentage: 48 },
];

export const UsageStatsCard: React.FC<UsageStatsCardProps> = ({
    title = 'Resource Usage',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const items = data?.items || defaultUsageItems;
    const subtitle = data?.subtitle || 'Last 30 days';

    return (
        <div className="h-full flex flex-col">
            {showTitle && (
                <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {title}
                    </h3>
                    <span className="text-xs text-muted-foreground">{subtitle}</span>
                </div>
            )}
            <div className="flex-1 p-4 space-y-3 overflow-auto">
                {items.map((item, index) => (
                    <div key={index} className="space-y-1.5">
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-foreground font-medium">{item.name}</span>
                            <span className="text-xs text-muted-foreground tabular-nums">
                                {item.current} / {item.limit}
                            </span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                            <div
                                className={cn(
                                    "h-full rounded-full transition-all",
                                    item.percentage > 80 ? "bg-red-500" :
                                        item.percentage > 50 ? "bg-amber-500" : "bg-primary"
                                )}
                                style={{ width: `${Math.min(100, item.percentage)}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};


// ============================================================================
// STORAGE CARD: Segmented usage bar (adapted from blocks.so stats-13)
// ============================================================================

interface StorageSegment {
    label: string;
    value: number;
    color: string;
}

interface StorageCardProps {
    title?: string;
    data?: {
        used?: number;
        total?: number;
        unit?: string;
        segments?: StorageSegment[];
    };
    config?: {
        showTitle?: boolean;
    };
    style?: any;
}

const defaultSegments: StorageSegment[] = [
    { label: 'Documents', value: 2400, color: 'bg-blue-500' },
    { label: 'Photos', value: 1800, color: 'bg-emerald-500' },
    { label: 'Videos', value: 3200, color: 'bg-amber-500' },
    { label: 'Music', value: 900, color: 'bg-purple-500' },
];

// Default colors for auto-assignment
const DEFAULT_SEGMENT_COLORS = [
    'bg-blue-500',
    'bg-emerald-500',
    'bg-amber-500',
    'bg-purple-500',
    'bg-cyan-500',
    'bg-pink-500',
    'bg-indigo-500',
    'bg-teal-500',
];

export const StorageCard: React.FC<StorageCardProps> = ({
    title = 'Storage Usage',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const used = data?.used || 8300;
    const total = data?.total || 15000;
    const unit = data?.unit || 'MB';

    // Auto-assign colors if not provided
    const rawSegments = data?.segments || defaultSegments;
    const segments = rawSegments.map((seg: any, idx: number) => ({
        ...seg,
        color: seg.color || DEFAULT_SEGMENT_COLORS[idx % DEFAULT_SEGMENT_COLORS.length]
    }));

    const freeValue = total - used;

    return (
        <div className="h-full flex flex-col p-4">
            {showTitle && (
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    {title}
                </h3>
            )}

            <p className="mb-3 text-sm text-muted-foreground">
                Using <span className="font-semibold text-foreground">{used.toLocaleString()} {unit}</span> of {total.toLocaleString()} {unit}
            </p>

            <div className="mb-4 flex h-3 w-full overflow-hidden rounded-full bg-muted">
                {segments.map((segment, index) => (
                    <div
                        key={index}
                        className={cn("h-full", segment.color)}
                        style={{ width: `${(segment.value / total) * 100}%` }}
                    />
                ))}
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                {segments.map((segment, index) => (
                    <div key={index} className="flex items-center gap-2">
                        <span className={cn("size-2.5 shrink-0 rounded", segment.color)} />
                        <span className="text-xs text-muted-foreground">{segment.label}</span>
                        <span className="text-xs tabular-nums text-muted-foreground">{segment.value} {unit}</span>
                    </div>
                ))}
                <div className="flex items-center gap-2">
                    <span className="size-2.5 shrink-0 rounded bg-muted" />
                    <span className="text-xs text-muted-foreground">Free</span>
                    <span className="text-xs tabular-nums text-muted-foreground">{freeValue} {unit}</span>
                </div>
            </div>
        </div>
    );
};


// ============================================================================
// ACCORDION TABLE CARD: Expandable hierarchical table (from blocks.so table-01)
// ============================================================================

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface AccordionRowData {
    id: string;
    name: string;
    category: string;
    value: number;
    date: string;
    children?: AccordionRowData[];
}

interface AccordionTableCardProps {
    title?: string;
    data?: {
        rows?: AccordionRowData[];
    };
    config?: {
        showTitle?: boolean;
    };
    style?: any;
}

const defaultAccordionData: AccordionRowData[] = [
    {
        id: '001', name: 'Project Alpha', category: 'Development', value: 45000, date: '2024-01-15',
        children: [
            { id: '001-01', name: 'Frontend Module', category: 'Development', value: 15000, date: '2024-01-16' },
            { id: '001-02', name: 'Backend Module', category: 'Development', value: 20000, date: '2024-01-21' },
        ]
    },
    {
        id: '002', name: 'Marketing Campaign', category: 'Marketing', value: 28500, date: '2024-01-18',
        children: [
            { id: '002-01', name: 'Social Media', category: 'Marketing', value: 12000, date: '2024-01-19' },
            { id: '002-02', name: 'Email Marketing', category: 'Marketing', value: 8500, date: '2024-01-22' },
        ]
    },
    { id: '003', name: 'Customer Support', category: 'Service', value: 19800, date: '2024-01-25' },
];

const AccordionRow: React.FC<{ row: AccordionRowData; defaultOpen?: boolean }> = ({ row, defaultOpen = false }) => {
    const [isOpen, setIsOpen] = useState(defaultOpen);
    const hasChildren = row.children && row.children.length > 0;

    return (
        <>
            <tr className="border-b border-border/50 hover:bg-muted/50">
                <td className="px-3 py-2 w-8">
                    <button
                        onClick={() => setIsOpen(!isOpen)}
                        className={cn(
                            "p-1 rounded transition-colors",
                            hasChildren ? "hover:bg-muted cursor-pointer" : "opacity-30 cursor-default"
                        )}
                        disabled={!hasChildren}
                    >
                        {hasChildren ? (
                            isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />
                        ) : (
                            <div className="w-3.5 h-3.5" />
                        )}
                    </button>
                </td>
                <td className="px-3 py-2 text-xs  text-muted-foreground">{row.id}</td>
                <td className="px-3 py-2 text-sm font-medium">{row.name}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{row.category}</td>
                <td className="px-3 py-2 text-sm  font-semibold text-right">${row.value.toLocaleString()}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{row.date}</td>
            </tr>
            {hasChildren && isOpen && row.children?.map(child => (
                <tr key={child.id} className="border-b border-border/50 bg-muted/50">
                    <td className="px-3 py-2 w-8"></td>
                    <td className="px-3 py-2 text-xs  text-muted-foreground pl-6">{child.id}</td>
                    <td className="px-3 py-2 text-xs">{child.name}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{child.category}</td>
                    <td className="px-3 py-2 text-xs  text-right">${child.value.toLocaleString()}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{child.date}</td>
                </tr>
            ))}
        </>
    );
};

export const AccordionTableCard: React.FC<AccordionTableCardProps> = ({
    title = 'Projects',
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const rows = data?.rows || defaultAccordionData;

    return (
        <div className="h-full flex flex-col">
            {showTitle && (
                <div className="px-4 py-3 border-b border-border">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {title}
                    </h3>
                </div>
            )}
            <div className="flex-1 overflow-auto">
                <table className="w-full text-sm">
                    <thead className="bg-muted sticky top-0">
                        <tr className="border-b border-border">
                            <th className="px-3 py-2 w-8"></th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">ID</th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Name</th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Category</th>
                            <th className="px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Value</th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, index) => (
                            <AccordionRow key={row.id} row={row} defaultOpen={index === 0} />
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
