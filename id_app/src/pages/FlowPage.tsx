import { useEffect, useState } from 'react';
import { useJourneyStore } from '@/lib/store';
import { DynamicForm } from '@/components/DynamicForm';
import { Stepper } from '@/components/Stepper';
import { Card, CardContent } from '@/components/ui/card';
import { Check, ExternalLink, Loader2 } from 'lucide-react';
import { useSubmitStep, usePolling } from '@/lib/hooks';

export default function FlowPage() {
    const { flowData, addCollectedData, collectedData } = useJourneyStore();
    const { mutateAsync: submitStep, isPending: isSubmitting } = useSubmitStep();

    const [started, setStarted] = useState(false);
    const [currentStep, setCurrentStep] = useState(1);
    const [currentStepData, setCurrentStepData] = useState<any>(null);
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
        if (flowData && !started && !currentStepData) {
            submitStep({})
                .then((data) => {
                    setCurrentStepData(data);
                    setStarted(true);
                })
                .catch((err) => {
                    setLocalError(err.message || "Failed to start");
                });
        }
    }, [flowData, started, currentStepData, submitStep]);

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
                // Stop polling and move to next step automatically
                setIsPolling(false);
                setPollingInfo(null);
                setPopupWindow(null); // Clear popup reference

                // Automatically trigger next step without user interaction
                const autoSubmit = async () => {
                    try {
                        const payload = await submitStep({});
                        if (payload.action === 'REDIRECT') {
                            window.location.href = payload.url;
                            return;
                        }
                        setCurrentStepData(payload);
                        setCurrentStep(prev => prev + 1);
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

    const handleStepSubmit = async (data: any) => {
        try {
            // Save form data before submitting
            if (currentStepData && Object.keys(data).length > 0) {
                addCollectedData({
                    stepNumber: currentStep,
                    featureName: currentStepData.title || currentStepData.feature_name || `Step ${currentStep}`,
                    data: data,
                });
            }

            const payload = await submitStep(data);

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
            setLocalError(err.message || "Something went wrong sending step.");
        }
    };

    if (!flowData) return null;

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-4 font-sans text-gray-900">
            <div className="max-w-4xl mx-auto pt-8">
                {/* Header */}
                <div className="mb-8 text-center">
                    <h1 className="text-4xl font-extrabold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent tracking-tight">
                        {flowData.flow_details.name}
                    </h1>
                    <p className="text-gray-600 mt-3 text-lg">{flowData.flow_details.description}</p>
                    {flowData.end_customer && (
                        <p className="text-sm text-gray-500 mt-2">
                            Welcome, <span className="font-semibold text-indigo-600">{flowData.end_customer.name}</span>
                        </p>
                    )}
                </div>

                <Stepper steps={flowData.steps} currentStep={currentStep} />

                {localError && (
                    <div className="max-w-md mx-auto mb-4 p-4 bg-red-50 text-red-700 rounded-lg shadow-sm border border-red-200">
                        {localError}
                    </div>
                )}

                <div className="transition-all duration-500 ease-in-out">
                    {!currentStepData && started && !localError && (
                        <div className="text-center py-10">
                            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                            <p className="text-gray-400 mt-4">Loading Step...</p>
                        </div>
                    )}

                    {currentStepData && currentStepData.action === 'NEXT_FORM' && (
                        <DynamicForm
                            featureName={currentStepData.title || currentStepData.feature_name}
                            fields={currentStepData.form_fields}
                            onSubmit={handleStepSubmit}
                            isLoading={isSubmitting}
                        />
                    )}

                    {currentStepData && currentStepData.action === 'POLLING' && (
                        <Card className="max-w-md mx-auto mt-6 text-center shadow-xl border-blue-100 bg-gradient-to-br from-blue-50 to-indigo-50">
                            <CardContent className="pt-8 pb-8">
                                <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-indigo-500 text-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg relative">
                                    <Loader2 className="w-8 h-8 animate-spin" />
                                    <div className="absolute inset-0 rounded-full bg-blue-400 opacity-20 animate-ping" />
                                </div>
                                <h2 className="text-2xl font-bold text-blue-700 mb-2">Verification in Progress</h2>
                                <p className="text-gray-600 mb-4">
                                    Please complete the verification in the opened window.
                                </p>
                                <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                                    <ExternalLink className="w-4 h-4" />
                                    <span>Waiting for verification...</span>
                                </div>
                                <div className="mt-4 text-xs text-gray-400">
                                    This page will automatically continue once verification is complete
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {currentStepData && currentStepData.action === 'STEP_COMPLETE' && (
                        <Card className="max-w-md mx-auto mt-6 text-center shadow-xl border-green-100 bg-gradient-to-br from-green-50 to-emerald-50">
                            <CardContent className="pt-8 pb-8">
                                <div className="w-16 h-16 bg-gradient-to-br from-green-400 to-emerald-500 text-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg">
                                    <Check className="w-8 h-8" />
                                </div>
                                <h2 className="text-2xl font-bold text-green-700 mb-2">Success!</h2>
                                <p className="text-gray-600">{currentStepData.message}</p>

                                <button
                                    onClick={async () => {
                                        await handleStepSubmit({});
                                        setCurrentStep(prev => prev + 1);
                                    }}
                                    className="mt-6 px-8 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold rounded-full transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-105"
                                >
                                    Continue to Next Step
                                </button>
                            </CardContent>
                        </Card>
                    )}

                    {currentStepData && currentStepData.action === 'JOURNEY_COMPLETE' && (
                        <div className="max-w-3xl mx-auto mt-6 space-y-6">
                            <Card className="text-center shadow-xl border-green-100 bg-gradient-to-br from-green-50 to-emerald-50">
                                <CardContent className="pt-8 pb-8">
                                    <div className="w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 text-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg">
                                        <Check className="w-10 h-10" />
                                    </div>
                                    <h2 className="text-3xl font-bold text-green-700 mb-2">Journey Complete!</h2>
                                    <p className="text-gray-600 text-lg">{currentStepData.message}</p>
                                </CardContent>
                            </Card>

                            {collectedData.length > 0 && (
                                <Card className="shadow-xl border-indigo-100 bg-white">
                                    <CardContent className="pt-6 pb-6">
                                        <h3 className="text-xl font-bold text-indigo-900 mb-4 flex items-center gap-2">
                                            <span className="w-2 h-2 bg-indigo-600 rounded-full"></span>
                                            Collected Data Summary
                                        </h3>
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                            <pre className="text-sm text-gray-700 overflow-x-auto whitespace-pre-wrap">
                                                {JSON.stringify(collectedData, null, 2)}
                                            </pre>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
