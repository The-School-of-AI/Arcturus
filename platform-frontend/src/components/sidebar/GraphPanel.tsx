import React from 'react';
import { Network, Info } from 'lucide-react';
import { useAppStore } from '@/store';

export const GraphPanel: React.FC = () => {
    const currentSpaceId = useAppStore((s) => s.currentSpaceId);
    const spaces = useAppStore((s) => s.spaces);
    const setCurrentSpaceId = useAppStore((s) => s.setCurrentSpaceId);

    const currentSpace = currentSpaceId
        ? spaces.find((s) => s.space_id === currentSpaceId)
        : null;

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground p-4 space-y-4">
            <div className="flex items-center gap-2 text-muted-foreground">
                <Network className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider">Knowledge Graph</span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
                Entities and relationships extracted from your memories. Pan, zoom, and click nodes to explore.
            </p>
            <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Space</label>
                <select
                    value={currentSpaceId ?? '__global__'}
                    onChange={(e) => setCurrentSpaceId(e.target.value === '__global__' ? null : e.target.value)}
                    className="w-full h-8 px-2 rounded-md bg-muted border border-border text-sm text-foreground"
                >
                    <option value="__global__">Global (all)</option>
                    {spaces.map((s) => (
                        <option key={s.space_id} value={s.space_id}>
                            {s.name || 'Unnamed Space'}
                        </option>
                    ))}
                </select>
                {currentSpace && (
                    <p className="text-xs text-muted-foreground">
                        Filtering: &quot;{currentSpace.name}&quot;
                    </p>
                )}
            </div>
            <div className="flex items-start gap-2 p-2 rounded-lg bg-muted/50 border border-border/50">
                <Info className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />
                <p className="text-xs text-muted-foreground leading-relaxed">
                    Uses NetworkX (local) or Neo4j. Click &quot;Populate Graph&quot; in the main view to extract entities from your memories.
                </p>
            </div>
        </div>
    );
};
