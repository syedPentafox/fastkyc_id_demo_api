import React, { useEffect } from 'react';
import { useJourneyStore, FlowActivationData } from '@/lib/store';
import { useFlowActivation } from '@/lib/hooks';

interface Props {
    children: React.ReactNode;
}

export const FlowInitializationHandler: React.FC<Props> = ({ children }) => {
    const { initSession, setFlowData, setError, flowData, error: storeError, token } = useJourneyStore();

    // 1. Extract Token on Mount
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const tkn = params.get('tkn');

        // Only set if we found a token and it's different (or we don't have one)
        // Note: initSession saves to localStorage.
        if (tkn) {
            initSession(tkn);
        } else if (!token && !tkn) {
            // If no token in URL and no token in store/localStorage, we can't proceed.
            // But we might be on a route that doesn't need it? 
            // For now, let's assume this handler guards the flow.
        }
    }, [initSession, token]);

    // 2. Fetch Data (TanStack Query)
    // It will run if token is available.
    const { data, error, isLoading } = useFlowActivation(token);

    // 3. Sync to Store
    useEffect(() => {
        if (data) {
            // Only update if not already set or checks pass
            // We can do a deep check or just simple ID check if we had one.
            // For now, simply set it.
            setFlowData(data as FlowActivationData);
        }
    }, [data, setFlowData]);

    // 4. Handle Errors
    useEffect(() => {
        if (error) {
            const msg = (error as any).response?.data?.message || (error as any).message || 'Failed to activate flow';
            setError(msg);
        }
    }, [error, setError]);

    // Render Logic

    // If we have an error from store, show it (blocking)
    if (storeError) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-red-50">
                <div className="text-center p-6 bg-white rounded-lg shadow-md border border-red-200">
                    <h2 className="text-lg font-bold text-red-600 mb-2">Initialization Error</h2>
                    <p className="text-gray-600">{storeError}</p>
                </div>
            </div>
        );
    }

    // If loading or (token exists but no data yet and no error)
    if (isLoading || (token && !flowData && !error)) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <div className="flex flex-col items-center animate-pulse">
                    <div className="w-12 h-12 bg-blue-100 rounded-full mb-4"></div>
                    <p className="text-gray-500 font-medium">Initializing Flow...</p>
                </div>
            </div>
        );
    }

    // If no token and no data (and verify strictly), maybe show "Missing Token"
    if (!token && !flowData) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <p className="text-gray-400">Waiting for access token...</p>
            </div>
        );
    }

    return <>{children}</>;
};
