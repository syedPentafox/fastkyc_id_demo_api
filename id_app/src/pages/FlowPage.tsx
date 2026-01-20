import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJourneyStore } from '@/lib/store';
import { DynamicForm } from '@/components/DynamicForm';
import { Stepper } from '@/components/Stepper';
import { BrandHeader } from '@/components/BrandHeader';
import { JourneyOverview } from '@/components/JourneyOverview';
import { Card, CardContent } from '@/components/ui/card';
import { AlertCircle, Check, ExternalLink, Loader2, XIcon } from 'lucide-react';
import { useSubmitStep, usePolling } from '@/lib/hooks';

export default function FlowPage() {
    const navigate = useNavigate();
    const {
        flowData,
        addCollectedData,
        collectedData,
        hasStartedJourney,
        currentStepData,
        setCurrentStepData,
        currentStepNumber,
        setCurrentStepNumber,
        setHasStartedJourney
    } = useJourneyStore();
    const { mutateAsync: submitStep, isPending: isSubmitting } = useSubmitStep();

    const [localError, setLocalError] = useState<string | null>(null);

    // Polling state for redirect flows
    const [pollingInfo, setPollingInfo] = useState<{ clientId: string; featureId: number } | null>(null);
    const [isPolling, setIsPolling] = useState(false);
    const [popupWindow, setPopupWindow] = useState<Window | null>(null);

    // Use polling hook
    const { data: pollData, error: pollError } = usePolling(
        pollingInfo?.clientId || null,
        pollingInfo?.featureId || null,
        isPolling
    );
    useEffect(() => {
        if (!hasStartedJourney) {
            navigate('/', { replace: true });
        } else if (!currentStepData && !localError && !isSubmitting) {
            // go back if something fails
            setHasStartedJourney(false);
            navigate('/', { replace: true });
        }
    }, [hasStartedJourney, currentStepData, localError, isSubmitting, navigate, setHasStartedJourney]);

    // Monitor popup window close
    useEffect(() => {
        if (!popupWindow || !isPolling) return;

        const checkWindowClosed = setInterval(() => {
            if (popupWindow.closed) {
                // Window was closed without completion
                setIsPolling(false);
                setPollingInfo(null);
                setPopupWindow(null);
                setLocalError('Verification window was closed. Please try again.');
                clearInterval(checkWindowClosed);
            }
        }, 1000); // Check every second

        return () => clearInterval(checkWindowClosed);
    }, [popupWindow, isPolling]);

    // Handle polling results
    useEffect(() => {
        if (pollData && isPolling) {
            const status = pollData.status;
            if (pollData.data.is_completed) {
                // Stop polling
                setIsPolling(false);
                setPollingInfo(null);
                setPopupWindow(null);

                // Save Polling Success Data
                addCollectedData({
                    stepNumber: currentStepNumber,
                    featureName: currentStepData?.title || currentStepData?.feature_name || `Step ${currentStepNumber}`,
                    data: pollData.data
                });

                // Automatically trigger next step without user interaction
                const autoSubmit = async () => {
                    try {
                        const payload = await submitStep({});
                        if (payload.action === 'REDIRECT') {
                            window.location.href = payload.url;
                            return;
                        }
                        setCurrentStepData(payload);
                        setCurrentStepNumber(currentStepNumber + 1);
                    } catch (err: any) {
                        setLocalError(err.message || 'Failed to proceed to next step');
                    }
                };
                autoSubmit();
            } else if (pollData.data.is_failed || status === 'FAILED' || status === 'failed') {
                setIsPolling(false);
                setPollingInfo(null);
                setPopupWindow(null); // Clear popup reference
                setLocalError(pollData.message || 'Verification failed');
            }
        }
    }, [pollData, isPolling, submitStep]);

    // Handle polling errors
    useEffect(() => {
        if (pollError && isPolling) {
            setLocalError('Polling failed. Please try again.');
            setIsPolling(false);
            setPollingInfo(null);
            setPopupWindow(null); // Clear popup reference
        }
    }, [pollError, isPolling]);

    // Auto-advance for STEP_COMPLETE
    console.log("Current step data:", currentStepData);
    useEffect(() => {
        if (currentStepData && currentStepData.action === 'STEP_COMPLETE') {
            const timer = setTimeout(async () => {
                await handleStepSubmit({});
                setCurrentStepNumber(currentStepNumber + 1);
            }, 1500); // 1.5s delay to show success message

            return () => clearTimeout(timer);
        }
    }, [currentStepData]);

    // RAIPD API EXECUTION: Auto-advance if NEXT_FORM has no fields
    useEffect(() => {
        if (currentStepData && currentStepData.action === 'NEXT_FORM') {
            const fields = currentStepData.form_fields || [];
            if (fields.length === 0 && !isSubmitting && !localError) {
                // Auto-submit empty forms (Rapid Execution)
                console.log("Auto-advancing rapid API step...");
                handleStepSubmit({});
            }
        }
    }, [currentStepData, isSubmitting, localError]);

    const handleStepSubmit = async (data: any) => {
        setLocalError(null);
        try {
            const payload = await submitStep(data);

            // Save RESPONSE data for non-redirect flows
            if (payload.action !== 'REDIRECT') {
                // Filter out UI config to keep data clean
                const { form_fields, action, poll_info, ...responseData } = payload;

                addCollectedData({
                    stepNumber: currentStepNumber,
                    featureName: currentStepData?.title || currentStepData?.feature_name || `Step ${currentStepNumber}`,
                    data: responseData
                });
            }

            if (payload.action === 'REDIRECT') {
                // Open redirect URL in new window and store reference
                const redirectUrl = payload.url;
                let popup: Window | null = null;

                if (redirectUrl) {
                    popup = window.open(redirectUrl, '_blank', 'noopener,noreferrer');
                    setPopupWindow(popup);
                }

                // Start polling if we have poll_info
                if (payload.poll_info && payload.poll_info.client_id && payload.poll_info.api_id) {
                    setPollingInfo({
                        clientId: payload.poll_info.client_id,
                        featureId: payload.poll_info.api_id
                    });
                    setIsPolling(true);
                    // Update UI to show polling state
                    setCurrentStepData({
                        ...payload,
                        action: 'POLLING'
                    });
                }
                return;
            }

            setCurrentStepData(payload);
        } catch (err: any) {
            console.error("Error submitting step:", err);
            setLocalError(err.response?.data?.message || err.message || "Something went wrong sending step.");
        }
    };

    if (!flowData) return null;

    const isJourneyComplete = currentStepData?.action === 'JOURNEY_COMPLETE';

    // Create display steps including the virtual "Overview" step
    const displaySteps = [
        ...flowData.steps,
        {
            step_number: flowData.steps.length + 1,
            name: 'Overview',
            description: 'Journey Summary',
            action: 'OVERVIEW'
        }
    ];

    // If journey is complete, we are on the Overview step (last step)
    // Otherwise we are on the currentStepNumber
    const stepperCurrentStep = isJourneyComplete ? displaySteps.length : currentStepNumber;

    return (
        <div className="min-h-screen bg-background">
            {/* Brand Header */}
            <BrandHeader />

            {/* Main Content */}
            <div className="max-w-5xl mx-auto px-4 py-8">

                {/* Stepper - Always visible */}
                <Stepper
                    steps={displaySteps as any}
                    currentStep={stepperCurrentStep}
                    isJourneyComplete={isJourneyComplete}
                />

                {/* Error Display */}
                {localError && (
                    <div className="relative max-w-2xl mx-auto mb-6 p-4 bg-destructive/10 text-destructive rounded-xl shadow-sm border border-destructive/20 animate-in fade-in slide-in-from-top-2 duration-300">
                        <div className="flex items-center gap-2">
                            <span className="text-lg"><AlertCircle className="w-5 h-5" /></span>
                            <span>{localError}</span>
                        </div>
                        <div className="absolute top-1 right-1 flex items-center gap-2">
                            <button
                                onClick={() => setLocalError(null)}
                                className="text-sm text-destructive hover:underline bg-destructive/80 rounded-full p-1"
                            >
                                <XIcon className="w-3 h-3 text-white" />
                            </button>
                        </div>
                    </div>
                )}

                {/* Content Area - Centered */}
                <div className="flex items-center justify-center min-h-[400px] transition-all duration-500 ease-in-out">
                    {!currentStepData && !localError && (
                        <div className="text-center py-16 animate-in fade-in duration-500">
                            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-muted border-t-primary mb-4"></div>
                            <p className="text-muted-foreground font-medium">Loading your next step...</p>
                        </div>
                    )}

                    {currentStepData && currentStepData.action === 'NEXT_FORM' && (
                        <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <DynamicForm
                                featureName={currentStepData.title || currentStepData.feature_name}
                                fields={currentStepData.form_fields}
                                onSubmit={handleStepSubmit}
                                isLoading={isSubmitting}
                            />
                        </div>
                    )}

                    {currentStepData && currentStepData.action === 'POLLING' && (
                        <Card className="max-w-lg mx-auto text-center shadow-2xl border-0 bg-card/90 backdrop-blur animate-in fade-in zoom-in-95 duration-500">
                            <CardContent className="pt-12 pb-12">
                                <div className="w-20 h-20 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl relative">
                                    <Loader2 className="w-10 h-10 animate-spin" />
                                    <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" />
                                </div>
                                <h2 className="text-3xl font-bold text-foreground mb-3">Verification in Progress</h2>
                                <p className="text-muted-foreground mb-6 text-lg">
                                    Please complete the verification in the opened window.
                                </p>
                                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground bg-accent rounded-full px-4 py-2 inline-flex">
                                    <ExternalLink className="w-4 h-4" />
                                    <span>Waiting for verification...</span>
                                </div>
                                <div className="mt-6 text-xs text-muted-foreground">
                                    ✨ This page will automatically continue once complete
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {currentStepData && currentStepData.action === 'STEP_COMPLETE' && (
                        <Card className="max-w-lg mx-auto text-center shadow-2xl border-0 bg-white/90 backdrop-blur animate-in fade-in zoom-in-95 duration-500">
                            <CardContent className="pt-12 pb-12">
                                <div className="w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 text-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl animate-bounce">
                                    <Check className="w-10 h-10" strokeWidth={3} />
                                </div>
                                <h2 className="text-3xl font-bold text-green-700 mb-3">Success!</h2>
                                <p className="text-gray-600 mb-6 text-lg">{currentStepData.message}</p>
                                <div className="flex items-center justify-center gap-2 text-sm text-indigo-600 bg-indigo-50 rounded-full px-4 py-2 inline-flex">
                                    <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse"></div>
                                    <span className="font-medium">Continuing to next step...</span>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {currentStepData && currentStepData.action === 'JOURNEY_COMPLETE' && (
                        <div className="w-full">
                            <JourneyOverview
                                steps={flowData.steps}
                                collectedData={collectedData}
                                onFinish={() => {
                                    setHasStartedJourney(false);
                                    navigate('/', { replace: true });
                                }}
                            />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
