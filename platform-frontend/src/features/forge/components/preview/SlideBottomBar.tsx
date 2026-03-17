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
    const ext = job.format || 'pdf';
    const defaultName = `${artifactTitle || 'slides'}.${ext}`;
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

  const handleExport = (format: 'pdf' | 'pptx' = 'pdf') => {
    startExport(artifactId, format, selectedThemeId, format === 'pptx' ? (strictLayout || undefined) : undefined, format === 'pptx' ? (generateImages || undefined) : undefined);
    setShowExportOptions(false);
  };

  const selectedTheme = themes.find((t: { id: string }) => t.id === selectedThemeId);

  return (
    <div className="h-12 border-t border-white/[0.06] bg-[#0a0b0d] flex items-center px-4 gap-3 shrink-0">
      {/* Theme selector */}
      <div className="relative">
        <button
          onClick={() => { setShowThemeDropdown(v => !v); setShowExportOptions(false); }}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs text-white/50 hover:text-white/80 hover:bg-white/[0.04] transition-colors"
        >
          <Palette className="w-3.5 h-3.5" />
          {selectedTheme && (
            <div className="flex items-center gap-0.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: selectedTheme.colors?.primary }} />
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: selectedTheme.colors?.accent }} />
            </div>
          )}
          <span className="max-w-[100px] truncate">{selectedTheme?.name || selectedThemeId}</span>
        </button>

        {showThemeDropdown && (
          <div className="absolute bottom-full left-0 mb-2 w-60 max-h-72 overflow-y-auto rounded-xl border border-white/[0.08] bg-[#111215] shadow-2xl z-50">
            {themes.map((t: { id: string; name: string; colors?: { primary: string; accent: string; background: string } }) => (
              <button
                key={t.id}
                onClick={() => { onThemeChange(t.id); setShowThemeDropdown(false); }}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2.5 text-left text-xs hover:bg-white/[0.04] transition-colors',
                  t.id === selectedThemeId && 'bg-blue-500/10 text-blue-400'
                )}
              >
                <div className="flex items-center gap-0.5 shrink-0">
                  {[t.colors?.primary, t.colors?.accent, t.colors?.background].filter(Boolean).map((c, ci) => (
                    <div key={ci} className="w-3 h-3 rounded-full border border-white/10" style={{ backgroundColor: c }} />
                  ))}
                </div>
                <span className={cn('truncate', t.id === selectedThemeId ? 'text-blue-400' : 'text-white/60')}>{t.name}</span>
              </button>
            ))}
            {themes.length === 0 && (
              <div className="p-3 text-xs text-white/30 flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" /> Loading themes...
              </div>
            )}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Navigation */}
      <div className="flex items-center gap-1.5">
        <button
          className="p-1.5 rounded-md text-white/30 hover:text-white/70 hover:bg-white/[0.04] disabled:opacity-30 transition-colors"
          disabled={currentIndex === 0}
          onClick={() => onNavigate(currentIndex - 1)}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-xs text-white/40 font-mono min-w-[50px] text-center tabular-nums">
          {currentIndex + 1} / {totalSlides}
        </span>
        <button
          className="p-1.5 rounded-md text-white/30 hover:text-white/70 hover:bg-white/[0.04] disabled:opacity-30 transition-colors"
          disabled={currentIndex >= totalSlides - 1}
          onClick={() => onNavigate(currentIndex + 1)}
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Export */}
      <div className="relative flex items-center gap-1.5">
        <button
          onClick={() => { setShowExportOptions(v => !v); setShowThemeDropdown(false); }}
          className="p-1.5 rounded-md text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
        </button>

        {showExportOptions && (
          <div className="absolute bottom-full right-0 mb-2 p-3 rounded-xl border border-white/[0.08] bg-[#111215] shadow-2xl z-50 space-y-2.5 w-52">
            <button
              onClick={() => handleExport('pptx')}
              disabled={isExporting}
              className="w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-xs text-white/60 hover:text-white hover:bg-white/[0.06] transition-colors disabled:opacity-40"
            >
              <Download className="w-3 h-3" />
              Export as PPTX
            </button>
            <div className="border-t border-white/[0.06] pt-2 space-y-2">
              <label className="flex items-center gap-2 text-xs text-white/50 cursor-pointer">
                <Switch checked={strictLayout} onCheckedChange={setStrictLayout} />
                Strict layout (PPTX)
              </label>
              <label className="flex items-center gap-2 text-xs text-white/50 cursor-pointer">
                <Switch checked={generateImages} onCheckedChange={setGenerateImages} />
                Generate images (PPTX)
              </label>
            </div>
          </div>
        )}

        <Button
          size="sm"
          onClick={() => handleExport('pdf')}
          disabled={isExporting}
          className="h-8 text-xs gap-1.5 bg-blue-600 hover:bg-blue-500 text-white border-0"
        >
          {isExporting ? (
            <><Loader2 className="w-3 h-3 animate-spin" /> Exporting...</>
          ) : (
            <><Download className="w-3 h-3" /> Export PDF</>
          )}
        </Button>
      </div>
    </div>
  );
}
