import React, { useEffect } from 'react';
import { useAppStore } from '@/store';
import {
    Terminal, Pause, Play, Trash2, X,
    Filter, Download, ChevronDown, Activity, Bell, Check, Clock, MailOpen,
    AlertTriangle, Info, AlertCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import ReactMarkdown from 'react-markdown';

interface InboxPanelProps {
    onClose: () => void;
}

export const InboxPanel: React.FC<InboxPanelProps> = ({ onClose }) => {
    const {
        notifications,
        fetchNotifications,
        markAsRead,
        deleteNotification,
        markAllAsRead
    } = useAppStore();

    useEffect(() => {
        fetchNotifications();
        // Poll every minute
        const interval = setInterval(fetchNotifications, 60000);
        return () => clearInterval(interval);
    }, [fetchNotifications]);

    const getPriorityIcon = (priority: number) => {
        switch (priority) {
            case 3: return <AlertCircle className="w-4 h-4 text-red-500" />;
            case 2: return <AlertTriangle className="w-4 h-4 text-orange-500" />;
            default: return <Info className="w-4 h-4 text-blue-500" />;
        }
    };

    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        const now = new Date();
        const diff = now.getTime() - date.getTime();

        // If less than 24 hours, show relative
        if (diff < 24 * 60 * 60 * 1000) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        return date.toLocaleDateString();
    };

    const sortedNotifications = [...notifications].sort((a, b) => {
        // Sort by read status (unread first), then priority (high first), then time (newest first)
        if (a.is_read !== b.is_read) return a.is_read ? 1 : -1;
        if (a.priority !== b.priority) return b.priority - a.priority;
        return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });

    return (
        <div className="w-[400px] h-[calc(100vh-80px)] flex flex-col border-l border-white/10 shadow-2xl animate-in slide-in-from-right duration-300 absolute right-0 top-14 z-50 rounded-l-xl overflow-hidden bg-[#09090b] border-l border-white/10 shadow-black/50">
            <div className="p-4 border-b border-border/50 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <Bell className="w-4 h-4 text-neon-yellow" />
                    <h2 className="font-semibold text-sm tracking-tight">Inbox</h2>
                    <Badge variant="outline" className="text-[10px] h-5 px-1.5 border-neon-yellow/30 text-neon-yellow">
                        {notifications.filter(n => !n.is_read).length} Unread
                    </Badge>
                </div>
                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 hover:bg-white/10 hover:text-green-400"
                        title="Mark all as read"
                        onClick={() => markAllAsRead()}
                    >
                        <Check className="w-4 h-4" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 hover:bg-white/10"
                        onClick={onClose}
                    >
                        <X className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            <ScrollArea className="flex-1">
                <div className="flex flex-col p-2 gap-2">
                    {sortedNotifications.length === 0 ? (
                        <div className="flex flex-col items-center justify-center p-8 text-center opacity-50 space-y-2">
                            <MailOpen className="w-12 h-12 stroke-1" />
                            <p className="text-sm">All caught up!</p>
                        </div>
                    ) : (
                        sortedNotifications.map(notification => (
                            <div
                                key={notification.id}
                                className={cn(
                                    "p-3 rounded-lg border transition-all duration-200 group relative",
                                    notification.is_read
                                        ? "bg-transparent border-transparent opacity-60 hover:opacity-100 hover:bg-white/5"
                                        : "bg-white/5 border-white/10 shadow-sm"
                                )}
                            >
                                <div className="flex items-start justify-between gap-3 mb-1.5">
                                    <div className="flex items-center gap-2 min-w-0">
                                        {getPriorityIcon(notification.priority)}
                                        <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider truncate">
                                            {notification.source}
                                        </span>
                                    </div>
                                    <span className="text-[10px] text-muted-foreground whitespace-nowrap flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {formatTime(notification.timestamp)}
                                    </span>
                                </div>

                                <h3 className={cn(
                                    "text-sm font-medium mb-1 leading-snug",
                                    !notification.is_read && "text-neon-yellow"
                                )}>
                                    {notification.title}
                                </h3>

                                <div className="text-xs text-muted-foreground prose prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-black/30 prose-pre:p-2 prose-pre:rounded-md">
                                    <ReactMarkdown>{notification.body}</ReactMarkdown>
                                </div>

                                {/* Action Buttons */}
                                <div className="mt-3 flex gap-2">
                                    {notification.metadata?.run_id && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-7 text-[10px] gap-1.5 border-neon-yellow/30 bg-neon-yellow/5 hover:bg-neon-yellow/10"
                                            onClick={() => {
                                                useAppStore.getState().setSidebarTab('runs');
                                                useAppStore.getState().setCurrentRun(notification.metadata.run_id);
                                                onClose();
                                            }}
                                        >
                                            <Activity className="w-3 h-3" />
                                            View Run
                                        </Button>
                                    )}
                                    {notification.metadata?.file_path && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-7 text-[10px] gap-1.5 border-neon-cyan/30 bg-neon-cyan/5 hover:bg-neon-cyan/10"
                                            onClick={() => {
                                                const path = notification.metadata.file_path;
                                                // Map to relative if needed or just use as is
                                                const filename = path.split('/').pop();
                                                useAppStore.getState().setSidebarTab('notes');
                                                // Assuming we can select the node by filename or path
                                                // For now, let's at least switch to the tab
                                                onClose();
                                            }}
                                        >
                                            <Clock className="w-3 h-3" />
                                            Open Report
                                        </Button>
                                    )}
                                </div>

                                <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 bg-background/80 backdrop-blur-sm rounded-md shadow-sm">
                                    {!notification.is_read && (
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                markAsRead(notification.id);
                                            }}
                                            className="p-1 hover:text-green-400 transition-colors"
                                            title="Mark as read"
                                        >
                                            <Check className="w-3.5 h-3.5" />
                                        </button>
                                    )}
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            deleteNotification(notification.id);
                                        }}
                                        className="p-1 hover:text-red-400 transition-colors"
                                        title="Delete"
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </ScrollArea>
        </div>
    );
};
