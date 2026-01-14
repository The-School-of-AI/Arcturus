import { AppLayout } from '@/components/layout/AppLayout';
import { ThemeProvider } from '@/components/theme';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

function SplashScreen() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <div className="w-16 h-16 mx-auto rounded-full bg-primary/20 flex items-center justify-center animate-pulse">
          <svg className="w-8 h-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-foreground">Arcturus Platform</h2>
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
        await axios.get(`${API_BASE}/runs`, { timeout: 1000 });
        setIsBackendReady(true);
      } catch {
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(checkBackend, 1000);
        } else {
          // Force show UI after 30s even if backend isn't responding
          setIsBackendReady(true);
        }
      }
    };

    checkBackend();
  }, []);

  return (
    <ThemeProvider defaultTheme="dark">
      <TooltipProvider>
        {!isBackendReady && <SplashScreen />}
        <div className={isBackendReady ? 'opacity-100 transition-opacity duration-500' : 'opacity-0'}>
          <AppLayout />
        </div>
      </TooltipProvider>
    </ThemeProvider>
  );
}

export default App;
