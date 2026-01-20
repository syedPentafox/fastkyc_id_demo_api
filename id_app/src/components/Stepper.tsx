import { FC } from 'react';
import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';

interface Step {
    step_number: number;
    name: string;
    description: string;
    action?: string;
}

interface StepperProps {
    steps: Step[];
    currentStep: number;
    isJourneyComplete?: boolean;
}

export const Stepper: FC<StepperProps> = ({ steps, currentStep, isJourneyComplete }) => {
    return (
        <div className="w-full mb-8">
            <div className="block md:hidden">
                <MobileStepper steps={steps} currentStep={currentStep} isJourneyComplete={isJourneyComplete} />
            </div>
            <div className="hidden md:block">
                <DesktopStepper steps={steps} currentStep={currentStep} isJourneyComplete={isJourneyComplete} />
            </div>
        </div>
    );
};

const MobileStepper: FC<StepperProps> = ({ steps, currentStep, isJourneyComplete }) => {
    const progress = Math.min((currentStep / steps.length) * 100, 100);
    const activeStep = steps.find(s => s.step_number === currentStep) || steps[steps.length - 1];

    // Determine if the journey is fully complete for display logic
    const displayProgress = isJourneyComplete ? 100 : progress;

    return (
        <div className="bg-card border-b border-border/50 pb-4 mb-4">
            <div className="flex justify-between items-end mb-2 px-1">
                <div>
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest">
                        Step {isJourneyComplete ? steps.length : currentStep} of {steps.length}
                    </span>
                    <h3 className="text-sm font-semibold text-foreground mt-0.5 truncate max-w-[200px]">
                        {isJourneyComplete ? "Journey Complete" : activeStep?.name}
                    </h3>
                </div>
                <div className="text-right">
                    <span className="text-xs font-medium text-primary">
                        {Math.round(displayProgress)}%
                    </span>
                </div>
            </div>
            {/* Minimal Progress Bar */}
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                <div
                    className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
                    style={{ width: `${displayProgress}%` }}
                />
            </div>
        </div>
    );
};

const DesktopStepper: FC<StepperProps> = ({ steps, currentStep, isJourneyComplete }) => {
    return (
        <div className="max-w-4xl mx-auto px-4 py-8">
            <div className="relative flex items-center justify-between w-full">
                {/* Connecting Line - Background */}
                <div className="absolute top-1/2 left-0 w-full h-[2px] bg-muted -translate-y-1/2 z-0 rounded-full" />

                {/* Connecting Line - Progress */}
                <div
                    className="absolute top-1/2 left-0 h-[2px] bg-primary -translate-y-1/2 z-0 transition-all duration-700 ease-out rounded-full"
                    style={{
                        width: isJourneyComplete
                            ? '100%'
                            : `${((currentStep - 1) / (steps.length - 1)) * 100}%`
                    }}
                />

                {steps.map((step) => {
                    const isCompleted = isJourneyComplete || step.step_number < currentStep;
                    const isCurrent = !isJourneyComplete && step.step_number === currentStep;
                    const isPending = !isJourneyComplete && step.step_number > currentStep;

                    return (
                        <div key={step.step_number} className="relative z-10 group">
                            {/* Step Node */}
                            <div
                                className={cn(
                                    "flex items-center justify-center transition-all duration-300 rounded-full border-[3px]",
                                    isCurrent ? "w-4 h-4 bg-background border-primary shadow-[0_0_0_4px_rgba(var(--primary),0.15)] scale-125" : "w-3 h-3",
                                    isCompleted ? "bg-primary border-primary w-3 h-3" : "",
                                    isPending ? "bg-background border-muted" : ""
                                )}
                            >
                                {/* Active Pulse */}
                                {isCurrent && (
                                    <div className="absolute inset-0 bg-primary/30 rounded-full animate-ping" />
                                )}
                            </div>

                            {/* Label - Absolute positioning to prevent layout shift */}
                            <div className={cn(
                                "absolute top-8 left-1/2 -translate-x-1/2 w-max max-w-[150px] text-center transition-all duration-300 transform",
                                isCurrent ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-2 group-hover:opacity-100 group-hover:translate-y-0"
                            )}>
                                <p className={cn(
                                    "text-sm font-semibold mb-0.5",
                                    isCompleted ? "text-primary" : "text-foreground"
                                )}>
                                    {step.name}
                                </p>
                                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">
                                    Step {step.step_number}
                                </p>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Current Step Description (Floating below) */}
            {!isJourneyComplete && (
                <div className="mt-20 text-center animate-in fade-in slide-in-from-bottom-2 duration-500">
                    <p className="inline-block px-4 py-2 rounded-full bg-muted/30 text-muted-foreground text-sm leading-relaxed border border-border/50">
                        {steps[currentStep - 1]?.description}
                    </p>
                </div>
            )}
        </div>
    );
};
