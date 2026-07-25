import React from 'react';
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuSeparator,
    ContextMenuSub,
    ContextMenuSubContent,
    ContextMenuSubTrigger,
    ContextMenuTrigger,
} from '@/components/ui/context-menu';
import {
    Plus, Compass, Flame, Focus, Bug,
    Maximize2, Eye, ScrollText, Copy, RotateCcw
} from 'lucide-react';
import { useAppStore } from '@/store';
import type { UIMode } from '@/store';

// ── Canvas Context Menu (right-click on empty canvas) ────────────────────────

export const CanvasContextMenu: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const setUIMode = useAppStore(state => state.setUIMode);
    const uiMode = useAppStore(state => state.uiMode);
    const setIsNewRunOpen = useAppStore(state => state.setIsNewRunOpen);
    const setSidebarTab = useAppStore(state => state.setSidebarTab);

    const modes: { id: UIMode; label: string; icon: any }[] = [
        { id: 'explore', label: 'Explore', icon: Compass },
        { id: 'execute', label: 'Execute', icon: Flame },
        { id: 'focus', label: 'Focus', icon: Focus },
        { id: 'debug', label: 'Debug', icon: Bug },
    ];

    return (
        <ContextMenu>
            <ContextMenuTrigger asChild>
                {children}
            </ContextMenuTrigger>
            <ContextMenuContent className="w-52">
                <ContextMenuItem
                    onClick={() => {
                        setSidebarTab('runs');
                        setTimeout(() => setIsNewRunOpen(true), 100);
                    }}
                    className="gap-2"
                >
                    <Plus className="w-3.5 h-3.5" />
                    New Agent Run
                </ContextMenuItem>

                <ContextMenuSeparator />

                <ContextMenuSub>
                    <ContextMenuSubTrigger className="gap-2">
                        <Eye className="w-3.5 h-3.5" />
                        Switch Mode
                    </ContextMenuSubTrigger>
                    <ContextMenuSubContent className="w-44">
                        {modes.map((mode) => {
                            const Icon = mode.icon;
                            return (
                                <ContextMenuItem
                                    key={mode.id}
                                    onClick={() => setUIMode(mode.id)}
                                    className="gap-2"
                                >
                                    <Icon className="w-3.5 h-3.5" />
                                    {mode.label}
                                    {uiMode === mode.id && (
                                        <span className="ml-auto text-2xs text-primary font-bold">Active</span>
                                    )}
                                </ContextMenuItem>
                            );
                        })}
                    </ContextMenuSubContent>
                </ContextMenuSub>

                <ContextMenuSeparator />

                <ContextMenuItem
                    onClick={() => {
                        // Dispatch fit view via ReactFlow
                        const fitBtn = document.querySelector('.react-flow__controls-fitview') as HTMLButtonElement;
                        fitBtn?.click();
                    }}
                    className="gap-2"
                >
                    <Maximize2 className="w-3.5 h-3.5" />
                    Fit View
                </ContextMenuItem>
            </ContextMenuContent>
        </ContextMenu>
    );
};

// ── Node Context Menu (right-click on a node) ────────────────────────────────

interface NodeContextMenuProps {
    children: React.ReactNode;
    nodeId: string;
    onFocus?: () => void;
}

export const NodeContextMenu: React.FC<NodeContextMenuProps> = ({ children, nodeId, onFocus }) => {
    const setUIMode = useAppStore(state => state.setUIMode);
    const selectNode = useAppStore(state => state.selectNode);
    const nodes = useAppStore(state => state.nodes);
    const currentRun = useAppStore(state => state.currentRun);
    const executeNode = useAppStore(state => state.executeNode);

    const node = nodes.find(n => n.id === nodeId);

    return (
        <ContextMenu>
            <ContextMenuTrigger asChild>
                {children}
            </ContextMenuTrigger>
            <ContextMenuContent className="w-48">
                <ContextMenuItem
                    onClick={() => {
                        selectNode(nodeId);
                        setUIMode('focus');
                    }}
                    className="gap-2"
                >
                    <Focus className="w-3.5 h-3.5" />
                    Focus on This
                </ContextMenuItem>

                <ContextMenuItem
                    onClick={() => {
                        selectNode(nodeId);
                        setUIMode('debug');
                    }}
                    className="gap-2"
                >
                    <Bug className="w-3.5 h-3.5" />
                    Debug This Node
                </ContextMenuItem>

                {node?.data.output && (
                    <ContextMenuItem
                        onClick={() => {
                            navigator.clipboard.writeText(node.data.output || '');
                        }}
                        className="gap-2"
                    >
                        <Copy className="w-3.5 h-3.5" />
                        Copy Output
                    </ContextMenuItem>
                )}

                {currentRun && node?.data.status === 'completed' && (
                    <>
                        <ContextMenuSeparator />
                        <ContextMenuItem
                            onClick={() => {
                                executeNode(currentRun.id, nodeId, 'single');
                            }}
                            className="gap-2"
                        >
                            <RotateCcw className="w-3.5 h-3.5" />
                            Re-run This Node
                        </ContextMenuItem>
                    </>
                )}

                <ContextMenuSeparator />

                <ContextMenuItem
                    onClick={() => {
                        selectNode(nodeId);
                        useAppStore.getState().toggleFloatingPanel('agent-detail');
                    }}
                    className="gap-2"
                >
                    <ScrollText className="w-3.5 h-3.5" />
                    Show Details Panel
                </ContextMenuItem>
            </ContextMenuContent>
        </ContextMenu>
    );
};
