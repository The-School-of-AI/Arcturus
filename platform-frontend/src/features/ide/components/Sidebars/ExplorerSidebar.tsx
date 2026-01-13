import React from 'react';
import { ExplorerPanel as OriginalExplorerPanel } from '@/components/sidebar/ExplorerPanel';

export const ExplorerSidebar: React.FC = () => {
    return (
        <div className="h-full bg-background">
            <OriginalExplorerPanel />
        </div>
    );
};
