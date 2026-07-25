import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { X, Loader2, AlertCircle, Maximize2, Minimize2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '@/store';
import { api, API_BASE } from '@/lib/api';
import { SlideFilmstrip } from './SlideFilmstrip';
import { SlideRenderer } from './SlideRenderer';
import { SlideEditPanel } from './SlideEditPanel';
import { SlideBottomBar } from './SlideBottomBar';
import { useSlideFonts } from '../../hooks/useSlideFonts';
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

type NavDirection = 'right' | 'left' | 'down' | 'up';

const DIRECTION_ANIMATION: Record<NavDirection, string> = {
  right: 'animate-slide-from-right',
  left: 'animate-slide-from-left',
  down: 'animate-slide-from-bottom',
  up: 'animate-slide-from-top',
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

  // Load custom fonts declared by LLM in content_tree metadata
  const deckFonts = useMemo(() => {
    const meta = activeArtifact?.content_tree?.metadata;
    return Array.isArray(meta?.fonts) ? meta.fonts as string[] : undefined;
  }, [activeArtifact?.content_tree?.metadata]);
  useSlideFonts(deckFonts);

  // Initialize once on mount (this component remounts each open via key)
  const initialTheme = activeArtifact?.theme_id
    ?? studioThemes[0]?.id
    ?? 'corporate-blue';

  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [selectedThemeId, setSelectedThemeId] = useState<string>(initialTheme);
  const [navDirection, setNavDirection] = useState<NavDirection>('right');
  const [slideKey, setSlideKey] = useState(0);
  const [slideshowMode, setSlideshowMode] = useState(false);
  const [showHtmlEditor, setShowHtmlEditor] = useState(false);

  // Resolve theme object from ID
  const theme: SlideTheme = useMemo(() => {
    const found = studioThemes.find((t: { id: string }) => t.id === selectedThemeId);
    if (found) return found as SlideTheme;
    // Fall back to LLM-generated custom theme stored on artifact
    if (activeArtifact?.custom_theme && typeof activeArtifact.custom_theme === 'object' && activeArtifact.custom_theme.colors) {
      return activeArtifact.custom_theme as SlideTheme;
    }
    return DEFAULT_THEME;
  }, [studioThemes, selectedThemeId, activeArtifact?.custom_theme]);

  // Image base URL for preview (will be undefined for non-slides)
  const imageBaseUrl = activeArtifact?.id
    ? `${API_BASE}/studio/${activeArtifact.id}/images`
    : undefined;

  // Poll for available slide images (background generation may still be running)
  const [availableImageIds, setAvailableImageIds] = useState<ReadonlySet<string>>(new Set());
  const expectedImageSlides = useMemo(() => {
    return slides.filter(s =>
      (s.slide_type === 'image_text' || s.slide_type === 'image_full')
      && s.elements.some(el => el.type === 'image' && typeof el.content === 'string' && el.content)
    ).length;
  }, [slides]);

  const revisionHeadId = activeArtifact?.revision_head_id;

  useEffect(() => {
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
        if (ids.length >= expectedImageSlides) return;
      } catch { /* ignore errors during polling */ }
      if (!cancelled) pollTimer = setTimeout(poll, 4000);
    };

    let pollTimer: ReturnType<typeof setTimeout>;
    poll();
    return () => { cancelled = true; clearTimeout(pollTimer); };
  }, [activeArtifact?.id, expectedImageSlides, revisionHeadId]);

  // Navigate with direction tracking
  const navigateTo = useCallback((index: number, direction: NavDirection) => {
    setNavDirection(direction);
    setCurrentSlideIndex(index);
    setSlideKey(k => k + 1);
  }, []);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const tag = (e.target as HTMLElement)?.tagName;
    if (tag === 'TEXTAREA' || tag === 'INPUT') return;

    if (e.key === 'ArrowLeft') {
      setCurrentSlideIndex(i => {
        const next = Math.max(0, i - 1);
        if (next !== i) { setNavDirection('left'); setSlideKey(k => k + 1); }
        return next;
      });
    } else if (e.key === 'ArrowRight' || e.key === ' ') {
      if (e.key === ' ') e.preventDefault();
      setCurrentSlideIndex(i => {
        const next = Math.min(slides.length - 1, i + 1);
        if (next !== i) { setNavDirection('right'); setSlideKey(k => k + 1); }
        return next;
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setCurrentSlideIndex(i => {
        const next = Math.max(0, i - 1);
        if (next !== i) { setNavDirection('up'); setSlideKey(k => k + 1); }
        return next;
      });
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setCurrentSlideIndex(i => {
        const next = Math.min(slides.length - 1, i + 1);
        if (next !== i) { setNavDirection('down'); setSlideKey(k => k + 1); }
        return next;
      });
    } else if (e.key === 'f' || e.key === 'F') {
      setSlideshowMode(m => !m);
    } else if (e.key === 'Escape' && slideshowMode) {
      e.preventDefault();
      e.stopPropagation();
      setSlideshowMode(false);
    }
  }, [slides.length, slideshowMode]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [handleKeyDown]);

  // Clamp index when slides change
  const clampedIndex = slides.length > 0
    ? Math.min(currentSlideIndex, slides.length - 1)
    : 0;

  // Show loading/empty state
  if (!activeArtifact || slides.length === 0) {
    return (
      <>
        <DialogTitle className="sr-only">Slide Preview</DialogTitle>
        <div className="h-14 border-b border-border[0.06] flex items-center px-6 shrink-0 bg-[#0a0b0d]">
          <span className="text-sm font-semibold text-white/90 tracking-tight">
            Slide Preview
          </span>
          <div className="ml-auto">
            <DialogClose asChild>
              <Button variant="ghost" size="sm" className="gap-1.5 text-white/60 hover:text-white hover:bg-accent[0.06]">
                <X className="w-4 h-4" />
              </Button>
            </DialogClose>
          </div>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-white/40 bg-[#0d0e11]">
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
  const animClass = DIRECTION_ANIMATION[navDirection];

  // ─── SLIDESHOW (FULLSCREEN) MODE ───
  if (slideshowMode) {
    return (
      <>
        <DialogTitle className="sr-only">Slideshow</DialogTitle>
        <div className="fixed inset-0 z-[100] bg-black flex items-center justify-center cursor-none group"
          onClick={() => {
            setCurrentSlideIndex(i => {
              const next = Math.min(slides.length - 1, i + 1);
              if (next !== i) { setNavDirection('right'); setSlideKey(k => k + 1); }
              return next;
            });
          }}
        >
          {/* Slide */}
          <div
            key={`ss-${slideKey}`}
            className={`w-full max-w-[90vw] max-h-[90vh] aspect-[16/9] ${animClass}`}
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

          {/* Hover controls */}
          <div className="absolute bottom-0 left-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <div className="flex items-center justify-center gap-4 pb-8">
              <button
                onClick={e => { e.stopPropagation(); navigateTo(Math.max(0, clampedIndex - 1), 'left'); }}
                disabled={clampedIndex === 0}
                className="p-2 rounded-full bg-accent backdrop-blur-sm text-white/80 hover:bg-accent hover:text-white disabled:opacity-30 transition-all"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <span className="text-white/60 text-sm font-mono min-w-[60px] text-center tabular-nums">
                {clampedIndex + 1} / {slides.length}
              </span>
              <button
                onClick={e => { e.stopPropagation(); navigateTo(Math.min(slides.length - 1, clampedIndex + 1), 'right'); }}
                disabled={clampedIndex >= slides.length - 1}
                className="p-2 rounded-full bg-accent backdrop-blur-sm text-white/80 hover:bg-accent hover:text-white disabled:opacity-30 transition-all"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Exit hint */}
          <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <button
              onClick={e => { e.stopPropagation(); setSlideshowMode(false); }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent backdrop-blur-sm text-white/70 text-xs hover:bg-accent hover:text-white transition-all"
            >
              <Minimize2 className="w-3.5 h-3.5" />
              Exit
              <kbd className="ml-1 px-1.5 py-0.5 rounded bg-accent text-xs font-mono">Esc</kbd>
            </button>
          </div>
        </div>
      </>
    );
  }

  // ─── NORMAL PREVIEW MODE ───
  return (
    <>
      <DialogTitle className="sr-only">Slide Preview</DialogTitle>

      {/* Header — sleek dark gradient */}
      <div className="h-14 border-b border-border[0.06] flex items-center px-6 shrink-0 bg-[#0a0b0d]">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm font-semibold text-white/90 tracking-tight shrink-0">
            Slide Preview
          </span>
          <span className="text-xs text-white/30 truncate max-w-[300px]">
            {activeArtifact.title}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSlideshowMode(true)}
            className="gap-1.5 h-8 text-white/50 hover:text-white hover:bg-accent[0.06] text-xs"
            title="Slideshow mode (F)"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            Slideshow
          </Button>
          <DialogClose asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-white/40 hover:text-white hover:bg-accent[0.06]">
              <X className="w-4 h-4" />
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
          onSelect={(i) => navigateTo(i, i > clampedIndex ? 'right' : 'left')}
          imageBaseUrl={imageBaseUrl}
          availableImageIds={availableImageIds}
        />

        {/* Center: Main Preview */}
        <div className="flex-1 flex items-center justify-center min-w-0 relative"
          style={{
            background: 'radial-gradient(ellipse at center, #141519 0%, #0a0b0d 70%)',
          }}
        >
          {/* Subtle grid pattern */}
          <div className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.4) 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
          />

          {/* Navigation arrows */}
          <button
            onClick={() => navigateTo(Math.max(0, clampedIndex - 1), 'left')}
            disabled={clampedIndex === 0}
            className="absolute left-4 z-10 p-2 rounded-full bg-accent[0.04] border border-border[0.06] text-white/30 hover:bg-accent[0.08] hover:text-white/60 disabled:opacity-0 transition-all duration-200"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            onClick={() => navigateTo(Math.min(slides.length - 1, clampedIndex + 1), 'right')}
            disabled={clampedIndex >= slides.length - 1}
            className="absolute right-4 z-10 p-2 rounded-full bg-accent[0.04] border border-border[0.06] text-white/30 hover:bg-accent[0.08] hover:text-white/60 disabled:opacity-0 transition-all duration-200"
          >
            <ChevronRight className="w-5 h-5" />
          </button>

          {/* Slide with directional animation */}
          <div className="px-16 py-8 w-full flex items-center justify-center relative z-[1]">
            <div
              key={slideKey}
              className={`w-full max-w-4xl ${animClass}`}
              style={{
                filter: 'drop-shadow(0 20px 40px rgba(0,0,0,0.4)) drop-shadow(0 4px 12px rgba(0,0,0,0.3))',
              }}
            >
              <SlideRenderer
                slide={activeSlide}
                theme={theme}
                slideIndex={clampedIndex}
                totalSlides={slides.length}
                imageBaseUrl={imageBaseUrl}
                availableImageIds={availableImageIds}
                onEditHtml={activeSlide.html ? () => setShowHtmlEditor(true) : undefined}
              />
            </div>
          </div>
        </div>

        {/* Right: Edit Panel */}
        <SlideEditPanel
          artifactId={activeArtifact.id}
          activeSlide={activeSlide}
          slideIndex={clampedIndex}
          revisionHeadId={activeArtifact.revision_head_id}
          showHtml={showHtmlEditor}
          onToggleHtml={() => setShowHtmlEditor(v => !v)}
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
        onNavigate={(i) => navigateTo(i, i > clampedIndex ? 'right' : 'left')}
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
        className="fixed inset-0 sm:inset-3 max-w-none translate-x-0 translate-y-0 left-0 top-0 flex flex-col bg-[#0d0e11] rounded-none sm:rounded-xl border-0 sm:border sm:border-border[0.06] overflow-hidden p-0 animate-modal-scale-in shadow-sm"
      >
        <SlidePreviewContent key={openCount} />
      </DialogContent>
    </Dialog>
  );
}
