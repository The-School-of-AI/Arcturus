import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import { FolderOpen, Plus, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';

/** Phase 4: Spaces panel — Perplexity-style project hubs. */
export const SpacesPanel: React.FC = () => {
    const {
        spaces,
        currentSpaceId,
        fetchSpaces,
        createSpace,
        setCurrentSpaceId,
    } = useAppStore();
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [newName, setNewName] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [keepOnDeviceOnly, setKeepOnDeviceOnly] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchSpaces();
    }, [fetchSpaces]);

    const handleCreate = async () => {
        if (!newName.trim()) return;
        setIsCreating(true);
        setError(null);
        try {
            const sync_policy = keepOnDeviceOnly ? 'local_only' : 'sync';
            const space = await createSpace(newName.trim(), newDescription.trim() || undefined, sync_policy);
            setIsCreateOpen(false);
            setNewName('');
            setNewDescription('');
            setKeepOnDeviceOnly(false);
            setCurrentSpaceId(space.space_id);
        } catch (e: any) {
            setError(e?.message || 'Failed to create space');
        } finally {
            setIsCreating(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-transparent text-foreground">
            <div className="p-2 border-b border-border/50 bg-muted/20 flex items-center justify-between shrink-0">
                <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                    Project Hubs
                </span>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background/80"
                    onClick={() => setIsCreateOpen(true)}
                    title="Create Space"
                >
                    <Plus className="w-4 h-4" />
                </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {/* Global option */}
                <button
                    onClick={() => setCurrentSpaceId(null)}
                    className={cn(
                        'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors',
                        currentSpaceId === null
                            ? 'bg-primary/10 text-primary border border-primary/30'
                            : 'hover:bg-muted/50 text-foreground'
                    )}
                >
                    <FolderOpen className="w-4 h-4 shrink-0 text-muted-foreground" />
                    <span className="font-medium truncate">Global (all runs)</span>
                </button>
                {spaces.map((s) => (
                    <button
                        key={s.space_id}
                        onClick={() => setCurrentSpaceId(s.space_id)}
                        className={cn(
                            'w-full flex flex-col gap-0.5 px-3 py-2 rounded-lg text-left transition-colors',
                            currentSpaceId === s.space_id
                                ? 'bg-primary/10 text-primary border border-primary/30'
                                : 'hover:bg-muted/50 text-foreground'
                        )}
                    >
                        <span className="font-medium truncate text-sm">{s.name || 'Unnamed Space'}</span>
                        {s.description && (
                            <span className="text-xs text-muted-foreground truncate">{s.description}</span>
                        )}
                    </button>
                ))}
                {spaces.length === 0 && (
                    <div className="py-8 text-center text-muted-foreground text-sm">
                        <FolderOpen className="w-10 h-10 mx-auto mb-2 opacity-50" />
                        <p>No spaces yet.</p>
                        <p className="text-xs mt-1">Create one to organize runs and memories by project.</p>
                        <Button
                            variant="outline"
                            size="sm"
                            className="mt-3"
                            onClick={() => setIsCreateOpen(true)}
                        >
                            <Plus className="w-3 h-3 mr-1" />
                            Create Space
                        </Button>
                    </div>
                )}
            </div>

            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                    <DialogHeader>
                        <DialogTitle className="text-foreground">Create Space</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <div className="space-y-2">
                            <Label htmlFor="space-name" className="text-sm text-muted-foreground dark:text-foreground/80">
                                Name
                            </Label>
                            <Input
                                id="space-name"
                                placeholder="e.g. Biology 101, Q2 Launch"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                className="bg-muted border-input dark:border-muted-foreground/50 text-foreground placeholder:text-muted-foreground dark:placeholder:text-foreground/50"
                                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="space-desc" className="text-sm text-muted-foreground dark:text-foreground/80">
                                Description (optional)
                            </Label>
                            <Textarea
                                id="space-desc"
                                placeholder="Brief description of this space"
                                value={newDescription}
                                onChange={(e) => setNewDescription(e.target.value)}
                                className="bg-muted border-input dark:border-muted-foreground/50 text-foreground placeholder:text-muted-foreground dark:placeholder:text-foreground/50 min-h-[60px] resize-none"
                                rows={2}
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="space-local-only"
                                checked={keepOnDeviceOnly}
                                onCheckedChange={(v) => setKeepOnDeviceOnly(v === true)}
                                className="border-input dark:border-muted-foreground/70 dark:data-[state=unchecked]:bg-muted/80"
                            />
                            <Label htmlFor="space-local-only" className="text-sm text-muted-foreground dark:text-foreground/80 cursor-pointer">
                                Keep on this device only (don&apos;t sync to cloud)
                            </Label>
                        </div>
                        {error && (
                            <p className="text-sm text-red-500">{error}</p>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCreate}
                            disabled={!newName.trim() || isCreating}
                        >
                            {isCreating ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                'Create'
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
