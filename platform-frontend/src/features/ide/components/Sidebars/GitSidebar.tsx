import React from 'react';
import { GitBranch, GitCommit, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const GitSidebar: React.FC = () => {
    return (
        <div className="h-full flex flex-col bg-background p-4 text-center">
            <div className="flex flex-col items-center justify-center flex-1 space-y-4 opacity-50">
                <div className="p-4 rounded-full bg-muted">
                    <GitBranch className="w-8 h-8 text-muted-foreground" />
                </div>
                <div>
                    <h3 className="text-sm font-semibold mb-1">Source Control</h3>
                    <p className="text-xs text-muted-foreground max-w-[200px] mx-auto leading-relaxed">
                        Git integration is currently being implemented. Check back soon for status updates and commit features.
                    </p>
                </div>

                <Button variant="outline" size="sm" className="gap-2 text-xs" disabled>
                    <GitCommit className="w-3.5 h-3.5" />
                    Initialize Repo
                </Button>
            </div>

            <div className="mt-auto pt-4 border-t border-border/50">
                <div className="flex items-center gap-2 text-[10px] text-yellow-500/80 justify-center">
                    <AlertCircle className="w-3 h-3" />
                    <span>Beta Feature</span>
                </div>
            </div>
        </div>
    );
};
