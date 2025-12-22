import React from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { WorkspacePanel } from '../workspace/WorkspacePanel';
import { GraphCanvas } from '../graph/GraphCanvas';
import { RunTimeline } from '@/features/replay/RunTimeline';

export const AppLayout: React.FC = () => {
    return (
        <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden font-sans select-none">
            <Header />

            <div className="flex-1 flex overflow-hidden">
                {/* Left Sidebar: Run Library */}
                <div className="w-64 border-r border-border bg-card/50 backdrop-blur-sm flex-shrink-0">
                    <Sidebar />
                </div>

                {/* Center Canvas */}
                <div className="flex-1 relative bg-grid-dots overflow-hidden">
                    <GraphCanvas />

                    {/* Floating Timeline Control */}
                    <RunTimeline />
                </div>

                {/* Right Workspace Panel */}
                <div className="w-[450px] border-l border-border bg-card/50 backdrop-blur-sm flex-shrink-0 flex flex-col">
                    <WorkspacePanel />
                </div>
            </div>
        </div>
    );
};
