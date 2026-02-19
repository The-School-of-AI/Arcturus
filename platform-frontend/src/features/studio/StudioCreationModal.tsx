import { useState } from 'react';
import { Loader2, Presentation, FileText, Table2 } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useAppStore } from '@/store';

const TYPES = [
    { key: 'slides' as const, label: 'Slides', icon: Presentation, desc: 'Presentation deck' },
    { key: 'documents' as const, label: 'Document', icon: FileText, desc: 'Written document' },
    { key: 'sheets' as const, label: 'Sheet', icon: Table2, desc: 'Spreadsheet workbook' },
];

export function StudioCreationModal() {
    const isOpen = useAppStore(s => s.isStudioModalOpen);
    const setOpen = useAppStore(s => s.setIsStudioModalOpen);
    const createArtifact = useAppStore(s => s.createArtifact);
    const isGenerating = useAppStore(s => s.isGenerating);

    const [type, setType] = useState<'slides' | 'documents' | 'sheets'>('slides');
    const [title, setTitle] = useState('');
    const [prompt, setPrompt] = useState('');
    const [error, setError] = useState('');

    if (!isOpen) return null;

    const handleGenerate = async () => {
        if (!prompt.trim()) {
            setError('Please describe what you want to create');
            return;
        }
        setError('');
        try {
            await createArtifact(type, prompt, title || undefined);
            setTitle('');
            setPrompt('');
        } catch {
            setError('Generation failed. Please try again.');
        }
    };

    const modalContent = (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={() => setOpen(false)}>
            <div className="bg-background border border-border rounded-lg p-6 max-w-2xl w-full mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
                <h2 className="text-xl font-semibold mb-4">Create Artifact</h2>

                {/* Type picker */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                    {TYPES.map(t => {
                        const Icon = t.icon;
                        const selected = type === t.key;
                        return (
                            <button
                                key={t.key}
                                onClick={() => setType(t.key)}
                                className={`flex flex-col items-center gap-2 p-4 rounded-lg border transition-colors ${
                                    selected
                                        ? 'border-primary bg-primary/10 text-primary'
                                        : 'border-border hover:border-primary/50 text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                <Icon className="w-6 h-6" />
                                <span className="text-sm font-medium">{t.label}</span>
                                <span className="text-[10px] opacity-60">{t.desc}</span>
                            </button>
                        );
                    })}
                </div>

                {/* Title */}
                <div className="mb-3">
                    <label className="block text-sm font-medium mb-1">Title (optional)</label>
                    <input
                        type="text"
                        value={title}
                        onChange={e => setTitle(e.target.value)}
                        placeholder="e.g., Q4 Sales Report"
                        className="w-full px-4 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                        disabled={isGenerating}
                    />
                </div>

                {/* Prompt */}
                <div className="mb-3">
                    <label className="block text-sm font-medium mb-1">
                        Describe your content <span className="text-destructive">*</span>
                    </label>
                    <textarea
                        value={prompt}
                        onChange={e => setPrompt(e.target.value)}
                        placeholder="Describe the content you want to generate..."
                        rows={4}
                        className="w-full px-4 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                        disabled={isGenerating}
                    />
                </div>

                {error && (
                    <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm mb-3">
                        {error}
                    </div>
                )}

                <div className="flex gap-3">
                    <button
                        onClick={() => setOpen(false)}
                        className="flex-1 py-2 px-4 rounded-lg border border-border hover:border-destructive hover:bg-destructive/10 transition-colors"
                        disabled={isGenerating}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleGenerate}
                        disabled={isGenerating || !prompt.trim()}
                        className="flex-1 py-2 px-4 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {isGenerating ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Generating...
                            </>
                        ) : (
                            'Generate Outline'
                        )}
                    </button>
                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
