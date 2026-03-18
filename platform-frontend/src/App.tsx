import { AppLayout } from '@/components/layout/AppLayout';
import { ThemeProvider } from '@/components/theme';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { ArcturusLogo } from '@/components/common/ArcturusLogo';
import { useAppStore } from './store';
import { FeatureFlagsProvider } from '@/hooks/useFeatureFlags';

const API_BASE = 'http://localhost:8000';

function SplashScreen() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
      <div className="text-center space-y-6">
        <div className="w-16 h-16 mx-auto flex items-center justify-center">
          <ArcturusLogo className="w-10 h-10" />
        </div>
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground">Arcturus</h2>
          <div className="flex items-center justify-center gap-2">
            <div className="w-4 h-4 border-2 border-muted-foreground/20 border-t-primary rounded-full animate-spinner" />
            <p className="text-sm text-muted-foreground">Initializing...</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [isBackendReady, setIsBackendReady] = useState(false);

  useEffect(() => {
    let attempts = 0;
    const maxAttempts = 30; // 30 seconds max

    const checkBackend = async () => {
      try {
        console.log(`[App] Checking backend health... (Attempt ${attempts + 1}/${maxAttempts})`);
        const res = await axios.get(`${API_BASE}/health`, { timeout: 2000 });
        if (res.data.status === 'ok') {
          console.log('[App] Backend is healthy and ready.');
          // Small extra delay to ensure everything is really settled
          setTimeout(() => setIsBackendReady(true), 500);
        } else {
          throw new Error('Backend responded but is not ready');
        }
      } catch (err) {
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(checkBackend, 1000);
        } else {
          console.error('[App] Backend check failed after max attempts. Forcing ready state.');
          setIsBackendReady(true);
        }
      }
    };

    checkBackend();
  }, []);

  // Initialize Auth after backend is ready
  useEffect(() => {
    if (isBackendReady) {
      useAppStore.getState().initAuth();
    }
  }, [isBackendReady]);

  return (
    <ThemeProvider defaultTheme="dark">
      <TooltipProvider>
        {!isBackendReady ? (
          <SplashScreen />
        ) : (
          <FeatureFlagsProvider>
            <AppLayout />
          </FeatureFlagsProvider>
        )}
      </TooltipProvider>
    </ThemeProvider>
  );
}

export default App;
