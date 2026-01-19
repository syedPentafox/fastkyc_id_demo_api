import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJourneyStore } from '@/lib/store';

export default function LandingPage() {
    const navigate = useNavigate();
    const { flowData } = useJourneyStore();

    useEffect(() => {
        if (flowData) {
            navigate('/flow', { replace: true });
        }
    }, [flowData, navigate]);

    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-50">
            <div className="flex flex-col items-center animate-pulse">
                {/* Visual placeholder while waiting for redirect */}
            </div>
        </div>
    );
}
