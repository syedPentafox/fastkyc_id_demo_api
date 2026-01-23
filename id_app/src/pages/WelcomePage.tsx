import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJourneyStore } from '@/lib/store';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight, Loader2, Sparkles } from 'lucide-react';
import brandLogo from '@/assets/logo.png';

export default function WelcomePage() {
    const navigate = useNavigate();
    const { flowData, setHasStartedJourney, hasStartedJourney } = useJourneyStore();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleStartJourney = async () => {
        try {
            setIsLoading(true);
            setError(null);

            // Just mark as started and navigate. 
            // The FlowPage will fetch the initial state automatically.
            setHasStartedJourney(true);

            console.log("Journey Started, navigating to flow...");
            navigate('/flow');
        } catch (err: any) {
            setError(err.message || 'Failed to start journey');
            setIsLoading(false);
        }
    };

    // If journey already started, redirect to flow (in useEffect to avoid setState during render)
    useEffect(() => {
        if (hasStartedJourney) {
            navigate('/flow', { replace: true });
        }
    }, [hasStartedJourney, navigate]);

    if (!flowData) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <div className="animate-pulse text-gray-400">Loading flow information...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background flex items-center justify-center p-4 font-sans">
            <Card className="max-w-2xl w-full shadow-2xl border-0 bg-card/80 backdrop-blur-sm">
                <CardContent className="pt-12 pb-12 px-8">

                    {/* Flow Name */}
                    <h1 className="text-3xl font-extrabold tracking-wide text-center text-secondary-foreground/80 mb-4 tracking-tight">
                        {flowData.flow_details.name}
                    </h1>

                    {/* Flow Description */}
                    <p className="text-secondary-foreground text-center text-md mb-8 leading-relaxed">
                        {flowData.flow_details.description}
                    </p>

                    {/* Customer Info */}
                    {flowData.end_customer && (
                        <div className="bg-accent rounded-lg p-4 mb-8 border border-border">
                            <p className="text-center text-foreground">
                                Welcome, <span className="font-bold text-primary">{flowData.end_customer.name}</span>
                            </p>
                            {flowData.end_customer.phone && (
                                <p className="text-center text-sm text-gray-500 mt-1">
                                    {flowData.end_customer.phone}
                                </p>
                            )}
                        </div>
                    )}

                    {/* Journey Steps Preview */}
                    <div className="mb-8">
                        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 text-center">
                            Your Journey
                        </h2>
                        <div className="space-y-2">
                            {flowData.steps.map((step, index) => (
                                <div
                                    key={step.step_number}
                                    className="flex items-center gap-3 p-3 bg-accent/50 rounded-lg border border-border hover:border-primary/50 transition-colors"
                                >
                                    <div className="w-8 h-8 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-bold shrink-0">
                                        {index + 1}
                                    </div>
                                    <div className="flex-1">
                                        <p className="font-semibold text-foreground">{step.name}</p>
                                        <p className="text-xs text-muted-foreground">{step.description}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="mb-6 p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20 text-center">
                            {error}
                        </div>
                    )}

                    {/* Start Button */}
                    <Button
                        onClick={handleStartJourney}
                        disabled={isLoading}
                        className="w-full h-14 text-lg font-bold bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                                Starting Journey...
                            </>
                        ) : (
                            <>
                                Start Journey
                                <ArrowRight className="w-5 h-5 ml-2" />
                            </>
                        )}
                    </Button>

                    {/* Footer Note */}
                    <p className="text-center text-xs text-gray-400 mt-6">
                        Click the button above to begin your verification journey
                    </p>
                    <div className="flex justify-center items-center text-sm gap-2 mt-6">
                        <span>Powered by</span>
                        <img src={brandLogo} alt="FastKYC" className='h-6' />
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
