import { useState, useEffect, useCallback, useMemo } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { useAppStore } from '@/store';
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

  if (!activeArtifact || slides.length === 0) return null;

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
      </div>

      {/* 3-Panel Layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: Filmstrip */}
        <SlideFilmstrip
          slides={slides}
          theme={theme}
          currentIndex={clampedIndex}
          onSelect={setCurrentSlideIndex}
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
        className="fixed inset-4 max-w-none translate-x-0 translate-y-0 left-0 top-0 flex flex-col bg-charcoal-900 rounded-xl border-border/30 overflow-hidden p-0 animate-modal-scale-in [&>button:last-child]:top-3 [&>button:last-child]:right-3 [&>button:last-child]:text-muted-foreground [&>button:last-child]:z-10"
      >
        <SlidePreviewContent key={openCount} />
      </DialogContent>
    </Dialog>
  );
}
