import { useState, useEffect } from 'react';
import { Send, Loader2, AlertCircle, AlertTriangle, History, MessageSquare, StickyNote } from 'lucide-react';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import type { Slide } from './normalizers';

interface SlideEditPanelProps {
  artifactId: string;
  activeSlide: Slide;
  slideIndex: number;
  revisionHeadId?: string;
}

export function SlideEditPanel({ artifactId, activeSlide, slideIndex, revisionHeadId }: SlideEditPanelProps) {
  const applyEditInstruction = useAppStore(s => s.applyEditInstruction);
  const editLoading = useAppStore(s => s.editLoading);
  const editError = useAppStore(s => s.editError);
  const editConflict = useAppStore(s => s.editConflict);
  const clearEditState = useAppStore(s => s.clearEditState);
  const loadArtifact = useAppStore(s => s.loadArtifact);

  const [instruction, setInstruction] = useState('');
  const [revisions, setRevisions] = useState<{ id: string; change_summary: string; created_at?: string }[]>([]);
  const [revisionsLoading, setRevisionsLoading] = useState(false);
  const [showNotes, setShowNotes] = useState(false);

  // Fetch revisions on open and after edits
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setRevisionsLoading(true);
      try {
        const data = await api.listRevisions(artifactId);
        if (!cancelled) setRevisions(data);
      } catch {
        if (!cancelled) setRevisions([]);
      } finally {
        if (!cancelled) setRevisionsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [artifactId, revisionHeadId]);

  const handleSubmit = async () => {
    if (!instruction.trim()) return;
    // Auto-prefix with slide context
    const prefix = `On slide ${slideIndex + 1} (${activeSlide.slide_type}, title: '${activeSlide.title || 'untitled'}'): `;
    await applyEditInstruction(artifactId, prefix + instruction.trim(), revisionHeadId);
    setInstruction('');
    // Refresh revisions
    try {
      const data = await api.listRevisions(artifactId);
      setRevisions(data);
    } catch { /* ignore */ }
  };

  return (
    <div className="w-80 border-l border-border/30 bg-charcoal-950/50 flex flex-col shrink-0">
      {/* Header */}
      <div className="p-3 border-b border-border/30 flex items-center gap-2">
        <MessageSquare className="w-3.5 h-3.5 text-primary" />
        <span className="text-xs font-semibold text-foreground">Edit Slide {slideIndex + 1}</span>
      </div>

      {/* Edit input */}
      <div className="p-3 border-b border-border/30 space-y-2">
        <Textarea
          value={instruction}
          onChange={e => { setInstruction(e.target.value); clearEditState(); }}
          placeholder="e.g. 'Make the title shorter' or 'Add a stat about revenue'"
          className="min-h-[60px] text-xs bg-charcoal-900 border-border/30"
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <Button
          size="sm"
          onClick={handleSubmit}
          disabled={editLoading || !instruction.trim()}
          className="w-full"
        >
          {editLoading ? (
            <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Applying...</>
          ) : (
            <><Send className="w-3 h-3 mr-1" /> Apply Edit</>
          )}
        </Button>

        {editError && (
          <div className="rounded-md bg-red-500/10 border border-red-500/20 p-2 text-xs text-red-400 flex items-start gap-2">
            <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
            <span>{editError}</span>
          </div>
        )}

        {editConflict && (
          <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2 text-xs text-amber-400 flex items-center gap-2">
            <AlertTriangle className="w-3 h-3 shrink-0" />
            <span>Conflict: another edit was applied. </span>
            <button
              onClick={() => { loadArtifact(artifactId); clearEditState(); }}
              className="underline hover:text-amber-300"
            >
              Reload Latest
            </button>
          </div>
        )}
      </div>

      {/* Revisions */}
      <div className="flex items-center gap-2 px-3 pt-3 pb-1">
        <History className="w-3 h-3 text-muted-foreground" />
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Revisions</span>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-3 pb-2 space-y-1.5">
          {revisionsLoading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground py-4">
              <Loader2 className="w-3 h-3 animate-spin" />
              Loading...
            </div>
          ) : revisions.length === 0 ? (
            <p className="text-xs text-muted-foreground italic py-2">No revisions yet</p>
          ) : (
            revisions.map((rev) => (
              <div key={rev.id} className="rounded-md border border-border/30 bg-charcoal-900/50 p-2">
                <p className="text-[11px] text-foreground truncate">{rev.change_summary}</p>
                {rev.created_at && (
                  <span className="text-[9px] text-muted-foreground">
                    {formatDistanceToNow(new Date(rev.created_at), { addSuffix: true })}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Speaker Notes Toggle */}
      <div className="border-t border-border/30">
        <button
          onClick={() => setShowNotes(v => !v)}
          className={cn(
            'w-full flex items-center gap-2 px-3 py-2 text-xs transition-colors',
            showNotes ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <StickyNote className="w-3 h-3" />
          Speaker Notes
        </button>
        {showNotes && activeSlide.speaker_notes && (
          <div className="px-3 pb-3 text-xs text-muted-foreground italic whitespace-pre-wrap">
            {activeSlide.speaker_notes}
          </div>
        )}
        {showNotes && !activeSlide.speaker_notes && (
          <div className="px-3 pb-3 text-xs text-muted-foreground/50 italic">
            No speaker notes for this slide.
          </div>
        )}
      </div>
    </div>
  );
}
