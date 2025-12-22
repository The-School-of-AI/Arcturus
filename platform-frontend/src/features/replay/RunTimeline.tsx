import React, { useEffect, useState } from 'react';
import { Play, Pause, SkipBack, SkipForward, Clock } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import { mockNodes, mockEdges } from '@/lib/mockData';

export const RunTimeline: React.FC = () => {
    const {
        snapshots,
        currentSnapshotIndex,
        loadSnapshot,
        addSnapshot, // we'll use this to init data
        isReplayMode,
        toggleReplayMode,
        nodes
    } = useAppStore();

    const [isPlaying, setIsPlaying] = useState(false);

    // Mock initialization of snapshots for demo
    useEffect(() => {
        if (snapshots.length === 0) {
            // Generate some dummy snapshots
            const baseTime = Date.now();
            const dummySnapshots = [
                { id: 's1', timestamp: baseTime, nodeId: '1', chatHistory: [], codeContent: '# Step 1: Planning', webUrl: '', webContent: '', htmlOutput: '', graphState: { nodes: [mockNodes[0]], edges: [] } },
                { id: 's2', timestamp: baseTime + 1000, nodeId: '2', chatHistory: [], codeContent: '# Step 2: Retrieval', webUrl: 'https://google.com', webContent: '', htmlOutput: '', graphState: { nodes: mockNodes.slice(0, 2), edges: mockEdges.slice(0, 1) } },
                { id: 's3', timestamp: baseTime + 2000, nodeId: '3', chatHistory: [], codeContent: '# Step 3: Thinking', webUrl: 'https://docs.api', webContent: '', htmlOutput: '', graphState: { nodes: mockNodes.slice(0, 3), edges: mockEdges.slice(0, 2) } },
                { id: 's4', timestamp: baseTime + 3000, nodeId: '4', chatHistory: [], codeContent: '# Step 4: Coding', webUrl: '', webContent: '', htmlOutput: '<h1>Done</h1>', graphState: { nodes: mockNodes, edges: mockEdges } },
            ];
            dummySnapshots.forEach(s => addSnapshot(s as any));
        }
    }, []);

    // Autoplay logic
    useEffect(() => {
        let interval: any;
        if (isPlaying) {
            interval = setInterval(() => {
                const next = currentSnapshotIndex + 1;
                if (next < snapshots.length) {
                    loadSnapshot(next);
                } else {
                    setIsPlaying(false);
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [isPlaying, currentSnapshotIndex, snapshots.length, loadSnapshot]);

    const maxSteps = snapshots.length - 1;
    const progress = snapshots.length > 0 ? (currentSnapshotIndex / maxSteps) * 100 : 0;

    return (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[600px] h-16 bg-charcoal-800/90 backdrop-blur border border-border rounded-xl shadow-2xl flex items-center px-4 gap-4 z-50">
            <div className="flex items-center gap-1">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:text-neon-yellow"
                    onClick={() => loadSnapshot(Math.max(0, currentSnapshotIndex - 1))}
                    disabled={currentSnapshotIndex <= 0}
                >
                    <SkipBack className="w-4 h-4" />
                </Button>

                <Button
                    variant="outline"
                    size="icon"
                    className={cn(
                        "h-10 w-10 rounded-full border-neon-yellow/30 text-neon-yellow hover:bg-neon-yellow/10 hover:border-neon-yellow",
                        isPlaying && "animate-pulse"
                    )}
                    onClick={() => setIsPlaying(!isPlaying)}
                >
                    {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
                </Button>

                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:text-neon-yellow"
                    onClick={() => loadSnapshot(Math.min(maxSteps, currentSnapshotIndex + 1))}
                    disabled={currentSnapshotIndex >= maxSteps}
                >
                    <SkipForward className="w-4 h-4" />
                </Button>
            </div>

            <div className="flex-1 flex flex-col justify-center gap-1.5 pt-1">
                <div className="flex justify-between items-center text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                    <span className={cn(isReplayMode && "text-neon-yellow")}>
                        {isReplayMode ? "Replay Mode" : "Live View"}
                    </span>
                    <span>{currentSnapshotIndex + 1} / {snapshots.length}</span>
                </div>

                <div className="relative h-1.5 bg-background rounded-full overflow-hidden cursor-pointer group">
                    {/* Hover effect bar */}
                    <div className="absolute inset-0 bg-white/5 group-hover:bg-white/10 transition-colors" />

                    {/* Progress Bar */}
                    <div
                        className="absolute h-full bg-neon-yellow transition-[width] duration-300 ease-out"
                        style={{ width: `${progress}%` }}
                    />

                    {/* Ticks */}
                    {snapshots.map((_, i) => (
                        <div
                            key={i}
                            className="absolute top-0 bottom-0 w-px bg-charcoal-900/50"
                            style={{ left: `${(i / maxSteps) * 100}%` }}
                        />
                    ))}

                    <input
                        type="range"
                        min={0}
                        max={maxSteps}
                        value={currentSnapshotIndex}
                        onChange={(e) => {
                            const val = parseInt(e.target.value);
                            loadSnapshot(val);
                            toggleReplayMode(true);
                        }}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                    />
                </div>
            </div>

            <Button variant="ghost" size="sm" className="h-8 gap-2 text-muted-foreground hover:text-foreground">
                <Clock className="w-3 h-3" />
                <span className="text-xs font-mono">150ms</span>
            </Button>
        </div>
    );
};
