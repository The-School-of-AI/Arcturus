import { useState, useEffect, useRef } from 'react';
import { Send, Loader2, AlertCircle, AlertTriangle, History, MessageSquare, StickyNote, RotateCcw, Code2, Check } from 'lucide-react';
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
  /** Controlled: whether HTML editor is open */
  showHtml?: boolean;
  /** Controlled: toggle HTML editor */
  onToggleHtml?: () => void;
}

export function SlideEditPanel({ artifactId, activeSlide, slideIndex, revisionHeadId, showHtml: showHtmlProp, onToggleHtml }: SlideEditPanelProps) {
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
  const [showHtmlLocal, setShowHtmlLocal] = useState(false);
  const showHtml = showHtmlProp ?? showHtmlLocal;
  const toggleHtml = onToggleHtml ?? (() => setShowHtmlLocal(v => !v));
  const [htmlDraft, setHtmlDraft] = useState('');
  const [htmlSaving, setHtmlSaving] = useState(false);
  const [htmlSaved, setHtmlSaved] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const patchSlideContent = useAppStore(s => s.patchSlideContent);

  const handleRestore = async (revisionId: string, changeSummary: string) => {
    if (!window.confirm(`Restore to '${changeSummary}'? This will create a new revision.`)) return;
    setRestoreLoading(true);
    setRestoreError(null);
    try {
      await api.restoreRevision(artifactId, revisionId, revisionHeadId);
      await loadArtifact(artifactId);
      const data = await api.listRevisions(artifactId);
      setRevisions(data);
    } catch (err: any) {
      if (err?.response?.status === 409) {
        setRestoreError('Conflict: the artifact was modified. Please reload.');
      } else {
        setRestoreError(err?.response?.data?.detail || 'Restore failed');
      }
    } finally {
      setRestoreLoading(false);
    }
  };

  // Sync HTML draft when active slide changes
  useEffect(() => {
    setHtmlDraft(activeSlide.html || '');
    setHtmlSaved(false);
  }, [activeSlide.id, activeSlide.html]);

  const handleHtmlSave = async () => {
    if (htmlDraft === (activeSlide.html || '')) return;
    setHtmlSaving(true);
    try {
      await patchSlideContent(artifactId, { [slideIndex]: { html: htmlDraft } }, revisionHeadId);
      setHtmlSaved(true);
      setTimeout(() => setHtmlSaved(false), 2000);
      // Refresh revisions
      try {
        const data = await api.listRevisions(artifactId);
        setRevisions(data);
      } catch { /* ignore */ }
    } catch (e: any) {
      console.error('HTML save failed', e);
    } finally {
      setHtmlSaving(false);
    }
  };

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
    const prefix = `On slide ${slideIndex + 1} (${activeSlide.slide_type}, title: '${activeSlide.title || 'untitled'}'): `;
    await applyEditInstruction(artifactId, prefix + instruction.trim(), revisionHeadId);
    const { editError: err, editConflict: conflict } = useAppStore.getState();
    if (!err && !conflict) setInstruction('');
    try {
      const data = await api.listRevisions(artifactId);
      setRevisions(data);
    } catch { /* ignore */ }
  };

  return (
    <div className="w-80 border-l border-border[0.06] bg-[#0a0b0d] flex flex-col shrink-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border[0.06] flex items-center gap-2">
        <MessageSquare className="w-3.5 h-3.5 text-blue-400/70" />
        <span className="text-xs font-semibold text-white/80">Edit Slide {slideIndex + 1}</span>
      </div>

      {/* Edit input */}
      <div className="p-4 border-b border-border[0.06] space-y-3">
        <Textarea
          value={instruction}
          onChange={e => { setInstruction(e.target.value); clearEditState(); }}
          placeholder="e.g. 'Make the title shorter' or 'Add a stat about revenue'"
          className="min-h-[70px] text-xs bg-white/[0.03] border-border[0.08] text-white/90 placeholder:text-white/20 focus:border-blue-500/40 resize-none"
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
          className="w-full bg-blue-600 hover:bg-blue-500 text-white h-8 text-xs"
        >
          {editLoading ? (
            <><Loader2 className="w-3 h-3 animate-spin mr-1.5" /> Applying...</>
          ) : (
            <><Send className="w-3 h-3 mr-1.5" /> Apply Edit</>
          )}
        </Button>

        {editError && (
          <div className="rounded-md bg-red-500/10 border border-red-500/20 p-2.5 text-xs text-red-400 flex items-start gap-2">
            <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
            <span>{editError}</span>
          </div>
        )}

        {editConflict && (
          <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2.5 text-xs text-amber-400 flex items-center gap-2">
            <AlertTriangle className="w-3 h-3 shrink-0" />
            <span>Conflict detected. </span>
            <button
              onClick={() => { loadArtifact(artifactId); clearEditState(); }}
              className="underline hover:text-amber-300"
            >
              Reload
            </button>
          </div>
        )}
      </div>

      {/* Revisions */}
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <History className="w-3 h-3 text-white/30" />
        <span className="text-xs font-semibold text-white/40 uppercase tracking-wider">Revisions</span>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-4 pb-3 space-y-1.5">
          {revisionsLoading ? (
            <div className="flex items-center gap-2 text-xs text-white/30 py-4">
              <Loader2 className="w-3 h-3 animate-spin" />
              Loading...
            </div>
          ) : revisions.length === 0 ? (
            <p className="text-xs text-white/20 italic py-2">No revisions yet</p>
          ) : (
            revisions.map((rev) => (
              <div key={rev.id} className="rounded-md border border-border[0.06] bg-white/[0.02] p-2.5 hover:bg-white/[0.04] transition-colors">
                <div className="flex items-center gap-1">
                  <p className="text-[11px] text-white/70 truncate flex-1">{rev.change_summary}</p>
                  {rev.id === revisionHeadId ? (
                    <span className="text-2xs text-emerald-400/60 shrink-0 font-medium">current</span>
                  ) : (
                    <button
                      onClick={() => handleRestore(rev.id, rev.change_summary)}
                      disabled={restoreLoading}
                      className="flex items-center gap-1 text-2xs text-blue-400/60 hover:text-blue-400 disabled:opacity-50 transition-colors shrink-0"
                    >
                      <RotateCcw className="w-2.5 h-2.5" /> Restore
                    </button>
                  )}
                </div>
                {rev.created_at && (
                  <span className="text-2xs text-white/20">
                    {formatDistanceToNow(new Date(rev.created_at), { addSuffix: true })}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {restoreError && (
        <div className="mx-4 mb-2 rounded-md bg-red-500/10 border border-red-500/20 p-2 text-xs text-red-400 flex items-start gap-2">
          <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
          <span>{restoreError}</span>
        </div>
      )}

      {/* Speaker Notes Toggle */}
      <div className="border-t border-border[0.06]">
        <button
          onClick={() => setShowNotes(v => !v)}
          className={cn(
            'w-full flex items-center gap-2 px-4 py-2.5 text-xs transition-colors',
            showNotes ? 'text-blue-400/80' : 'text-white/30 hover:text-white/50'
          )}
        >
          <StickyNote className="w-3 h-3" />
          Speaker Notes
        </button>
        {showNotes && activeSlide.speaker_notes && (
          <div className="px-4 pb-3 text-xs text-white/40 italic whitespace-pre-wrap">
            {activeSlide.speaker_notes}
          </div>
        )}
        {showNotes && !activeSlide.speaker_notes && (
          <div className="px-4 pb-3 text-xs text-white/15 italic">
            No speaker notes for this slide.
          </div>
        )}
      </div>

      {/* HTML Editor Toggle */}
      {activeSlide.html && (
        <div className="border-t border-border[0.06]">
          <button
            onClick={toggleHtml}
            className={cn(
              'w-full flex items-center gap-2 px-4 py-2.5 text-xs transition-colors',
              showHtml ? 'text-orange-400/80' : 'text-white/30 hover:text-white/50'
            )}
          >
            <Code2 className="w-3 h-3" />
            Edit HTML
          </button>
          {showHtml && (
            <div className="px-3 pb-3 space-y-2">
              <textarea
                value={htmlDraft}
                onChange={e => { setHtmlDraft(e.target.value); setHtmlSaved(false); }}
                spellCheck={false}
                className="w-full h-48 text-xs font-mono leading-relaxed bg-black/40 border border-border[0.08] rounded-md p-2 text-orange-200/80 placeholder:text-white/15 focus:border-orange-500/40 focus:outline-none resize-y"
              />
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={handleHtmlSave}
                  disabled={htmlSaving || htmlDraft === (activeSlide.html || '')}
                  className="h-7 text-xs bg-orange-600 hover:bg-orange-500 text-white disabled:opacity-40"
                >
                  {htmlSaving ? (
                    <><Loader2 className="w-3 h-3 animate-spin mr-1" /> Saving...</>
                  ) : htmlSaved ? (
                    <><Check className="w-3 h-3 mr-1" /> Saved</>
                  ) : (
                    'Save HTML'
                  )}
                </Button>
                {htmlDraft !== (activeSlide.html || '') && (
                  <button
                    onClick={() => { setHtmlDraft(activeSlide.html || ''); setHtmlSaved(false); }}
                    className="text-xs text-white/30 hover:text-white/60 transition-colors"
                  >
                    Reset
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
