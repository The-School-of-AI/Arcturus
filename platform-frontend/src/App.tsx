import { AppLayout } from '@/components/layout/AppLayout';

function App() {
  return (
    <div className="dark">
      {/* Force dark mode class for now since our theme relies on it */}
      <AppLayout />
    </div>
  );
}

export default App;
