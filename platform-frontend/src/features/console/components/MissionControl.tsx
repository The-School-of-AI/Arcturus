import React, { useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store';
import {
    Terminal, Pause, Play, Trash2,
    Filter, Download, ChevronDown, Activity
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export const MissionControl: React.FC = () => {
    const { events, startEventStream, stopEventStream, isStreaming, clearEvents } = useAppStore();
    const scrollRef = useRef<HTMLDivElement>(null);
    const [autoScroll, setAutoScroll] = useState(true);
    const [filter, setFilter] = useState<string | null>(null);

    // Start stream on mount
    useEffect(() => {
        startEventStream();
        return () => stopEventStream();
    }, [startEventStream, stopEventStream]);

    // Auto-scroll logic
    useEffect(() => {
        if (autoScroll && scrollRef.current) {
            const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
            if (scrollContainer) {
                scrollContainer.scrollTop = scrollContainer.scrollHeight;
            }
        }
    }, [events, autoScroll]);

    const filteredEvents = filter
        ? events.filter(e => e.type.includes(filter) || e.source.includes(filter))
        : events;

    const getEventColor = (type: string) => {
        if (type.includes('error') || type.includes('fail')) return 'text-red-400';
        if (type.includes('complete') || type.includes('success')) return 'text-green-400';
        if (type.includes('start')) return 'text-neon-yellow';
        if (type.includes('tool')) return 'text-cyan-400';
        return 'text-muted-foreground';
    };

    return (
        <div className="flex flex-col h-full bg-[#09090b] font-mono text-xs">
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-white/10 bg-black/40 backdrop-blur-md">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-neon-green">
                        <Terminal className="w-4 h-4" />
                        <h2 className="font-bold tracking-wider uppercase text-sm">Mission Control</h2>
                    </div>

                    <div className="h-4 w-px bg-white/10" />

                    <Badge variant="outline" className={cn(
                        "h-5 px-1.5 border-transparent bg-white/5",
                        isStreaming ? "text-green-400 animate-pulse" : "text-muted-foreground"
                    )}>
                        <Activity className="w-3 h-3 mr-1" />
                        {isStreaming ? "LIVE" : "OFFLINE"}
                    </Badge>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => setAutoScroll(!autoScroll)}
                        title={autoScroll ? "Pause Scroll" : "Resume Scroll"}
                    >
                        {autoScroll ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 hover:text-red-400 hover:bg-red-500/10"
                        onClick={clearEvents}
                        title="Clear Console"
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                </div>
            </div>

            {/* Filter Bar */}
            <div className="flex items-center gap-2 p-2 border-b border-white/10 bg-black/20">
                <Filter className="w-3 h-3 text-muted-foreground ml-2" />
                <input
                    className="bg-transparent border-none text-muted-foreground focus:text-foreground outline-none text-[11px] w-full placeholder:text-muted-foreground/50"
                    placeholder="Filter events (e.g. 'error', 'tool_call')..."
                    value={filter || ''}
                    onChange={(e) => setFilter(e.target.value)}
                />
                {filter && (
                    <button onClick={() => setFilter('')} className="text-[10px] text-muted-foreground hover:text-white px-2">
                        Clear
                    </button>
                )}
            </div>

            {/* Log Area */}
            <ScrollArea className="flex-1" ref={scrollRef}>
                <div className="flex flex-col p-2 font-mono">
                    {filteredEvents.length === 0 ? (
                        <div className="py-20 text-center opacity-30 select-none">
                            <Terminal className="w-12 h-12 mx-auto mb-2" />
                            <p>Waiting for system telemetry...</p>
                        </div>
                    ) : (
                        filteredEvents.map((event, i) => (
                            <div key={i} className="flex gap-3 px-2 py-1 hover:bg-white/5 rounded-sm group leading-relaxed">
                                {/* Timestamp */}
                                <span className="opacity-40 shrink-0 select-none">
                                    {event.timestamp.split('T')[1].split('.')[0]}
                                </span>

                                {/* Source */}
                                <span className="text-blue-400 shrink-0 w-24 truncate select-none text-right">
                                    {event.source}
                                </span>

                                {/* Type */}
                                <span className={cn("shrink-0 w-32 truncate font-bold select-none", getEventColor(event.type))}>
                                    {event.type}
                                </span>

                                {/* Data */}
                                <span className="text-muted-foreground break-all whitespace-pre-wrap">
                                    {JSON.stringify(event.data)}
                                </span>
                            </div>
                        ))
                    )}
                </div>
            </ScrollArea>
        </div>
    );
};
