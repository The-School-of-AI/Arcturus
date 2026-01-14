import { AppLayout } from '@/components/layout/AppLayout';
import { ThemeProvider } from '@/components/theme';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Meteors } from '@/components/ui/meteors';
import { useState, useEffect } from 'react';
import axios from 'axios';
import { ArcturusLogo } from '@/components/common/ArcturusLogo';

const API_BASE = 'http://localhost:8000';

function SplashScreen() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background overflow-hidden">
      {/* Animated meteors background */}
      <div className="absolute inset-0 overflow-hidden">
        <Meteors number={30} />
      </div>

      {/* Content */}
      <div className="text-center space-y-4 relative z-10">
        <div className="w-24 h-24 mx-auto rounded-full bg-primary/10 flex items-center justify-center animate-pulse backdrop-blur-sm border border-primary/20">
          <ArcturusLogo className="w-12 h-12" />
        </div>
        <h2 className="text-2xl font-bold text-foreground">Arcturus Platform</h2>
        <p className="text-sm text-muted-foreground animate-pulse">Initializing backend services...</p>
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

  return (
    <ThemeProvider defaultTheme="dark">
      <TooltipProvider>
        {!isBackendReady ? (
          <SplashScreen />
        ) : (
          <AppLayout />
        )}
      </TooltipProvider>
    </ThemeProvider>
  );
}

export default App;
