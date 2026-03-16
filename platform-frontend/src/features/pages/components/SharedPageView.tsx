import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { API_BASE } from '@/lib/api';
import { AlertCircle, Globe, Loader2, Lock } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { PageRenderer } from './PageRenderer';

const SharedPageView: React.FC = () => {
    const token = window.location.pathname.replace(/^\/shared\//, '');
    const [password, setPassword] = useState('');
    const [needsPassword, setNeedsPassword] = useState(false);
    const [wrongPassword, setWrongPassword] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [pageData, setPageData] = useState<any>(null);
    const [shareInfo, setShareInfo] = useState<any>(null);

    const fetchPage = async (pwd?: string) => {
        setLoading(true);
        setError(null);
        setWrongPassword(false);
        try {
            const qs = pwd ? `?password=${encodeURIComponent(pwd)}` : '';
            const res = await fetch(`${API_BASE}/pages/shared/${token}${qs}`);
            if (res.status === 401) {
                setNeedsPassword(true);
                if (pwd) setWrongPassword(true);
            } else if (res.status === 404) {
                setError('This page link is invalid or has expired.');
            } else if (res.ok) {
                const data = await res.json();
                setPageData(data.page);
                setShareInfo(data.share_info);
                setNeedsPassword(false);
            } else {
                setError('Failed to load the shared page.');
            }
        } catch {
            setError('Network error. Please check your connection.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchPage(); }, []);

    if (loading) {
        return (
            <div className="h-screen flex items-center justify-center bg-background">
                <div className="flex flex-col items-center gap-3 text-muted-foreground">
                    <Loader2 className="w-8 h-8 animate-spin" />
                    <p className="text-sm">Loading shared page…</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-screen flex flex-col items-center justify-center gap-4 bg-background text-foreground">
                <AlertCircle className="w-12 h-12 text-red-400" />
                <h2 className="text-xl font-semibold">Page Unavailable</h2>
                <p className="text-muted-foreground">{error}</p>
            </div>
        );
    }

    if (needsPassword) {
        return (
            <div className="h-screen flex flex-col items-center justify-center gap-6 bg-background text-foreground p-8">
                <Lock className="w-14 h-14 text-primary/60" />
                <div className="text-center">
                    <h2 className="text-2xl font-bold mb-1">Password Protected</h2>
                    <p className="text-muted-foreground text-sm">Enter the password to view this page</p>
                </div>
                {wrongPassword && (
                    <p className="text-red-400 text-sm">Incorrect password. Please try again.</p>
                )}
                <div className="flex gap-2 w-full max-w-sm">
                    <Input
                        type="password"
                        placeholder="Enter password…"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && fetchPage(password)}
                        autoFocus
                    />
                    <Button onClick={() => fetchPage(password)} disabled={!password.trim()}>
                        Unlock
                    </Button>
                </div>
            </div>
        );
    }

    if (!pageData) return null;

    const citations = Array.isArray(pageData.citations)
        ? pageData.citations
        : Object.entries(pageData.citations || {}).map(([id, c]: [string, any]) => ({
            id,
            url: c.url || '',
            title: c.title || id,
            snippet: c.snippet,
        }));

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col">
            {/* Shared page banner */}
            <div className="border-b border-border/50 px-6 py-2.5 flex items-center justify-between bg-muted/30 shrink-0">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Globe className="w-4 h-4" />
                    <span>Shared via <span className="font-medium text-foreground">Arcturus Pages</span></span>
                </div>
                {shareInfo?.access_count !== undefined && (
                    <span className="text-xs text-muted-foreground">{shareInfo.access_count} views</span>
                )}
            </div>
            <div className="flex-1 overflow-hidden">
                <PageRenderer
                    page={{
                        id: pageData.id,
                        query: pageData.query,
                        template: pageData.template,
                        status: pageData.status,
                        sections: pageData.sections || [],
                        citations,
                        metadata: {
                            created_at: pageData.metadata?.created_at || pageData.created_at || new Date().toISOString(),
                            created_by: pageData.metadata?.created_by || pageData.created_by || 'unknown',
                        },
                    }}
                />
            </div>
        </div>
    );
};

export default SharedPageView;
