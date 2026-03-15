import { FileText, Sparkles } from 'lucide-react';
import React from 'react';
import { usePagesStore } from '../usePagesStore';
import { PageRenderer } from './PageRenderer';

export const PagesDashboard: React.FC = () => {
    const selectedPage = usePagesStore(s => s.selectedPage);

    if (!selectedPage) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-4 text-center px-8">
                <div className="p-6 rounded-2xl bg-muted/30 border border-border/30">
                    <FileText className="w-12 h-12 text-muted-foreground/40 mx-auto" />
                </div>
                <div>
                    <h2 className="text-xl font-semibold mb-1">Spark Pages</h2>
                    <p className="text-sm text-muted-foreground max-w-sm">
                        Select a page from the sidebar or generate a new one to get started.
                    </p>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground/60">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>AI-synthesized content with real web sources</span>
                </div>
            </div>
        );
    }

    const citations = Array.isArray(selectedPage.citations)
        ? selectedPage.citations
        : Object.entries(selectedPage.citations || {}).map(([id, c]: [string, any]) => ({
            id,
            url: c.url || '',
            title: c.title || id,
            snippet: c.snippet,
        }));

    return (
        <PageRenderer
            isEditable
            page={{
                id: selectedPage.id,
                query: selectedPage.query,
                template: selectedPage.template,
                status: selectedPage.status,
                sections: selectedPage.sections || [],
                citations,
                metadata: {
                    created_at: selectedPage.created_at,
                    created_by: selectedPage.created_by,
                },
            }}
        />
    );
};
