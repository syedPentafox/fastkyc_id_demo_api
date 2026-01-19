import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import FlowPage from './pages/FlowPage';
import LandingPage from './pages/LandingPage';
import { FlowInitializationHandler } from './components/FlowInitializationHandler';
import './index.css';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={
            <FlowInitializationHandler>
              <LandingPage />
            </FlowInitializationHandler>
          } />
          <Route path="/flow" element={
            <FlowInitializationHandler>
              <FlowPage />
            </FlowInitializationHandler>
          } />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
