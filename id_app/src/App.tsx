import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import FlowPage from './pages/FlowPage';
import WelcomePage from './pages/WelcomePage';
import SessionExpiredPage from './pages/SessionExpiredPage';
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
              <WelcomePage />
            </FlowInitializationHandler>
          } />
          <Route path="/flow" element={
            <FlowInitializationHandler>
              <FlowPage />
            </FlowInitializationHandler>
          } />
          <Route path="/session-expired" element={<SessionExpiredPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
