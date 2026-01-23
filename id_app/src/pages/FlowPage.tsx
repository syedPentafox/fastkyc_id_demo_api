import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useJourneyStore } from '@/lib/store';
import { useJourneyState, useJourneyNext } from '@/lib/hooks';
import { DynamicForm } from '@/components/DynamicForm';
import { Stepper } from '@/components/Stepper';
import { BrandHeader } from '@/components/BrandHeader';
import { JourneyOverview } from '@/components/JourneyOverview';
import { Card, CardContent } from '@/components/ui/card';
import { AlertCircle, Check, ExternalLink, Loader2, XIcon } from 'lucide-react';
import { FormUI, RedirectUI, PollingUI, MessageUI } from '@/lib/types';

export default function FlowPage() {
    const navigate = useNavigate();
    const {
        flowData,
        hasStartedJourney,
        setHasStartedJourney,
        addCollectedData,
        collectedData
    } = useJourneyStore();

    // Use Query for State
    const {
        data: journeyState,
        isLoading: isStateLoading,
        error: stateError
    } = useJourneyState(hasStartedJourney);

    const { mutate: nextStep, isPending: isSubmitting } = useJourneyNext();

    // Popup state for Redirect
    const [popupWindow, setPopupWindow] = useState<Window | null>(null);

    // Redirect Effect: Open Window if REDIRECT UI
    useEffect(() => {
        if (journeyState?.ui?.type === 'REDIRECT') {
            const ui = journeyState.ui as RedirectUI;
            if (ui.url) {
                const popup = window.open(ui.url, '_blank', 'noopener,noreferrer');
                setPopupWindow(popup);
            }
        }
    }, [journeyState?.ui]);

    // Cleanup popup
    useEffect(() => {
        if (journeyState?.ui?.type !== 'REDIRECT' && popupWindow) {
            // We moved away from redirect state, close popup if needed?
            // Actually, usually we keep it open until user finishes.
            setPopupWindow(null);
        }
    }, [journeyState?.ui, popupWindow]);

    // Safety Checks
    useEffect(() => {
        if (!hasStartedJourney) {
            navigate('/', { replace: true });
        }
    }, [hasStartedJourney, navigate]);

    // Auto-advance empty Forms (Rapid Execution)
    useEffect(() => {
        if (journeyState?.ui?.type === 'FORM') {
            const ui = journeyState.ui as FormUI;
            if (ui.form_fields.length === 0 && !isSubmitting) {
                console.log("Auto-advancing empty form...");
                handleStepSubmit({});
            }
        }
    }, [journeyState, isSubmitting]);


    const handleStepSubmit = (data: any) => {
        nextStep(data, {
            onSuccess: (newState) => {
                // Determine step number for data collection
                // Since newState is the NEXT step, the data belongs to the PREVIOUS step.
                // We use newState.current_step - 1, BUT for transitions (Form -> Form) valid.
                // However, wait: the backend returns 'step_response_data' in the newState
                // which represents the result of the ACTION just performed.

                if (newState.step_response_data) {
                    addCollectedData({
                        stepNumber: journeyState?.current_step || 1, // Use CURRENT state before update
                        featureName: (journeyState?.ui as FormUI)?.title || (journeyState?.ui as any)?.feature_name || 'Step',
                        data: newState.step_response_data
                    });
                } else if (journeyState?.ui?.type === 'FORM') {
                    // Fallback to form input if no backend response data (should not happen if backend aligned)
                    const ui = journeyState.ui as FormUI;
                    addCollectedData({
                        stepNumber: journeyState.current_step,
                        featureName: ui.title || ui.feature_name,
                        data: data
                    });
                }
            }
        });
    };

    if (!flowData) return null;

    // Derived Logic
    const currentStepNumber = journeyState?.current_step || 1;
    const isJourneyComplete = journeyState?.status === 'completed';
    const isPolling = journeyState?.ui?.type === 'POLLING';

    // Steps for Stepper
    // Combine backend steps with local Overview step
    const displaySteps = [
        ...flowData.steps.map(s => ({
            step_number: s.step_number,
            name: s.name,
            description: s.description,
            action: 'STEP'
        })),
        {
            step_number: flowData.steps.length + 1,
            name: 'Overview',
            description: 'Journey Summary',
            action: 'OVERVIEW'
        }
    ];

    const currentUI = journeyState?.ui;

    return (
        <div className="min-h-screen bg-background">
            <BrandHeader />

            <div className="max-w-5xl mx-auto px-4 py-8">
                <Stepper
                    steps={displaySteps}
                    currentStep={isJourneyComplete ? displaySteps.length : currentStepNumber}
                    isJourneyComplete={isJourneyComplete}
                />

                {stateError && (
                    <div className="relative max-w-2xl mx-auto mb-6 p-4 bg-destructive/10 text-destructive rounded-xl shadow-sm border border-destructive/20">
                        <div className="flex items-center gap-2">
                            <span className="text-lg"><AlertCircle className="w-5 h-5" /></span>
                            <span>{(stateError as any).message || "Something went wrong"}</span>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-center min-h-[400px] transition-all duration-500 ease-in-out">

                    {/* LOADING */}
                    {(isStateLoading || !journeyState) && !stateError && (
                        <div className="text-center py-16">
                            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-muted border-t-primary mb-4"></div>
                            <p className="text-muted-foreground font-medium">Loading...</p>
                        </div>
                    )}

                    {/* FORM UI */}
                    {currentUI?.type === 'FORM' && (
                        <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <DynamicForm
                                featureName={(currentUI as FormUI).title || (currentUI as FormUI).feature_name}
                                fields={(currentUI as FormUI).form_fields}
                                onSubmit={handleStepSubmit}
                                isLoading={isSubmitting}
                            />
                        </div>
                    )}

                    {/* REDIRECT UI */}
                    {currentUI?.type === 'REDIRECT' && (
                        <Card className="max-w-lg mx-auto text-center shadow-2xl border-0 bg-card/90 backdrop-blur animate-in fade-in zoom-in-95 duration-500">
                            <CardContent className="pt-12 pb-12">
                                <h2 className="text-2xl font-bold mb-4">Redirecting...</h2>
                                <p className="mb-6">Please complete the process in the new window.</p>
                                <a
                                    href={(currentUI as RedirectUI).url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="px-6 py-2 bg-primary text-primary-foreground rounded-full inline-flex items-center gap-2 hover:opacity-90 transition-opacity"
                                >
                                    <ExternalLink className="w-4 h-4" />
                                    Open Link Again
                                </a>
                                <p className="mt-4 text-sm text-muted-foreground">This page will update automatically.</p>
                            </CardContent>
                        </Card>
                    )}

                    {/* POLLING UI */}
                    {currentUI?.type === 'POLLING' && (
                        <Card className="max-w-lg mx-auto text-center shadow-2xl border-0 bg-card/90 backdrop-blur animate-in fade-in zoom-in-95 duration-500">
                            <CardContent className="pt-12 pb-12">
                                <div className="w-20 h-20 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl relative">
                                    <Loader2 className="w-10 h-10 animate-spin" />
                                    <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" />
                                </div>
                                <h2 className="text-3xl font-bold text-foreground mb-3">Verification in Progress</h2>
                                <p className="text-muted-foreground mb-6 text-lg">
                                    {(currentUI as PollingUI).message}
                                </p>
                            </CardContent>
                        </Card>
                    )}

                    {/* MESSAGE UI (e.g. FAILED or CUSTOM) */}
                    {currentUI?.type === 'MESSAGE' && currentUI.status !== 'COMPLETED' && (
                        <Card className="max-w-lg mx-auto text-center shadow-2xl border-0 bg-white/90 backdrop-blur animate-in fade-in zoom-in-95 duration-500">
                            <CardContent className="pt-12 pb-12">
                                <h2 className="text-xl font-bold text-red-600 mb-2">Notice</h2>
                                <p>{(currentUI as MessageUI).message}</p>
                            </CardContent>
                        </Card>
                    )}

                    {/* COMPLETED / OVERVIEW */}
                    {(currentUI?.type === 'MESSAGE' && currentUI.status === 'COMPLETED' || isJourneyComplete) && (
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
