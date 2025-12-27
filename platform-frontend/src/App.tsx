import { AppLayout } from '@/components/layout/AppLayout';
import { ThemeProvider } from '@/components/theme';

function App() {
  return (
    <ThemeProvider defaultTheme="dark">
      <AppLayout />
    </ThemeProvider>
  );
}

export default App;
