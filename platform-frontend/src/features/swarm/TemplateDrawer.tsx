// features/swarm/TemplateDrawer.tsx
// Drawer UI for saving and loading swarm configurations as reusable templates.

import React, { useEffect, useState } from 'react';
import { BookMarked, Trash2, Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useSwarmStore } from './useSwarmStore';
import { swarmApi } from './swarmApi';
import type { SwarmTemplate } from './types';

interface TemplateDrawerProps {
    onApply: (template: SwarmTemplate) => void;
}

export const TemplateDrawer: React.FC<TemplateDrawerProps> = ({ onApply }) => {
    const isOpen = useSwarmStore(s => s.isTemplateDrawerOpen);
    const setOpen = useSwarmStore(s => s.setTemplateDrawerOpen);
    const templates = useSwarmStore(s => s.templates);
    const loadTemplates = useSwarmStore(s => s.loadTemplates);
    const tasks = useSwarmStore(s => s.tasks);

    const [saveName, setSaveName] = useState('');
    const [saveDesc, setSaveDesc] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (isOpen) loadTemplates();
    }, [isOpen, loadTemplates]);

    const handleSave = async () => {
        if (!saveName.trim()) return;
        setSaving(true);
        try {
            await swarmApi.saveTemplate({
                name: saveName.trim(),
                description: saveDesc.trim(),
                tasks_template: tasks.map(t => ({
                    title: t.title,
                    description: '',
                    assigned_to: t.assigned_to,
                    priority: t.priority,
                })),
            });
            await loadTemplates();
            setSaveName('');
            setSaveDesc('');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (name: string) => {
        await swarmApi.deleteTemplate(name);
        await loadTemplates();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-y-0 right-0 w-80 bg-card border-l border-border shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-200">
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <BookMarked className="w-4 h-4 text-primary" />
                    <span className="text-sm font-semibold">Swarm Templates</span>
                </div>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setOpen(false)}>
                    <X className="w-3.5 h-3.5" />
                </Button>
            </div>

            {/* Save current run as template */}
            <div className="p-4 border-b border-border space-y-2 shrink-0">
                <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Save Current Run</p>
                <div className="space-y-1.5">
                    <Label className="text-xs">Name</Label>
                    <Input
                        placeholder="e.g. Research Pipeline"
                        value={saveName}
                        onChange={e => setSaveName(e.target.value)}
                        className="text-xs bg-muted border-input h-8"
                    />
                </div>
                <div className="space-y-1.5">
                    <Label className="text-xs">Description (optional)</Label>
                    <Textarea
                        placeholder="What does this template do?"
                        value={saveDesc}
                        onChange={e => setSaveDesc(e.target.value)}
                        className="text-xs bg-muted border-input resize-none h-16"
                    />
                </div>
                <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={saving || !saveName.trim() || tasks.length === 0}
                    className="w-full h-8 text-xs bg-primary hover:bg-primary/90 text-white gap-1"
                >
                    <Plus className="w-3 h-3" />
                    {saving ? 'Saving…' : 'Save Template'}
                </Button>
                {tasks.length === 0 && (
                    <p className="text-[10px] text-muted-foreground text-center">Start a run first to save its task structure.</p>
                )}
            </div>

            {/* Saved templates list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-hide">
                <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Saved Templates</p>
                {templates.length === 0 ? (
                    <p className="text-xs text-muted-foreground opacity-50 text-center pt-4">No templates yet.</p>
                ) : (
                    templates.map(tmpl => (
                        <div
                            key={tmpl.name}
                            className="p-3 rounded-xl border border-border hover:border-primary/40 transition-all bg-muted/30 space-y-2 group"
                        >
                            <div className="flex items-start justify-between gap-2">
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-foreground truncate">{tmpl.name}</p>
                                    {tmpl.description && (
                                        <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{tmpl.description}</p>
                                    )}
                                    <p className="text-[10px] text-muted-foreground/60 mt-1">
                                        {tmpl.tasks_template.length} task{tmpl.tasks_template.length !== 1 ? 's' : ''}
                                    </p>
                                </div>
                                <button
                                    onClick={() => handleDelete(tmpl.name)}
                                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/10 text-muted-foreground hover:text-red-400 transition-all"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                            <Button
                                size="sm"
                                variant="outline"
                                className="w-full h-7 text-xs border-border hover:border-primary/40 hover:text-primary"
                                onClick={() => { onApply(tmpl); setOpen(false); }}
                            >
                                Apply Template
                            </Button>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
