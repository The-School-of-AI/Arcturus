import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import { FolderOpen, Plus, Loader2, Laptop, User, Users, Settings2 } from 'lucide-react';
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
import { cn } from '@/lib/utils';
import type { SpaceSyncPolicy } from '@/types';

/** Pre-configured space templates (Shared Space step). */
const SPACE_TEMPLATES: Array<{
    id: string;
    sync_policy: SpaceSyncPolicy;
    label: string;
    description: string;
    guestAllowed: boolean;
    icon: React.ReactNode;
}> = [
    {
        id: 'computer_only',
        sync_policy: 'local_only',
        label: 'Computer Only',
        description: 'Stays on this device only; not synced to the cloud. Use for private or offline work.',
        guestAllowed: true,
        icon: <Laptop className="w-4 h-4 shrink-0" />,
    },
    {
        id: 'personal',
        sync_policy: 'sync',
        label: 'Personal',
        description: 'Syncs across your devices; private to you. Best for personal projects and notes.',
        guestAllowed: false,
        icon: <User className="w-4 h-4 shrink-0" />,
    },
    {
        id: 'workspace',
        sync_policy: 'shared',
        label: 'Workspace',
        description: 'Syncs and can be shared with others. Invite teammates by email or username to collaborate.',
        guestAllowed: false,
        icon: <Users className="w-4 h-4 shrink-0" />,
    },
    {
        id: 'custom',
        sync_policy: 'sync',
        label: 'Custom',
        description: 'Choose sync behavior yourself: device-only, sync, or shared.',
        guestAllowed: false,
        icon: <Settings2 className="w-4 h-4 shrink-0" />,
    },
];

/** Phase 4: Spaces panel — Perplexity-style project hubs. Shared Space: templates + guest gray-out. */
export const SpacesPanel: React.FC = () => {
    const {
        spaces,
        currentSpaceId,
        fetchSpaces,
        createSpace,
        setCurrentSpaceId,
        authStatus,
        setIsAuthModalOpen,
    } = useAppStore();
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [createStep, setCreateStep] = useState<'template' | 'details'>('template');
    const [selectedTemplate, setSelectedTemplate] = useState<typeof SPACE_TEMPLATES[0] | null>(null);
    const [customSyncPolicy, setCustomSyncPolicy] = useState<SpaceSyncPolicy>('sync');
    const [newName, setNewName] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const isGuest = authStatus === 'guest';

    useEffect(() => {
        fetchSpaces();
    }, [fetchSpaces]);

    const openCreate = () => {
        setCreateStep('template');
        setSelectedTemplate(null);
        setNewName('');
        setNewDescription('');
        setCustomSyncPolicy('sync');
        setError(null);
        setIsCreateOpen(true);
    };

    const onSelectTemplate = (t: typeof SPACE_TEMPLATES[0]) => {
        if (!t.guestAllowed && isGuest) {
            setIsAuthModalOpen(true);
            return;
        }
        setSelectedTemplate(t);
        setCreateStep('details');
        if (t.id === 'custom') setCustomSyncPolicy('sync');
    };

    const handleCreate = async () => {
        if (!newName.trim() || !selectedTemplate) return;
        const sync_policy: SpaceSyncPolicy =
            selectedTemplate.id === 'custom' ? customSyncPolicy : selectedTemplate.sync_policy;
        setIsCreating(true);
        setError(null);
        try {
            const space = await createSpace(newName.trim(), newDescription.trim() || undefined, sync_policy);
            setIsCreateOpen(false);
            setCurrentSpaceId(space.space_id);
        } catch (e: any) {
            setError(e?.message || 'Failed to create space');
        } finally {
            setIsCreating(false);
        }
    };

    const backToTemplates = () => {
        setCreateStep('template');
        setSelectedTemplate(null);
        setError(null);
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
                    onClick={openCreate}
                    title="Create Space"
                >
                    <Plus className="w-4 h-4" />
                </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
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
                        {(s.description || s.is_shared) && (
                            <span className="text-xs text-muted-foreground truncate">
                                {[s.description, s.is_shared ? '(Shared)' : null].filter(Boolean).join(' • ')}
                            </span>
                        )}
                    </button>
                ))}
                {spaces.length === 0 && (
                    <div className="py-8 text-center text-muted-foreground text-sm">
                        <FolderOpen className="w-10 h-10 mx-auto mb-2 opacity-50" />
                        <p>No spaces yet.</p>
                        <p className="text-xs mt-1">Create one to organize runs and memories by project.</p>
                        <Button variant="outline" size="sm" className="mt-3" onClick={openCreate}>
                            <Plus className="w-3 h-3 mr-1" />
                            Create Space
                        </Button>
                    </div>
                )}
            </div>

            <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                    <DialogHeader>
                        <DialogTitle className="text-foreground">
                            {createStep === 'template' ? 'Choose space type' : 'Name your space'}
                        </DialogTitle>
                    </DialogHeader>

                    {createStep === 'template' && (
                        <div className="space-y-2 py-2">
                            <p className="text-xs text-muted-foreground mb-3">
                                Select a template. You can set a name and description on the next step.
                            </p>
                            {SPACE_TEMPLATES.map((t) => {
                                const disabled = !t.guestAllowed && isGuest;
                                return (
                                    <button
                                        key={t.id}
                                        type="button"
                                        onClick={() => onSelectTemplate(t)}
                                        disabled={disabled}
                                        className={cn(
                                            'w-full flex gap-3 p-3 rounded-lg border text-left transition-colors',
                                            disabled
                                                ? 'opacity-60 cursor-not-allowed border-border/50 bg-muted/30'
                                                : 'hover:bg-muted/50 border-border hover:border-primary/30'
                                        )}
                                    >
                                        <span className="text-muted-foreground mt-0.5">{t.icon}</span>
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium text-sm text-foreground">{t.label}</div>
                                            <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>
                                            {disabled && (
                                                <p className="text-xs text-primary/90 mt-1">Log in to use this type.</p>
                                            )}
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {createStep === 'details' && selectedTemplate && (
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
                                    className="bg-muted border-input dark:border-muted-foreground/50 text-foreground placeholder:text-muted-foreground"
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
                                    className="bg-muted border-input dark:border-muted-foreground/50 text-foreground placeholder:text-muted-foreground min-h-[60px] resize-none"
                                    rows={2}
                                />
                            </div>
                            {selectedTemplate.id === 'custom' && (
                                <div className="space-y-2">
                                    <Label className="text-sm text-muted-foreground dark:text-foreground/80">
                                        Sync behavior
                                    </Label>
                                    <select
                                        value={customSyncPolicy}
                                        onChange={(e) => setCustomSyncPolicy(e.target.value as SpaceSyncPolicy)}
                                        className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm text-foreground"
                                    >
                                        <option value="local_only">Computer only (no sync)</option>
                                        <option value="sync">Personal (sync across my devices)</option>
                                        <option value="shared">Workspace (sync + share with others)</option>
                                    </select>
                                </div>
                            )}
                            {error && <p className="text-sm text-red-500">{error}</p>}
                            <DialogFooter>
                                <Button variant="outline" onClick={backToTemplates}>
                                    Back
                                </Button>
                                <Button
                                    onClick={handleCreate}
                                    disabled={!newName.trim() || isCreating}
                                >
                                    {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
                                </Button>
                            </DialogFooter>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
};
