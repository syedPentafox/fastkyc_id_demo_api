import { FC, useEffect, useState } from 'react';
import { useJourneyStore } from '@/lib/store';
import brandLogo from '@/assets/logo.png';
import { Clock } from 'lucide-react';

interface BrandHeaderProps {
    logo?: string;
    companyName?: string;
}

export const BrandHeader: FC<BrandHeaderProps> = ({ logo = brandLogo, companyName }) => {
    const { flowData } = useJourneyStore();
    const [timeLeft, setTimeLeft] = useState<string | null>(null);
    const [isExpired, setIsExpired] = useState(false);

    // Use flow name as fallback if no company name provided
    const displayName = companyName || flowData?.flow_details?.name || 'Verification Platform';

    // Timer Logic
    useEffect(() => {
        if (!flowData?.expires_at) return;

        const calculateTimeLeft = () => {
            const now = new Date().getTime();
            const expiresAt = new Date(flowData.expires_at).getTime();
            const distance = expiresAt - now;

            if (distance < 0) {
                setIsExpired(true);
                setTimeLeft("00:00");
                return;
            }

            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            setTimeLeft(`${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`);
        };

        calculateTimeLeft(); // Initial call
        const timer = setInterval(calculateTimeLeft, 1000);

        return () => clearInterval(timer);
    }, [flowData?.expires_at]);

    return (
        <header className="w-full bg-card border-b border-border sticky top-0 z-50 shadow-sm">
            <div className="max-w-7xl mx-auto px-4 py-3 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between">
                    {/* Logo and Company Name */}
                    <div className="flex items-center gap-3">
                        {logo ? (
                            <img
                                src={logo}
                                alt={displayName}
                                className="h-8 w-auto object-contain"
                            />
                        )
                            : (
                                <div className="h-9 w-9 rounded-lg bg-primary flex items-center justify-center shadow-sm">
                                    <span className="text-primary-foreground font-bold text-lg">
                                        {displayName.charAt(0).toUpperCase()}
                                    </span>
                                </div>
                            )
                        }
                    </div>

                    {/* Right Side: User Info & Timer */}
                    <div className="flex items-center gap-4">
                        {/* Session Timer */}
                        {timeLeft && (
                            <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold shadow-sm transition-colors ${isExpired
                                    ? "bg-destructive/10 text-destructive border-destructive/20"
                                    : "bg-primary/5 text-primary border-primary/20"
                                }`}>
                                <Clock className="w-3.5 h-3.5" />
                                <span className="tabular-nums">{isExpired ? "Session Expired" : timeLeft}</span>
                            </div>
                        )}

                        {/* Secure Session Indicator */}
                        <div className="hidden sm:flex items-center gap-2 text-sm text-muted-foreground border-l border-border pl-4">
                            {flowData?.end_customer ? (
                                <p className="text-xs font-medium">
                                    {flowData.end_customer.name}
                                </p>
                            ) : (
                                <div className="flex items-center gap-1.5">
                                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                    <span className="text-xs">Secure</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
};
