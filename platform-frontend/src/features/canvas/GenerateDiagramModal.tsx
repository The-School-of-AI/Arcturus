import React, { useState, useCallback } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { API_BASE } from '@/lib/api';

export type DiagramType = 'table' | 'mermaid' | 'architecture';

const DEFAULT_MERMAID_CODE = `flowchart LR
A[Developer Commit] --> B[GitHub Repo]
B --> C{Trigger CI}
C --> D[Run Lint]
C --> E[Run Unit Tests]
C --> F[Security Scan]
D --> G[Build Docker Image]
E --> G
F --> G
G --> H[Push to Container Registry]
H --> I{Deploy Target}
I --> J[Dev Environment]
I --> K[Staging]
I --> L[Production]
J --> M[Integration Tests]
K --> N[UAT Tests]
L --> O[Blue/Green Deployment]
O --> P[Monitoring & Alerts]`;

const ARCH_VARIANTS = [
    { value: '', label: 'Default' },
    { value: 'hero', label: 'Hero' },
    { value: 'accent', label: 'Accent' },
    { value: 'green', label: 'Green' },
    { value: 'orange', label: 'Orange' },
    { value: 'sage', label: 'Sage' },
    { value: 'teal', label: 'Teal' },
    { value: 'plum', label: 'Plum' },
    { value: 'recessed', label: 'Recessed' },
] as const;

export interface ArchitectureSection {
    title: string;
    description: string;
    items: string;
    variant: string;
    label: string;
}

const defaultArchSection = (): ArchitectureSection => ({
    title: 'Backend',
    description: 'API and services',
    items: 'REST API\nWebSocket\nDB',
    variant: '',
    label: '',
});

interface GenerateDiagramModalProps {
    open: boolean;
    onClose: () => void;
    onSuccess: (html: string, title: string) => void | Promise<void>;
}

function parseTableInput(headersStr: string, rowsStr: string): { headers: string[]; rows: string[][] } {
    const headers = headersStr
        .split(',')
        .map((h) => h.trim())
        .filter(Boolean);
    let rows: string[][] = [];
    try {
        const raw = rowsStr?.trim() || '[]';
        const parsed = JSON.parse(raw);
        rows = Array.isArray(parsed) ? parsed.map((r: unknown) => (Array.isArray(r) ? r.map(String) : [String(r)])) : [];
    } catch {
        rows = [];
    }
    return { headers, rows };
}

export function GenerateDiagramModal({ open, onClose, onSuccess }: GenerateDiagramModalProps) {
    const [type, setType] = useState<DiagramType>('table');
    const [title, setTitle] = useState('');
    const [tableHeaders, setTableHeaders] = useState('A, B');
    const [tableRows, setTableRows] = useState('[["1", "2"], ["3", "4"]]');
    const [mermaidCode, setMermaidCode] = useState(DEFAULT_MERMAID_CODE);
    const [archSubtitle, setArchSubtitle] = useState('');
    const [archSections, setArchSections] = useState<ArchitectureSection[]>([defaultArchSection()]);
    const [archFlowLabels, setArchFlowLabels] = useState<string[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    const addArchSection = useCallback(() => {
        setArchSections((prev) => [...prev, defaultArchSection()]);
        setArchFlowLabels((prev) => [...prev, '']);
    }, []);
    const removeArchSection = useCallback((index: number) => {
        setArchSections((prev) => prev.filter((_, i) => i !== index));
        setArchFlowLabels((prev) => {
            const next = prev.slice();
            if (index < next.length) next.splice(index, 1);
            return next;
        });
    }, []);
    const updateArchSection = useCallback((index: number, patch: Partial<ArchitectureSection>) => {
        setArchSections((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
    }, []);

    const resetForm = useCallback(() => {
        setTitle('');
        setTableHeaders('A, B');
        setTableRows('[["1", "2"], ["3", "4"]]');
        setMermaidCode(DEFAULT_MERMAID_CODE);
        setArchSubtitle('');
        setArchSections([defaultArchSection()]);
        setArchFlowLabels([]);
        setError('');
    }, []);

    const handleClose = useCallback(() => {
        resetForm();
        onClose();
    }, [onClose, resetForm]);

    const buildContent = (): Record<string, unknown> | string => {
        if (type === 'table') {
            const { headers, rows } = parseTableInput(tableHeaders, tableRows);
            return { headers, rows };
        }
        if (type === 'mermaid') {
            return mermaidCode.trim();
        }
        if (type === 'architecture') {
            const sections = archSections.map((s) => ({
                title: s.title || 'Section',
                description: s.description || '',
                items: s.items.split('\n').map((i) => i.trim()).filter(Boolean),
                ...(s.variant ? { variant: s.variant } : {}),
                ...(s.label ? { label: s.label } : {}),
            }));
            const flowLabels = archFlowLabels.slice(0, Math.max(0, archSections.length - 1)).filter((l) => l.trim());
            const payload: Record<string, unknown> = { sections };
            if (archSubtitle.trim()) payload.subtitle = archSubtitle.trim();
            if (flowLabels.length) payload.flowLabels = flowLabels;
            return payload;
        }
        return {};
    };

    const handleSubmit = async () => {
        setError('');
        const content = buildContent();
        if (type === 'table') {
            const c = content as { headers: string[]; rows: string[][] };
            if (!c.headers?.length) {
                setError('Enter at least one header (comma-separated).');
                return;
            }
        }
        if (type === 'mermaid' && !(content as string).trim()) {
            setError('Enter Mermaid diagram code.');
            return;
        }

        setIsSubmitting(true);
        try {
            const res = await fetch(`${API_BASE}/visual-explainer/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type,
                    title: title || 'Diagram',
                    content,
                }),
            });
            if (!res.ok) {
                const errBody = await res.text();
                throw new Error(errBody || `Request failed: ${res.status}`);
            }
            const data = await res.json();
            const html = data?.html;
            if (typeof html !== 'string') {
                throw new Error('Invalid response: missing html');
            }
            await Promise.resolve(onSuccess(html, title || 'Diagram'));
            handleClose();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to generate diagram. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={(open) => !open && handleClose()}>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Generate diagram</DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-2">
                    <div className="space-y-1">
                        <label className="text-sm font-medium">Type</label>
                        <select
                            value={type}
                            onChange={(e) => setType(e.target.value as DiagramType)}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                            <option value="table">Table</option>
                            <option value="mermaid">Mermaid</option>
                            <option value="architecture">Architecture</option>
                        </select>
                    </div>

                    <div className="space-y-1">
                        <label className="text-sm font-medium">Title</label>
                        <Input
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="Diagram title"
                            className="bg-muted"
                        />
                    </div>

                    {type === 'architecture' && (
                        <div className="space-y-1">
                            <label className="text-sm font-medium">Subtitle (optional)</label>
                            <Input
                                value={archSubtitle}
                                onChange={(e) => setArchSubtitle(e.target.value)}
                                placeholder="e.g. High-level overview"
                                className="bg-muted"
                            />
                        </div>
                    )}

                    {type === 'table' && (
                        <>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Headers (comma-separated)</label>
                                <Input
                                    value={tableHeaders}
                                    onChange={(e) => setTableHeaders(e.target.value)}
                                    placeholder="A, B, C"
                                    className="bg-muted font-mono text-sm"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Rows (JSON array of arrays)</label>
                                <textarea
                                    value={tableRows}
                                    onChange={(e) => setTableRows(e.target.value)}
                                    placeholder='[["1", "2"], ["3", "4"]]'
                                    rows={3}
                                    className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm font-mono resize-none"
                                />
                            </div>
                        </>
                    )}

                    {type === 'mermaid' && (
                        <div className="space-y-1">
                            <label className="text-sm font-medium">Mermaid code</label>
                            <textarea
                                value={mermaidCode}
                                onChange={(e) => setMermaidCode(e.target.value)}
                                placeholder="graph LR&#10;  A --> B"
                                rows={6}
                                className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm font-mono resize-none"
                            />
                        </div>
                    )}

                    {type === 'architecture' && (
                        <div className="space-y-4">
                            {archSections.map((section, index) => (
                                <div key={index} className="rounded-lg border border-border p-3 space-y-2 bg-muted/30">
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs font-medium text-muted-foreground">Section {index + 1}</span>
                                        <div className="flex gap-1">
                                            {archSections.length > 1 && (
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-7 w-7"
                                                    onClick={() => removeArchSection(index)}
                                                    title="Remove section"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="space-y-1">
                                            <label className="text-xs font-medium">Title</label>
                                            <Input
                                                value={section.title}
                                                onChange={(e) => updateArchSection(index, { title: e.target.value })}
                                                placeholder="e.g. Backend"
                                                className="bg-muted h-8 text-sm"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs font-medium">Variant</label>
                                            <select
                                                value={section.variant}
                                                onChange={(e) => updateArchSection(index, { variant: e.target.value })}
                                                className="w-full rounded-md border border-input bg-muted h-8 text-sm px-2"
                                            >
                                                {ARCH_VARIANTS.map((v) => (
                                                    <option key={v.value || 'default'} value={v.value}>{v.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium">Label (optional, monospace above title)</label>
                                        <Input
                                            value={section.label}
                                            onChange={(e) => updateArchSection(index, { label: e.target.value })}
                                            placeholder="Section label"
                                            className="bg-muted h-8 text-sm"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium">Description</label>
                                        <Input
                                            value={section.description}
                                            onChange={(e) => updateArchSection(index, { description: e.target.value })}
                                            placeholder="Short description"
                                            className="bg-muted h-8 text-sm"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium">Items (one per line)</label>
                                        <textarea
                                            value={section.items}
                                            onChange={(e) => updateArchSection(index, { items: e.target.value })}
                                            placeholder="REST API&#10;WebSocket"
                                            rows={3}
                                            className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm resize-none"
                                        />
                                    </div>
                                    {index < archSections.length - 1 && (
                                        <div className="space-y-1 pt-1">
                                            <label className="text-xs font-medium">Flow label after this section</label>
                                            <Input
                                                value={archFlowLabels[index] ?? ''}
                                                onChange={(e) => {
                                                    const next = [...archFlowLabels];
                                                    while (next.length <= index) next.push('');
                                                    next[index] = e.target.value;
                                                    setArchFlowLabels(next);
                                                }}
                                                placeholder="e.g. pipeline entry"
                                                className="bg-muted h-8 text-sm"
                                            />
                                        </div>
                                    )}
                                </div>
                            ))}
                            <Button type="button" variant="outline" size="sm" onClick={addArchSection} className="w-full">
                                <Plus className="w-4 h-4 mr-2" />
                                Add section
                            </Button>
                        </div>
                    )}

                    {error && (
                        <div className="rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm p-3">
                            {error}
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={handleClose} disabled={isSubmitting}>
                        Cancel
                    </Button>
                    <Button onClick={handleSubmit} disabled={isSubmitting}>
                        {isSubmitting ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Generating…
                            </>
                        ) : (
                            'Generate'
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
