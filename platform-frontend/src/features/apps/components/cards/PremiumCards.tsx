/**
 * Premium Card Components - built on Magic UI and Aceternity libraries
 * 
 * These cards can be dragged onto the App Builder canvas and configured via the Inspector.
 * Each card has a defined data schema that LLMs/Agents can populate.
 */

import React from 'react';
import { cn } from '@/lib/utils';
import {
    Bell,
    MessageSquare,
    TrendingUp,
    AlertCircle,
    CheckCircle,
    Info,
    BarChart3,
    FileText,
    Users,
    Zap
} from 'lucide-react';

// ============================================================================
// ANIMATED LIST CARD - Magic UI
// Perfect for: Notifications, Activity Feeds, Recent Transactions
// ============================================================================

interface NotificationItem {
    id: string;
    title: string;
    description: string;
    time: string;
    type: 'info' | 'success' | 'warning' | 'error' | 'message';
    icon?: React.ReactNode;
}

interface AnimatedListCardProps {
    title?: string;
    data?: {
        items?: NotificationItem[];
    };
    config?: {
        showTitle?: boolean;
        delay?: number;
        maxItems?: number;
    };
    style?: any;
}

const getNotificationIcon = (type: string) => {
    const icons: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
        info: { icon: <Info className="w-4 h-4" />, color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.15)' },
        success: { icon: <CheckCircle className="w-4 h-4" />, color: '#22c55e', bg: 'rgba(34, 197, 94, 0.15)' },
        warning: { icon: <AlertCircle className="w-4 h-4" />, color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
        error: { icon: <AlertCircle className="w-4 h-4" />, color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
        message: { icon: <MessageSquare className="w-4 h-4" />, color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)' },
    };
    return icons[type] || icons.info;
};

const defaultNotifications: NotificationItem[] = [
    { id: '1', title: 'New Analysis Complete', description: 'AAPL stock analysis finished', time: '2m ago', type: 'success' },
    { id: '2', title: 'Price Alert', description: 'TSLA crossed $250 threshold', time: '5m ago', type: 'warning' },
    { id: '3', title: 'Agent Message', description: 'Research agent found 3 insights', time: '12m ago', type: 'message' },
    { id: '4', title: 'System Update', description: 'New features available', time: '1h ago', type: 'info' },
];

export const AnimatedListCard: React.FC<AnimatedListCardProps> = ({
    title = "Activity Feed",
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const delay = config.delay || 2000;
    const items = data.items || defaultNotifications;

    return (
        <div className="h-full flex flex-col">
            {showTitle && (
                <div className="px-4 py-3 border-b border-white/10">
                    <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
                        <Bell className="w-3.5 h-3.5 text-primary" />
                        {title}
                    </h3>
                </div>
            )}
            <div className="flex-1 p-4 overflow-hidden">
                <AnimatedList delay={delay} className="gap-3">
                    {items.map((item) => {
                        const { icon, color, bg } = getNotificationIcon(item.type);
                        return (
                            <div
                                key={item.id}
                                className="flex items-start gap-3 p-3 rounded-lg border border-white/10 bg-black/40 hover:bg-white/5 transition-colors"
                            >
                                <div
                                    className="p-2 rounded-lg shrink-0"
                                    style={{ backgroundColor: bg, color }}
                                >
                                    {item.icon || icon}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="text-sm font-medium text-foreground truncate">{item.title}</span>
                                        <span className="text-[10px] text-muted-foreground shrink-0">{item.time}</span>
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-0.5 truncate">{item.description}</p>
                                </div>
                            </div>
                        );
                    })}
                </AnimatedList>
            </div>
        </div>
    );
};

// ============================================================================
// BENTO GRID CARD - Aceternity
// Perfect for: Dashboard Overview, Feature Showcase, Multi-Metric Display
// ============================================================================

interface BentoItem {
    id: string;
    title: string;
    description: string;
    icon?: string;
    className?: string;
    header?: React.ReactNode;
}

interface BentoGridCardProps {
    title?: string;
    data?: {
        items?: BentoItem[];
    };
    config?: {
        showTitle?: boolean;
        columns?: 2 | 3;
    };
    style?: any;
}

const getIconComponent = (iconName?: string) => {
    const icons: Record<string, React.ReactNode> = {
        chart: <BarChart3 className="w-4 h-4" />,
        file: <FileText className="w-4 h-4" />,
        users: <Users className="w-4 h-4" />,
        trending: <TrendingUp className="w-4 h-4" />,
        zap: <Zap className="w-4 h-4" />,
    };
    return icons[iconName || 'zap'] || <Zap className="w-4 h-4" />;
};

const Skeleton = () => (
    <div className="flex flex-1 w-full h-full min-h-[4rem] rounded-xl bg-gradient-to-br from-neutral-900 to-neutral-800 dark:from-neutral-900 dark:to-neutral-800" />
);

const defaultBentoItems: BentoItem[] = [
    { id: '1', title: 'Analytics', description: 'Track your performance metrics', icon: 'chart', className: 'md:col-span-2' },
    { id: '2', title: 'Reports', description: 'Generate detailed reports', icon: 'file' },
    { id: '3', title: 'Team', description: 'Collaborate with your team', icon: 'users' },
    { id: '4', title: 'Growth', description: 'Monitor your growth', icon: 'trending', className: 'md:col-span-2' },
];

export const BentoGridCard: React.FC<BentoGridCardProps> = ({
    title = "Dashboard Overview",
    data = {},
    config = {},
    style = {}
}) => {
    const showTitle = config.showTitle !== false;
    const items = data.items || defaultBentoItems;

    return (
        <div className="h-full flex flex-col">
            {showTitle && (
                <div className="px-4 py-3 border-b border-white/10">
                    <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
                        <Zap className="w-3.5 h-3.5 text-primary" />
                        {title}
                    </h3>
                </div>
            )}
            <div className="flex-1 p-4 overflow-auto">
                <BentoGrid className="max-w-none md:auto-rows-[8rem] gap-3">
                    {items.map((item) => (
                        <BentoGridItem
                            key={item.id}
                            title={item.title}
                            description={item.description}
                            header={<Skeleton />}
                            icon={
                                <div className="p-1.5 rounded bg-primary/10 text-primary w-fit">
                                    {getIconComponent(item.icon)}
                                </div>
                            }
                            className={cn(
                                "border-white/10 bg-black/40 dark:bg-black/40",
                                item.className
                            )}
                        />
                    ))}
                </BentoGrid>
            </div>
        </div>
    );
};
