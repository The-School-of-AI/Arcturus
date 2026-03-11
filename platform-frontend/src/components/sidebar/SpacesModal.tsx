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

/** Phase 4: Spaces management modal — select or create space, Ok applies selection and closes. */
export const SpacesModal: React.FC<{
    isOpen: boolean;
    onClose: () => void;
}> = ({ isOpen, onClose }) => {
    const {
        spaces,
        currentSpaceId,
        fetchSpaces,
        createSpace,
        setCurrentSpaceId,
    } = useAppStore();
    const [selectedId, setSelectedId] = useState<string | null>(currentSpaceId);
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [newName, setNewName] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [keepOnDeviceOnly, setKeepOnDeviceOnly] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            fetchSpaces();
            setSelectedId(currentSpaceId);
        }
    }, [isOpen, fetchSpaces, currentSpaceId]);

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
            setSelectedId(space.space_id);
        } catch (e: any) {
            setError(e?.message || 'Failed to create space');
        } finally {
            setIsCreating(false);
        }
    };

    const handleOk = () => {
        setCurrentSpaceId(selectedId);
        onClose();
    };

    return (
        <>
            <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                    <DialogHeader>
                        <DialogTitle className="text-foreground">Manage Spaces</DialogTitle>
                    </DialogHeader>
                    <p className="text-xs text-muted-foreground -mt-2">
                        Select a space to filter runs and memories. Available from all panels.
                    </p>
                    <div className="space-y-2 max-h-[320px] overflow-y-auto py-2">
                        {/* Global option */}
                        <button
                            onClick={() => setSelectedId(null)}
                            className={cn(
                                'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors',
                                selectedId === null
                                    ? 'bg-primary/10 text-primary border border-primary/30'
                                    : 'hover:bg-muted/50 text-foreground border border-transparent'
                            )}
                        >
                            <FolderOpen className="w-4 h-4 shrink-0 text-muted-foreground" />
                            <span className="font-medium truncate">Global (all runs)</span>
                        </button>
                        {spaces.map((s) => (
                            <button
                                key={s.space_id}
                                onClick={() => setSelectedId(s.space_id)}
                                className={cn(
                                    'w-full flex flex-col gap-0.5 px-3 py-2 rounded-lg text-left transition-colors',
                                    selectedId === s.space_id
                                        ? 'bg-primary/10 text-primary border border-primary/30'
                                        : 'hover:bg-muted/50 text-foreground border border-transparent'
                                )}
                            >
                                <span className="font-medium truncate text-sm">{s.name || 'Unnamed Space'}</span>
                                {s.description && (
                                    <span className="text-xs text-muted-foreground truncate">{s.description}</span>
                                )}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
                        <Button
                            variant="outline"
                            size="sm"
                            className="border-border text-foreground"
                            onClick={() => setIsCreateOpen(true)}
                        >
                            <Plus className="w-3.5 h-3.5 mr-1" />
                            New Space
                        </Button>
                        <DialogFooter className="gap-2 p-0 m-0 border-0">
                            <Button variant="outline" onClick={onClose} className="border-border text-foreground">
                                Cancel
                            </Button>
                            <Button onClick={handleOk} className="bg-neon-yellow text-white hover:bg-neon-yellow/90">
                                Ok
                            </Button>
                        </DialogFooter>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Nested create dialog */}
            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                    <DialogHeader>
                        <DialogTitle className="text-foreground">Create Space</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <div className="space-y-2">
                            <Label htmlFor="modal-space-name" className="text-sm text-muted-foreground dark:text-foreground/80">
                                Name
                            </Label>
                            <Input
                                id="modal-space-name"
                                placeholder="e.g. Biology 101, Q2 Launch"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                className="bg-muted border-input dark:border-muted-foreground/50 text-foreground placeholder:text-muted-foreground dark:placeholder:text-foreground/50"
                                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="modal-space-desc" className="text-sm text-muted-foreground dark:text-foreground/80">
                                Description (optional)
                            </Label>
                            <Textarea
                                id="modal-space-desc"
                                placeholder="Brief description of this space"
                                value={newDescription}
                                onChange={(e) => setNewDescription(e.target.value)}
                                className="bg-muted border-input dark:border-muted-foreground/50 text-foreground placeholder:text-muted-foreground dark:placeholder:text-foreground/50 min-h-[60px] resize-none"
                                rows={2}
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <Checkbox
                                id="modal-space-local-only"
                                checked={keepOnDeviceOnly}
                                onCheckedChange={(v) => setKeepOnDeviceOnly(v === true)}
                                className="border-input dark:border-muted-foreground/70 dark:data-[state=unchecked]:bg-muted/80"
                            />
                            <Label htmlFor="modal-space-local-only" className="text-sm text-muted-foreground dark:text-foreground/80 cursor-pointer">
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
        </>
    );
};
