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
import { Loader2 } from 'lucide-react';
import { API_BASE } from '@/lib/api';

export type DiagramType = 'table' | 'mermaid' | 'architecture';

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

function parseArchitectureSections(sectionTitle: string, sectionDesc: string, sectionItemsStr: string) {
    const items = sectionItemsStr
        .split('\n')
        .map((i) => i.trim())
        .filter(Boolean);
    return [{ title: sectionTitle || 'Section', description: sectionDesc || '', items }];
}

export function GenerateDiagramModal({ open, onClose, onSuccess }: GenerateDiagramModalProps) {
    const [type, setType] = useState<DiagramType>('table');
    const [title, setTitle] = useState('');
    const [tableHeaders, setTableHeaders] = useState('A, B');
    const [tableRows, setTableRows] = useState('[["1", "2"], ["3", "4"]]');
    const [mermaidCode, setMermaidCode] = useState('graph LR\n  A --> B --> C');
    const [archSectionTitle, setArchSectionTitle] = useState('Backend');
    const [archSectionDesc, setArchSectionDesc] = useState('API and services');
    const [archSectionItems, setArchSectionItems] = useState('REST API\nWebSocket\nDB');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    const resetForm = useCallback(() => {
        setTitle('');
        setTableHeaders('A, B');
        setTableRows('[["1", "2"], ["3", "4"]]');
        setMermaidCode('graph LR\n  A --> B --> C');
        setArchSectionTitle('Backend');
        setArchSectionDesc('API and services');
        setArchSectionItems('REST API\nWebSocket\nDB');
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
            const sections = parseArchitectureSections(archSectionTitle, archSectionDesc, archSectionItems);
            return { sections };
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
                        <>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Section title</label>
                                <Input
                                    value={archSectionTitle}
                                    onChange={(e) => setArchSectionTitle(e.target.value)}
                                    placeholder="e.g. Backend"
                                    className="bg-muted"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Section description</label>
                                <Input
                                    value={archSectionDesc}
                                    onChange={(e) => setArchSectionDesc(e.target.value)}
                                    placeholder="Short description"
                                    className="bg-muted"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Items (one per line)</label>
                                <textarea
                                    value={archSectionItems}
                                    onChange={(e) => setArchSectionItems(e.target.value)}
                                    placeholder="REST API&#10;WebSocket"
                                    rows={4}
                                    className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm resize-none"
                                />
                            </div>
                        </>
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
