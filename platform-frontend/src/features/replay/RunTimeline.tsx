import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Play, Pause, SkipBack, SkipForward, Clock } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useAppStore } from '@/store';
import { cn } from '@/lib/utils';
import type { PlatformNode, PlatformEdge } from '@/types';

export const RunTimeline: React.FC = () => {
    const {
        nodes,
        edges,
        currentRun,
        isReplayMode,
        toggleReplayMode,
        setNodes,
        setEdges,
        selectNode
    } = useAppStore();

    const [isPlaying, setIsPlaying] = useState(false);
    const [currentStep, setCurrentStep] = useState(-1);

    // Use refs to store the full graph so we don't lose it during replay
    const savedNodesRef = useRef<PlatformNode[]>([]);
    const savedEdgesRef = useRef<PlatformEdge[]>([]);

    // Calculate total steps based on SAVED nodes (not current display nodes)
    const totalSteps = savedNodesRef.current.length || nodes.length;
    const maxStep = Math.max(0, totalSteps - 1);

    // Save the full graph state when nodes change and we're not in replay mode
    useEffect(() => {
        if (nodes.length > 0 && !isReplayMode) {
            savedNodesRef.current = [...nodes];
            savedEdgesRef.current = [...edges];
        }
    }, [nodes, edges, isReplayMode]);

    // Reset when run changes
    useEffect(() => {
        setCurrentStep(-1);
        setIsPlaying(false);
        toggleReplayMode(false);
        savedNodesRef.current = [];
        savedEdgesRef.current = [];
    }, [currentRun?.id]);

    // Load a specific step - show nodes up to that index
    const loadStep = useCallback((stepIndex: number) => {
        const savedNodes = savedNodesRef.current;
        const savedEdges = savedEdgesRef.current;

        if (stepIndex < 0 || savedNodes.length === 0) return;
        if (stepIndex >= savedNodes.length) stepIndex = savedNodes.length - 1;

        setCurrentStep(stepIndex);
        toggleReplayMode(true);

        // Show only nodes up to this step
        const visibleNodes = savedNodes.slice(0, stepIndex + 1).map((node, i) => ({
            ...node,
            data: {
                ...node.data,
                status: (i === stepIndex ? 'running' : 'completed') as 'running' | 'completed' | 'failed' | 'pending'
            }
        }));

        // Show edges that connect visible nodes
        const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
        const visibleEdges = savedEdges.filter(
            e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
        );

        setNodes(visibleNodes);
        setEdges(visibleEdges);

        // Select the current node
        if (visibleNodes.length > 0) {
            selectNode(visibleNodes[stepIndex].id);
        }
    }, [setNodes, setEdges, selectNode, toggleReplayMode]);

    // Exit replay mode and restore full graph
    const exitReplay = useCallback(() => {
        setCurrentStep(-1);
        setIsPlaying(false);
        toggleReplayMode(false);
        if (savedNodesRef.current.length > 0) {
            setNodes(savedNodesRef.current);
            setEdges(savedEdgesRef.current);
        }
    }, [setNodes, setEdges, toggleReplayMode]);

    // Autoplay logic  
    useEffect(() => {
        if (!isPlaying) return;

        const savedNodes = savedNodesRef.current;
        if (savedNodes.length === 0) {
            setIsPlaying(false);
            return;
        }

        const interval = setInterval(() => {
            setCurrentStep(prev => {
                const next = prev + 1;
                if (next < savedNodes.length) {
                    // Use setTimeout to avoid state conflicts
                    setTimeout(() => loadStep(next), 0);
                    return next;
                } else {
                    setIsPlaying(false);
                    return prev;
                }
            });
        }, 1000);

        return () => clearInterval(interval);
    }, [isPlaying, loadStep]);

    // Handle play button - start from beginning if not in replay mode
    const handlePlayPause = () => {
        if (savedNodesRef.current.length === 0 && nodes.length > 0) {
            // Save current state before starting
            savedNodesRef.current = [...nodes];
            savedEdgesRef.current = [...edges];
        }

        if (isPlaying) {
            setIsPlaying(false);
        } else {
            if (!isReplayMode || currentStep < 0) {
                loadStep(0);
            }
            setIsPlaying(true);
        }
    };

    const progress = totalSteps > 0 && currentStep >= 0
        ? ((currentStep) / maxStep) * 100
        : 0;

    const displayStep = isReplayMode ? currentStep + 1 : totalSteps;
    const displayTotal = totalSteps;

    return (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[600px] h-12 bg-charcoal-800/90 backdrop-blur border border-border rounded-xl shadow-2xl flex items-center px-4 gap-4 z-50">
            <div className="flex items-center gap-1">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:text-neon-yellow"
                    onClick={() => loadStep(Math.max(0, currentStep - 1))}
                    disabled={currentStep <= 0 || totalSteps === 0}
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
                    onClick={handlePlayPause}
                    disabled={totalSteps === 0}
                >
                    {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
                </Button>

                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 hover:text-neon-yellow"
                    onClick={() => loadStep(Math.min(maxStep, currentStep + 1))}
                    disabled={currentStep >= maxStep || totalSteps === 0}
                >
                    <SkipForward className="w-4 h-4" />
                </Button>
            </div>

            <div className="flex-1 flex flex-col justify-center gap-1.5 pt-3">
                <div className="flex justify-between items-center text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                    <span
                        className={cn(
                            isReplayMode && "text-neon-yellow cursor-pointer hover:underline"
                        )}
                        onClick={isReplayMode ? exitReplay : undefined}
                    >
                        {isReplayMode ? "Replay Mode (click to exit)" : "Live View"}
                    </span>
                    <span>{displayStep} / {displayTotal}</span>
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
                    {totalSteps > 1 && Array.from({ length: totalSteps }).map((_, i) => (
                        <div
                            key={i}
                            className="absolute top-0 bottom-0 w-px bg-charcoal-900/50"
                            style={{ left: `${(i / maxStep) * 100}%` }}
                        />
                    ))}

                    <input
                        type="range"
                        min={0}
                        max={maxStep}
                        value={currentStep >= 0 ? currentStep : 0}
                        onChange={(e) => {
                            const val = parseInt(e.target.value);
                            loadStep(val);
                        }}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                        disabled={totalSteps === 0}
                    />
                </div>
            </div>

            <Button variant="ghost" size="sm" className="h-8 gap-2 text-muted-foreground hover:text-foreground">
                <Clock className="w-3 h-3" />
                <span className="text-xs font-mono">1s</span>
            </Button>
        </div>
    );
};
