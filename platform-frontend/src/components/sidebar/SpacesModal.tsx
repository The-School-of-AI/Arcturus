import React, { useEffect, useState } from 'react';
import { useAppStore } from '@/store';
import { FolderOpen, Plus, Loader2, Laptop, User, Users, Settings2, LayoutGrid, ChevronRight } from 'lucide-react';
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

const SPACE_TEMPLATES: Array<{
    id: string;
    sync_policy: SpaceSyncPolicy;
    label: string;
    description: string;
    guestAllowed: boolean;
    icon: React.ReactNode;
}> = [
    { id: 'computer_only', sync_policy: 'local_only', label: 'Computer Only', description: 'Stays on this device only; not synced to the cloud.', guestAllowed: true, icon: <Laptop className="w-4 h-4 shrink-0" /> },
    { id: 'personal', sync_policy: 'sync', label: 'Personal', description: 'Syncs across your devices; private to you.', guestAllowed: false, icon: <User className="w-4 h-4 shrink-0" /> },
    { id: 'workspace', sync_policy: 'shared', label: 'Workspace', description: 'Syncs and can be shared with others.', guestAllowed: false, icon: <Users className="w-4 h-4 shrink-0" /> },
    { id: 'custom', sync_policy: 'sync', label: 'Custom', description: 'Choose sync behavior yourself.', guestAllowed: false, icon: <Settings2 className="w-4 h-4 shrink-0" /> },
    { id: 'more_templates', sync_policy: 'sync', label: 'More Templates...', description: 'Startup Research, Home Renovation, and more.', guestAllowed: false, icon: <LayoutGrid className="w-4 h-4 shrink-0" /> },
];

const MORE_TEMPLATES: Array<{ id: string; sync_policy: SpaceSyncPolicy; label: string; description: string }> = [
    { id: 'startup_research', sync_policy: 'shared', label: 'Startup Research', description: 'Track competitors, market insights, and pitch ideas. Share with co-founders or advisors.' },
    { id: 'home_renovation', sync_policy: 'sync', label: 'Home Renovation', description: 'Plans, contractor notes, budget, and project timeline. Keep everything in one place.' },
    { id: 'book_writing', sync_policy: 'sync', label: 'Book Writing', description: 'Chapters, research notes, character outlines, and revision history.' },
    { id: 'travel_planning', sync_policy: 'sync', label: 'Travel Planning', description: 'Destinations, itineraries, bookings, and packing lists for your next trip.' },
    { id: 'learning', sync_policy: 'sync', label: 'Learning', description: 'Courses, notes, and progress tracking. One space per skill or course.' },
    { id: 'job_search', sync_policy: 'sync', label: 'Job Search', description: 'Applications, company research, and interview prep. Private to you.' },
];

/** Phase 4: Spaces management modal — select or create space; Shared Space: template-based create. */
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
        authStatus,
        setIsAuthModalOpen,
    } = useAppStore();
    const [selectedId, setSelectedId] = useState<string | null>(currentSpaceId);
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [createStep, setCreateStep] = useState<'template' | 'more_templates' | 'details'>('template');
    const [selectedTemplate, setSelectedTemplate] = useState<typeof SPACE_TEMPLATES[0] | typeof MORE_TEMPLATES[0] | null>(null);
    const [customSyncPolicy, setCustomSyncPolicy] = useState<SpaceSyncPolicy>('sync');
    const [newName, setNewName] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const isGuest = authStatus === 'guest';

    useEffect(() => {
        if (isOpen) {
            fetchSpaces();
            setSelectedId(currentSpaceId);
        }
    }, [isOpen, fetchSpaces, currentSpaceId]);

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
        const sync_policy: SpaceSyncPolicy = selectedTemplate.id === 'custom' ? customSyncPolicy : (selectedTemplate.sync_policy as SpaceSyncPolicy);
        setIsCreating(true);
        setError(null);
        try {
            const space = await createSpace(newName.trim(), newDescription.trim() || undefined, sync_policy);
            setIsCreateOpen(false);
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
                        Select a space to filter runs, memories, RAG, and notes. Available from all panels.
                    </p>
                    <div className="space-y-2 max-h-[320px] overflow-y-auto py-2">
                        <button
                            onClick={() => setSelectedId(null)}
                            className={cn(
                                'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors',
                                selectedId === null ? 'bg-primary/10 text-primary border border-primary/30' : 'hover:bg-muted/50 text-foreground border border-transparent'
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
                                    selectedId === s.space_id ? 'bg-primary/10 text-primary border border-primary/30' : 'hover:bg-muted/50 text-foreground border border-transparent'
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
                    </div>
                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
                        <Button variant="outline" size="sm" className="border-border text-foreground" onClick={openCreate}>
                            <Plus className="w-3.5 h-3.5 mr-1" />
                            New Space
                        </Button>
                        <DialogFooter className="gap-2 p-0 m-0 border-0">
                            <Button variant="outline" onClick={onClose} className="border-border text-foreground">Cancel</Button>
                            <Button onClick={handleOk} className="bg-neon-yellow text-white hover:bg-neon-yellow/90">Ok</Button>
                        </DialogFooter>
                    </div>
                </DialogContent>
            </Dialog>

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
                                            disabled ? 'opacity-60 cursor-not-allowed border-border/50 bg-muted/30' : 'hover:bg-muted/50 border-border'
                                        )}
                                    >
                                        <span className="text-muted-foreground mt-0.5">{t.icon}</span>
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium text-sm text-foreground">{t.label}</div>
                                            <p className="text-xs text-muted-foreground mt-0.5">{t.description}</p>
                                            {disabled && <p className="text-xs text-primary/90 mt-1">Log in to use this type.</p>}
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
                            <Button variant="outline" size="sm" className="w-full mt-2" onClick={() => setCreateStep('template')}>
                                Back
                            </Button>
                        </div>
                    )}
                    {createStep === 'details' && selectedTemplate && (
                        <div className="space-y-4 py-2">
                            <div className="space-y-2">
                                <Label htmlFor="modal-space-name" className="text-sm text-muted-foreground dark:text-foreground/80">Name</Label>
                                <Input
                                    id="modal-space-name"
                                    placeholder="e.g. Biology 101"
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    className="bg-muted border-input text-foreground"
                                    onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="modal-space-desc" className="text-sm text-muted-foreground dark:text-foreground/80">Description (optional)</Label>
                                <Textarea
                                    id="modal-space-desc"
                                    placeholder="Brief description"
                                    value={newDescription}
                                    onChange={(e) => setNewDescription(e.target.value)}
                                    className="bg-muted border-input text-foreground min-h-[60px] resize-none"
                                    rows={2}
                                />
                            </div>
                            {selectedTemplate.id === 'custom' && (
                                <div className="space-y-2">
                                    <Label className="text-sm text-muted-foreground">Sync behavior</Label>
                                    <select
                                        value={customSyncPolicy}
                                        onChange={(e) => setCustomSyncPolicy(e.target.value as SpaceSyncPolicy)}
                                        className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm text-foreground"
                                    >
                                        <option value="local_only">Computer only</option>
                                        <option value="sync">Personal (sync)</option>
                                        <option value="shared">Workspace (shared)</option>
                                    </select>
                                </div>
                            )}
                            {error && <p className="text-sm text-red-500">{error}</p>}
                            <DialogFooter>
                                <Button variant="outline" onClick={() => { setCreateStep('template'); setSelectedTemplate(null); setError(null); }}>Back</Button>
                                <Button onClick={handleCreate} disabled={!newName.trim() || isCreating}>
                                    {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
                                </Button>
                            </DialogFooter>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
};
