import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Download, Loader2, Palette, Settings2 } from 'lucide-react';
import { useAppStore } from '@/store';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

interface SlideBottomBarProps {
  artifactId: string;
  artifactTitle: string;
  currentIndex: number;
  totalSlides: number;
  selectedThemeId: string;
  onThemeChange: (themeId: string) => void;
  onNavigate: (index: number) => void;
}

export function SlideBottomBar({
  artifactId,
  artifactTitle,
  currentIndex,
  totalSlides,
  selectedThemeId,
  onThemeChange,
  onNavigate,
}: SlideBottomBarProps) {
  const themes = useAppStore(s => s.studioThemes);
  const fetchThemes = useAppStore(s => s.fetchThemes);
  const isExporting = useAppStore(s => s.isExporting);
  const startExport = useAppStore(s => s.startExport);
  const exportJobs = useAppStore(s => s.exportJobs);
  const autoDownloadJobId = useAppStore(s => s.autoDownloadJobId);
  const clearAutoDownload = useAppStore(s => s.clearAutoDownload);

  const [showThemeDropdown, setShowThemeDropdown] = useState(false);
  const [showExportOptions, setShowExportOptions] = useState(false);
  const [strictLayout, setStrictLayout] = useState(false);
  const [generateImages, setGenerateImages] = useState(true);

  // Fetch themes on mount
  useEffect(() => {
    fetchThemes();
  }, [fetchThemes]);

  // Auto-download: trigger save dialog when export completes.
  // Uses getState() to avoid double-fire when ExportPanel also handles this.
  useEffect(() => {
    if (!autoDownloadJobId) return;
    if (autoDownloadJobId.artifactId !== artifactId) return;
    const job = exportJobs.find((j: { id: string; status: string }) => j.id === autoDownloadJobId.jobId && j.status === 'completed');
    if (job) {
      if (!useAppStore.getState().autoDownloadJobId) return;
      clearAutoDownload();
      handleDownload(job);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoDownloadJobId, exportJobs, artifactId]);

  const handleDownload = async (job: { id: string; format?: string }) => {
    const url = api.getExportDownloadUrl(artifactId, job.id);
    const defaultName = `${artifactTitle || 'slides'}.pptx`;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const electronAPI = (window as any).electronAPI;
      if (electronAPI) {
        const result = await electronAPI.invoke('dialog:saveAndOpen', { url, defaultName });
        if (!result?.success && !result?.canceled) {
          console.error('Save failed:', result?.error);
        }
        return;
      }
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Download failed with HTTP ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = defaultName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const handleExport = () => {
    startExport(artifactId, 'pptx', selectedThemeId, strictLayout || undefined, generateImages || undefined);
    setShowExportOptions(false);
  };

  const selectedTheme = themes.find((t: { id: string }) => t.id === selectedThemeId);

  return (
    <div className="h-12 border-t border-border/30 bg-charcoal-950/80 flex items-center px-3 gap-3 shrink-0">
      {/* Theme selector */}
      <div className="relative">
        <button
          onClick={() => { setShowThemeDropdown(v => !v); setShowExportOptions(false); }}
          className="flex items-center gap-2 px-2 py-1 rounded-md text-xs text-foreground hover:bg-muted/30 transition-colors"
        >
          <Palette className="w-3.5 h-3.5 text-muted-foreground" />
          {selectedTheme && (
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full border border-border/40" style={{ backgroundColor: selectedTheme.colors?.primary }} />
              <div className="w-3 h-3 rounded-full border border-border/40" style={{ backgroundColor: selectedTheme.colors?.accent }} />
            </div>
          )}
          <span className="max-w-[120px] truncate">{selectedTheme?.name || selectedThemeId}</span>
        </button>

        {showThemeDropdown && (
          <div className="absolute bottom-full left-0 mb-1 w-64 max-h-72 overflow-y-auto rounded-lg border border-border/50 bg-charcoal-900 shadow-xl z-50">
            {themes.map((t: { id: string; name: string; colors?: { primary: string; accent: string; background: string } }) => (
              <button
                key={t.id}
                onClick={() => { onThemeChange(t.id); setShowThemeDropdown(false); }}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted/30 transition-colors',
                  t.id === selectedThemeId && 'bg-primary/10 text-primary'
                )}
              >
                <div className="flex items-center gap-1 shrink-0">
                  {[t.colors?.primary, t.colors?.accent, t.colors?.background].filter(Boolean).map((c, ci) => (
                    <div key={ci} className="w-3 h-3 rounded-full border border-border/40" style={{ backgroundColor: c }} />
                  ))}
                </div>
                <span className="truncate">{t.name}</span>
              </button>
            ))}
            {themes.length === 0 && (
              <div className="p-3 text-xs text-muted-foreground flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" /> Loading themes...
              </div>
            )}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Navigation */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          disabled={currentIndex === 0}
          onClick={() => onNavigate(currentIndex - 1)}
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <span className="text-xs text-muted-foreground font-mono min-w-[50px] text-center">
          {currentIndex + 1} / {totalSlides}
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          disabled={currentIndex >= totalSlides - 1}
          onClick={() => onNavigate(currentIndex + 1)}
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Export */}
      <div className="relative flex items-center gap-1">
        <button
          onClick={() => { setShowExportOptions(v => !v); setShowThemeDropdown(false); }}
          className="p-1 rounded hover:bg-muted/30 text-muted-foreground hover:text-foreground transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
        </button>

        {showExportOptions && (
          <div className="absolute bottom-full right-0 mb-1 p-3 rounded-lg border border-border/50 bg-charcoal-900 shadow-xl z-50 space-y-2 w-52">
            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <Switch checked={strictLayout} onCheckedChange={setStrictLayout} />
              Strict layout
            </label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <Switch checked={generateImages} onCheckedChange={setGenerateImages} />
              Generate images (AI)
            </label>
          </div>
        )}

        <Button
          size="sm"
          onClick={handleExport}
          disabled={isExporting}
          className="h-7 text-xs gap-1.5"
        >
          {isExporting ? (
            <><Loader2 className="w-3 h-3 animate-spin" /> Exporting...</>
          ) : (
            <><Download className="w-3 h-3" /> Export PPTX</>
          )}
        </Button>
      </div>
    </div>
  );
}
