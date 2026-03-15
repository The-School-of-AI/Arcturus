import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { FolderOpen, Plus, Loader2, Laptop, User, Users, Settings2, LayoutGrid, ChevronRight, Share2 } from 'lucide-react';
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
    {
        id: 'more_templates',
        sync_policy: 'sync',
        label: 'More Templates...',
        description: 'Startup Research, Home Renovation, and more.',
        guestAllowed: false,
        icon: <LayoutGrid className="w-4 h-4 shrink-0" />,
    },
];

/** Sample templates shown when user clicks "More Templates...". Pre-fill name and description. */
const MORE_TEMPLATES: Array<{ id: string; sync_policy: SpaceSyncPolicy; label: string; description: string }> = [
    { id: 'startup_research', sync_policy: 'shared', label: 'Startup Research', description: 'Track competitors, market insights, and pitch ideas. Share with co-founders or advisors.' },
    { id: 'home_renovation', sync_policy: 'sync', label: 'Home Renovation', description: 'Plans, contractor notes, budget, and project timeline. Keep everything in one place.' },
    { id: 'book_writing', sync_policy: 'sync', label: 'Book Writing', description: 'Chapters, research notes, character outlines, and revision history.' },
    { id: 'travel_planning', sync_policy: 'sync', label: 'Travel Planning', description: 'Destinations, itineraries, bookings, and packing lists for your next trip.' },
    { id: 'learning', sync_policy: 'sync', label: 'Learning', description: 'Courses, notes, and progress tracking. One space per skill or course.' },
    { id: 'job_search', sync_policy: 'sync', label: 'Job Search', description: 'Applications, company research, and interview prep. Private to you.' },
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
    const [createStep, setCreateStep] = useState<'template' | 'more_templates' | 'details'>('template');
    const [selectedTemplate, setSelectedTemplate] = useState<typeof SPACE_TEMPLATES[0] | (typeof MORE_TEMPLATES[0] & { guestAllowed?: boolean; icon?: React.ReactNode }) | null>(null);
    const [customSyncPolicy, setCustomSyncPolicy] = useState<SpaceSyncPolicy>('sync');
    const [newName, setNewName] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isShareOpen, setIsShareOpen] = useState(false);
    const [shareSpaceId, setShareSpaceId] = useState<string | null>(null);
    const [shareSpaceName, setShareSpaceName] = useState('');
    const [shareUserIds, setShareUserIds] = useState('');
    const [isSharing, setIsSharing] = useState(false);
    const [shareError, setShareError] = useState<string | null>(null);

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
        if (t.id === 'more_templates') {
            if (isGuest) {
                setIsAuthModalOpen(true);
                return;
            }
            setCreateStep('more_templates');
            return;
        }
        if (!t.guestAllowed && isGuest) {
            setIsAuthModalOpen(true);
            return;
        }
        setSelectedTemplate(t);
        setCreateStep('details');
        if (t.id === 'custom') setCustomSyncPolicy('sync');
    };

    const onSelectMoreTemplate = (t: typeof MORE_TEMPLATES[0]) => {
        setSelectedTemplate(t);
        setNewName(t.label);
        setNewDescription(t.description);
        setCreateStep('details');
    };

    const handleCreate = async () => {
        if (!newName.trim() || !selectedTemplate) return;
        const sync_policy: SpaceSyncPolicy =
            selectedTemplate.id === 'custom' ? customSyncPolicy : (selectedTemplate.sync_policy as SpaceSyncPolicy);
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

    const backFromMoreTemplates = () => {
        setCreateStep('template');
    };

    const openShareModal = (e: React.MouseEvent, space: { space_id: string; name: string }) => {
        e.stopPropagation();
        if (isGuest) {
            setIsAuthModalOpen(true);
            return;
        }
        setShareSpaceId(space.space_id);
        setShareSpaceName(space.name || 'Unnamed Space');
        setShareUserIds('');
        setShareError(null);
        setIsShareOpen(true);
    };

    const handleShare = async () => {
        if (!shareSpaceId) return;
        const ids = shareUserIds
            .split(/[\n,]+/)
            .map((s) => s.trim())
            .filter(Boolean);
        if (ids.length === 0) {
            setShareError('Enter at least one user ID (comma or newline separated).');
            return;
        }
        setIsSharing(true);
        setShareError(null);
        try {
            const res = await api.shareSpace(shareSpaceId, ids);
            setIsShareOpen(false);
            fetchSpaces();
        } catch (e: any) {
            setShareError(e?.response?.data?.detail || e?.message || 'Failed to share');
        } finally {
            setIsSharing(false);
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
                    <div
                        key={s.space_id}
                        className={cn(
                            'w-full flex items-center gap-1 px-3 py-2 rounded-lg transition-colors group',
                            currentSpaceId === s.space_id
                                ? 'bg-primary/10 text-primary border border-primary/30'
                                : 'hover:bg-muted/50 text-foreground'
                        )}
                    >
                        <button
                            onClick={() => setCurrentSpaceId(s.space_id)}
                            className="flex-1 flex flex-col gap-0.5 text-left min-w-0"
                        >
                            <span className="font-medium truncate text-sm">{s.name || 'Unnamed Space'}</span>
                            {(s.description || s.is_shared) && (
                                <span className="text-xs text-muted-foreground truncate">
                                    {[s.description, s.is_shared ? '(Shared)' : null].filter(Boolean).join(' • ')}
                                </span>
                            )}
                        </button>
                        {!isGuest && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 shrink-0 opacity-60 hover:opacity-100"
                                onClick={(e) => openShareModal(e, s)}
                                title="Share space"
                            >
                                <Share2 className="w-3.5 h-3.5" />
                            </Button>
                        )}
                    </div>
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
                            {createStep === 'template' && 'Choose space type'}
                            {createStep === 'more_templates' && 'More templates'}
                            {createStep === 'details' && 'Name your space'}
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

                    {createStep === 'more_templates' && (
                        <div className="space-y-2 py-2">
                            <p className="text-xs text-muted-foreground mb-3">
                                Pick a template to pre-fill name and description. You can edit them on the next step.
                            </p>
                            {MORE_TEMPLATES.map((t) => (
                                <button
                                    key={t.id}
                                    type="button"
                                    onClick={() => onSelectMoreTemplate(t)}
                                    className="w-full flex gap-3 p-3 rounded-lg border border-border text-left hover:bg-muted/50 hover:border-primary/30 transition-colors"
                                >
                                    <ChevronRight className="w-4 h-4 shrink-0 text-muted-foreground mt-0.5" />
                                    <div className="flex-1 min-w-0">
                                        <div className="font-medium text-sm text-foreground">{t.label}</div>
                                        <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>
                                    </div>
                                </button>
                            ))}
                            <Button variant="outline" size="sm" className="w-full mt-2" onClick={backFromMoreTemplates}>
                                Back
                            </Button>
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

            <Dialog open={isShareOpen} onOpenChange={setIsShareOpen}>
                <DialogContent className="bg-card border-border sm:max-w-md text-foreground">
                    <DialogHeader>
                        <DialogTitle className="text-foreground">Share space</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <p className="text-sm text-muted-foreground">
                            Share <strong>{shareSpaceName}</strong> with other users by their user ID.
                        </p>
                        <div className="space-y-2">
                            <Label htmlFor="share-user-ids" className="text-sm text-muted-foreground">
                                User IDs (comma or newline separated)
                            </Label>
                            <Textarea
                                id="share-user-ids"
                                placeholder="user-id-1, user-id-2"
                                value={shareUserIds}
                                onChange={(e) => setShareUserIds(e.target.value)}
                                className="bg-muted border-input dark:border-muted-foreground/50 text-foreground min-h-[100px] resize-y"
                                rows={4}
                            />
                        </div>
                        {shareError && <p className="text-sm text-destructive">{shareError}</p>}
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsShareOpen(false)}>
                                Cancel
                            </Button>
                            <Button onClick={handleShare} disabled={isSharing}>
                                {isSharing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Share'}
                            </Button>
                        </DialogFooter>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};
