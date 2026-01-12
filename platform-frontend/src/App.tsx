import { AppLayout } from '@/components/layout/AppLayout';
import { ThemeProvider } from '@/components/theme';
import { TooltipProvider } from '@/components/ui/tooltip';

function App() {
  return (
    <ThemeProvider defaultTheme="dark">
      <TooltipProvider>
        <AppLayout />
      </TooltipProvider>
    </ThemeProvider>
  );
}

export default App;
