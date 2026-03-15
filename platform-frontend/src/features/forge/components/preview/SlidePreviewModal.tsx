import { useState, useEffect, useCallback, useMemo } from 'react';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { X, Loader2, AlertCircle } from 'lucide-react';
import { useAppStore } from '@/store';
import { api, API_BASE } from '@/lib/api';
import { SlideFilmstrip } from './SlideFilmstrip';
import { SlideRenderer } from './SlideRenderer';
import { SlideEditPanel } from './SlideEditPanel';
import { SlideBottomBar } from './SlideBottomBar';
import type { SlideTheme } from './renderers';
import type { Slide } from './normalizers';

/** Default theme used when no theme info is available */
const DEFAULT_THEME: SlideTheme = {
  id: 'corporate-blue',
  name: 'Corporate Blue',
  colors: {
    primary: '#1E3A5F',
    secondary: '#4A7FB5',
    accent: '#A87A22',
    background: '#F5F6F8',
    text: '#1C2D3F',
    text_light: '#7B8FA3',
    title_background: '#152C47',
  },
  font_heading: 'Calibri',
  font_body: 'Corbel',
};

/**
 * Inner component that mounts fresh each time the modal opens (via key prop).
 * This avoids needing setState-in-effect or ref-during-render for initialization.
 */
function SlidePreviewContent() {
  const activeArtifact = useAppStore(s => s.activeArtifact);
  const studioThemes = useAppStore(s => s.studioThemes);
  const loadArtifact = useAppStore(s => s.loadArtifact);

  // Re-fetch artifact on mount to ensure content_tree is fresh
  const [refreshed, setRefreshed] = useState(false);
  useEffect(() => {
    if (activeArtifact?.id && !activeArtifact?.content_tree?.slides) {
      loadArtifact(activeArtifact.id).finally(() => setRefreshed(true));
    } else {
      setRefreshed(true);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- intentional mount-only

  // Extract slides from content_tree
  const slides: Slide[] = useMemo(() => {
    if (!activeArtifact?.content_tree?.slides) return [];
    return activeArtifact.content_tree.slides;
  }, [activeArtifact?.content_tree?.slides]);

  // Initialize once on mount (this component remounts each open via key)
  const initialTheme = activeArtifact?.theme_id
    ?? studioThemes[0]?.id
    ?? 'corporate-blue';

  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [selectedThemeId, setSelectedThemeId] = useState<string>(initialTheme);

  // Resolve theme object from ID
  const theme: SlideTheme = useMemo(() => {
    const found = studioThemes.find((t: { id: string }) => t.id === selectedThemeId);
    if (found) return found as SlideTheme;
    return DEFAULT_THEME;
  }, [studioThemes, selectedThemeId]);

  // Image base URL for preview (will be undefined for non-slides)
  const imageBaseUrl = activeArtifact?.id
    ? `${API_BASE}/studio/${activeArtifact.id}/images`
    : undefined;

  // Poll for available slide images (background generation may still be running)
  const [availableImageIds, setAvailableImageIds] = useState<ReadonlySet<string>>(new Set());
  // Match server logic: only count slides that have an image element with string prompt content
  const expectedImageSlides = useMemo(() => {
    return slides.filter(s =>
      (s.slide_type === 'image_text' || s.slide_type === 'image_full')
      && s.elements.some(el => el.type === 'image' && typeof el.content === 'string' && el.content)
    ).length;
  }, [slides]);

  // revision_head_id changes on every edit → restarts polling after backend cache invalidation
  const revisionHeadId = activeArtifact?.revision_head_id;

  useEffect(() => {
    // Always clear stale IDs when deps change (handles edit-away-all-images case)
    setAvailableImageIds(new Set());

    if (!activeArtifact?.id || expectedImageSlides === 0) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const ids = await api.listSlideImages(activeArtifact.id);
        if (!cancelled) {
          setAvailableImageIds(prev => {
            if (ids.length === prev.size && ids.every(id => prev.has(id))) return prev;
            return new Set(ids);
          });
        }
        // Stop polling once all expected images are available
        if (ids.length >= expectedImageSlides) return;
      } catch { /* ignore errors during polling */ }
      if (!cancelled) pollTimer = setTimeout(poll, 4000);
    };

    let pollTimer: ReturnType<typeof setTimeout>;
    poll();
    return () => { cancelled = true; clearTimeout(pollTimer); };
  }, [activeArtifact?.id, expectedImageSlides, revisionHeadId]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const tag = (e.target as HTMLElement)?.tagName;
    if (tag === 'TEXTAREA' || tag === 'INPUT') return;

    if (e.key === 'ArrowLeft') {
      setCurrentSlideIndex(i => Math.max(0, i - 1));
    } else if (e.key === 'ArrowRight') {
      setCurrentSlideIndex(i => Math.min(slides.length - 1, i + 1));
    }
  }, [slides.length]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Clamp index when slides change (e.g. after edit removes a slide)
  const clampedIndex = slides.length > 0
    ? Math.min(currentSlideIndex, slides.length - 1)
    : 0;

  // Show loading/empty state instead of blank modal
  if (!activeArtifact || slides.length === 0) {
    return (
      <>
        <DialogTitle className="sr-only">Slide Preview</DialogTitle>
        <div className="h-12 border-b border-border/30 flex items-center px-5 shrink-0">
          <span className="text-base font-semibold text-foreground tracking-tight">
            Slide Preview
          </span>
          <div className="ml-auto">
            <DialogClose asChild>
              <Button variant="ghost" size="sm" className="gap-1.5 text-foreground hover:text-foreground hover:bg-muted/40">
                <X className="w-3.5 h-3.5" />
                Close
              </Button>
            </DialogClose>
          </div>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-muted-foreground">
          {!refreshed ? (
            <>
              <Loader2 className="w-6 h-6 animate-spin" />
              <p className="text-sm">Loading slides...</p>
            </>
          ) : (
            <>
              <AlertCircle className="w-6 h-6" />
              <p className="text-sm">No slides available to preview</p>
            </>
          )}
        </div>
      </>
    );
  }

  const activeSlide = slides[clampedIndex] || slides[0];

  return (
    <>
      <DialogTitle className="sr-only">Slide Preview</DialogTitle>

      {/* Header */}
      <div className="h-12 border-b border-border/30 flex items-center px-5 shrink-0">
        <span className="text-base font-semibold text-foreground tracking-tight">
          Slide Preview
        </span>
        <span className="text-sm text-muted-foreground ml-3 truncate max-w-[400px]">
          — {activeArtifact.title}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <DialogClose asChild>
            <Button variant="ghost" size="sm" className="gap-1.5 text-foreground hover:text-foreground hover:bg-muted/40">
              <X className="w-3.5 h-3.5" />
              Close Preview
              <kbd className="ml-1 pointer-events-none hidden h-5 select-none items-center rounded border border-border/40 bg-muted/50 px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:inline-flex">
                Esc
              </kbd>
            </Button>
          </DialogClose>
        </div>
      </div>

      {/* 3-Panel Layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: Filmstrip */}
        <SlideFilmstrip
          slides={slides}
          theme={theme}
          currentIndex={clampedIndex}
          onSelect={setCurrentSlideIndex}
          imageBaseUrl={imageBaseUrl}
          availableImageIds={availableImageIds}
        />

        {/* Center: Main Preview */}
        <div className="flex-1 flex items-center justify-center p-10 bg-charcoal-950/30 min-w-0">
          <div
            key={clampedIndex}
            className="w-full max-w-4xl animate-slide-fade-in"
          >
            <SlideRenderer
              slide={activeSlide}
              theme={theme}
              slideIndex={clampedIndex}
              totalSlides={slides.length}
              imageBaseUrl={imageBaseUrl}
              availableImageIds={availableImageIds}
            />
          </div>
        </div>

        {/* Right: Edit Panel */}
        <SlideEditPanel
          artifactId={activeArtifact.id}
          activeSlide={activeSlide}
          slideIndex={clampedIndex}
          revisionHeadId={activeArtifact.revision_head_id}
        />
      </div>

      {/* Bottom Bar */}
      <SlideBottomBar
        artifactId={activeArtifact.id}
        artifactTitle={activeArtifact.title}
        currentIndex={clampedIndex}
        totalSlides={slides.length}
        selectedThemeId={selectedThemeId}
        onThemeChange={setSelectedThemeId}
        onNavigate={setCurrentSlideIndex}
      />
    </>
  );
}

/**
 * Outer wrapper: uses a `key` to remount inner content each time modal opens,
 * which naturally resets all state without setState-in-effect.
 */
export function SlidePreviewModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [openCount, setOpenCount] = useState(0);

  const handleOpenChange = (v: boolean) => {
    if (v) {
      setOpenCount(c => c + 1);
    } else {
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        hideCloseButton
        noDefaultAnimation
        className="fixed inset-4 max-w-none translate-x-0 translate-y-0 left-0 top-0 flex flex-col bg-charcoal-900 rounded-xl border-border/30 overflow-hidden p-0 animate-modal-scale-in"
      >
        <SlidePreviewContent key={openCount} />
      </DialogContent>
    </Dialog>
  );
}
