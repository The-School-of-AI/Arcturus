import { Sparkles, FileText } from 'lucide-react';

interface AppCreationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onCreateBlank: () => void;
    onGenerateWithAI: () => void;
}

export function AppCreationModal({ isOpen, onClose, onCreateBlank, onGenerateWithAI }: AppCreationModalProps) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onClose} style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0 }}>
            <div className="bg-background border border-border rounded-lg p-6 max-w-md w-full mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
                <h2 className="text-xl font-semibold mb-4">Create New Dashboard</h2>

                <div className="space-y-3">
                    {/* Create Blank Option */}
                    <button
                        onClick={() => {
                            onClose();
                            onCreateBlank();
                        }}
                        className="w-full flex items-start gap-4 p-4 rounded-lg border-2 border-border hover:border-primary hover:bg-muted/50 transition-all text-left group"
                    >
                        <div className="p-2 rounded-lg bg-muted group-hover:bg-primary/20 transition-colors">
                            <FileText className="w-6 h-6" />
                        </div>
                        <div className="flex-1">
                            <div className="font-bold mb-1">Design</div>
                            <div className="text-xs text-muted-foreground">Start with an empty canvas and build manually</div>
                        </div>
                    </button>

                    {/* Generate with AI Option */}
                    <button
                        onClick={() => {
                            onClose();
                            onGenerateWithAI();
                        }}
                        className="w-full flex items-start gap-4 p-4 rounded-lg border-2 border-border hover:border-primary hover:bg-muted/50 transition-all text-left group"
                    >
                        <div className="p-2 rounded-lg bg-primary/20 group-hover:bg-primary/30 transition-colors">
                            <Sparkles className="w-6 h-6 text-primary" />
                        </div>
                        <div className="flex-1">
                            <div className="font-bold mb-1 flex items-center gap-2">
                                Ask AI
                            </div>
                            <div className="text-xs text-muted-foreground">Describe your dashboard and let AI create it</div>
                        </div>
                    </button>
                </div>

                <button
                    onClick={onClose}
                    className="mt-4 w-full py-2 px-4 rounded-lg border border-border hover:border-destructive hover:bg-destructive/10 transition-colors"
                >
                    Cancel
                </button>
            </div>
        </div>
    );
}
