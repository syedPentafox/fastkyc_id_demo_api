import { FC, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Check, CheckCircle2, Clock, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { Step, CollectedStepData } from '@/lib/store';
import { cn } from '@/lib/utils';

interface JourneyOverviewProps {
    steps: Step[];
    collectedData: CollectedStepData[];
    onFinish: () => void;
}

const StepSummaryItem = ({ step, stepData }: { step: Step, stepData: CollectedStepData | undefined }) => {
    const [isOpen, setIsOpen] = useState(false);
    const hasData = stepData && stepData.data && Object.keys(stepData.data).length > 0;

    return (
        <div className="p-6 hover:bg-muted/20 transition-colors">
            <div className="flex items-start gap-4">
                {/* Status Icon */}
                <div className="shrink-0 mt-1">
                    {stepData ? (
                        <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center text-green-600">
                            <CheckCircle2 className="w-5 h-5" />
                        </div>
                    ) : (
                        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
                            <Clock className="w-5 h-5" />
                        </div>
                    )}
                </div>

                {/* Content */}
                <div className="flex-1 space-y-3">
                    <div className="flex items-center justify-between">
                        <h3 className="font-semibold text-lg text-foreground">
                            {step.name}
                        </h3>
                        <span className={cn(
                            "px-3 py-1 rounded-full text-xs font-medium border",
                            stepData
                                ? "bg-green-50 text-green-700 border-green-200"
                                : "bg-gray-50 text-gray-600 border-gray-200"
                        )}>
                            {stepData ? "Verified" : "Pending"}
                        </span>
                    </div>

                    <p className="text-sm text-muted-foreground">
                        {step.description}
                    </p>

                    {/* Accordion Toggle */}
                    {hasData && (
                        <div className="mt-2">
                            <button
                                onClick={() => setIsOpen(!isOpen)}
                                className="flex items-center text-xs font-medium text-primary hover:text-primary/80 transition-colors focus:outline-none"
                            >
                                {isOpen ? (
                                    <>
                                        <ChevronUp className="w-3 h-3 mr-1" />
                                        Hide API Response
                                    </>
                                ) : (
                                    <>
                                        <ChevronDown className="w-3 h-3 mr-1" />
                                        Show API Response
                                    </>
                                )}
                            </button>

                            {/* Data Content */}
                            <div
                                className={cn(
                                    "grid transition-all duration-300 ease-in-out overflow-hidden",
                                    isOpen ? "grid-rows-[1fr] opacity-100 mt-3" : "grid-rows-[0fr] opacity-0 mt-0"
                                )}
                            >
                                <div className="overflow-hidden">
                                    <div className="bg-muted/50 rounded-lg p-3 text-xs border border-border font-mono overflow-x-auto max-h-60 overflow-y-auto">
                                        <pre>
                                            {JSON.stringify(stepData!.data, null, 2)}
                                        </pre>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};


export const JourneyOverview: FC<JourneyOverviewProps> = ({ steps, collectedData, onFinish }) => {
    // Helper to find data for a step
    const getStepData = (stepNumber: number) => {
        return collectedData.find(d => d.stepNumber === stepNumber);
    };

    return (
        <div className="w-full max-w-3xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
            {/* Header Section */}
            <div className="text-center space-y-4">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-100 text-green-600 mb-2 shadow-lg animate-bounce">
                    <Check className="w-10 h-10" strokeWidth={3} />
                </div>
                <h2 className="text-3xl font-bold text-foreground tracking-tight">
                    Verification Complete!
                </h2>
                <p className="text-muted-foreground text-lg max-w-lg mx-auto">
                    You have successfully completed all steps. Here is a summary of your verification journey.
                </p>
            </div>

            {/* Steps Timeline Card */}
            <Card className="border-border shadow-md bg-card overflow-hidden">
                <CardHeader className="bg-muted/30 border-b border-border">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <FileText className="w-5 h-5 text-primary" />
                        Verification Summary
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="divide-y divide-border">
                        {steps.map((step) => (
                            <StepSummaryItem
                                key={step.step_number}
                                step={step}
                                stepData={getStepData(step.step_number)}
                            />
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Actions */}
            {/* <div className="flex justify-center pt-4">
                <Button
                    onClick={onFinish}
                    className="w-full sm:w-auto min-w-[200px] h-12 text-lg font-semibold shadow-lg hover:shadow-xl transition-all"
                >
                    Finish Journey
                </Button>
            </div> */}
        </div>
    );
};
