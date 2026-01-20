import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJourneyStore, useTokenStore, FlowActivationData } from '@/lib/store';
import { useFlowActivation } from '@/lib/hooks';

interface Props {
    children: React.ReactNode;
}

export const FlowInitializationHandler: React.FC<Props> = ({ children }) => {
    const navigate = useNavigate();
    const { initSession, token } = useTokenStore();
    const { setFlowData, setError, flowData, error: storeError } = useJourneyStore();

    // 1. Extract Token on Mount
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const tkn = params.get('tkn');

        // Only set if we found a token and it's different
        if (tkn && tkn !== token) {
            initSession(tkn);
        }
    }, [initSession, token]);

    // 2. Fetch Data (TanStack Query) - only if we don't have flowData in sessionStorage
    const shouldFetch = !!token && !flowData;
    const { data, error, isLoading } = useFlowActivation(shouldFetch);

    // 3. Sync to Store
    useEffect(() => {
        if (data && !flowData) {
            setFlowData(data as FlowActivationData);
        }
    }, [data, flowData, setFlowData]);

    // 4. Handle Errors
    useEffect(() => {
        if (error) {
            const msg = (error as any).response?.data?.message || (error as any).message || 'Failed to activate flow';
            setError(msg);
        }
    }, [error, setError]);

    // 5. Check Expiration
    useEffect(() => {
        if (flowData?.expires_at) {
            const checkExpiry = () => {
                const expiresAt = new Date(flowData.expires_at).getTime();
                const now = new Date().getTime();
                if (now > expiresAt) {
                    navigate('/session-expired');
                }
            };

            checkExpiry();
            // Check every minute just in case, though the header timer handles visual feedback
            const interval = setInterval(checkExpiry, 60000);
            return () => clearInterval(interval);
        }
    }, [flowData, navigate]);

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

    // If loading (and we're actually fetching)
    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <div className="flex flex-col items-center animate-pulse">
                    <div className="w-12 h-12 bg-blue-100 rounded-full mb-4"></div>
                    <p className="text-gray-500 font-medium">Initializing Flow...</p>
                </div>
            </div>
        );
    }

    // If no token and no data
    if (!token && !flowData) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <p className="text-gray-400">Waiting for access token...</p>
            </div>
        );
    }

    return <>{children}</>;
};
