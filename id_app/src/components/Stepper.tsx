import { FC } from 'react';
import { Check, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Step {
    step_number: number;
    name: string;
    description: string;
}

interface StepperProps {
    steps: Step[];
    currentStep: number;
}

export const Stepper: FC<StepperProps> = ({ steps, currentStep }) => {
    const progress = Math.min(((currentStep - 1) / (steps.length - 1)) * 100, 100);

    return (
        <div className="w-full max-w-4xl mx-auto mb-12 px-4">
            <div className="relative">
                {/* Background Track */}
                <div className="absolute top-8 left-0 w-full h-1 bg-gradient-to-r from-gray-200 via-gray-200 to-gray-200 rounded-full" />

                {/* Active Progress Bar with Gradient */}
                <div
                    className="absolute top-8 left-0 h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 rounded-full transition-all duration-700 ease-out shadow-lg"
                    style={{ width: `${progress}%` }}
                >
                    {/* Animated glow effect */}
                    <div className="absolute inset-0 bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 rounded-full blur-sm opacity-50 animate-pulse" />
                </div>

                {/* Steps */}
                <div className="relative flex justify-between">
                    {steps.map((step) => {
                        const isCompleted = step.step_number < currentStep;
                        const isCurrent = step.step_number === currentStep;
                        const isPending = step.step_number > currentStep;

                        return (
                            <div
                                key={step.step_number}
                                className="flex flex-col items-center group relative"
                                style={{ flex: 1 }}
                            >
                                {/* Step Circle */}
                                <div className="relative z-10 mb-3">
                                    <div
                                        className={cn(
                                            "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-500 transform",
                                            "border-4 shadow-lg",
                                            isCompleted && "bg-gradient-to-br from-green-400 to-emerald-500 border-green-300 scale-100",
                                            isCurrent && "bg-gradient-to-br from-blue-500 to-indigo-600 border-blue-300 scale-110 shadow-2xl ring-4 ring-blue-200 ring-opacity-50 animate-pulse",
                                            isPending && "bg-white border-gray-300 scale-95"
                                        )}
                                    >
                                        {isCompleted ? (
                                            <Check className="w-8 h-8 text-white drop-shadow-md" strokeWidth={3} />
                                        ) : isCurrent ? (
                                            <Circle className="w-8 h-8 text-white fill-white drop-shadow-md" />
                                        ) : (
                                            <span className="text-gray-400 font-bold text-xl">{step.step_number}</span>
                                        )}
                                    </div>

                                    {/* Pulse animation for current step */}
                                    {isCurrent && (
                                        <div className="absolute inset-0 rounded-full bg-blue-400 opacity-20 animate-ping" />
                                    )}
                                </div>

                                {/* Step Info */}
                                <div className="text-center max-w-[140px]">
                                    <p
                                        className={cn(
                                            "text-sm font-bold transition-all duration-300 mb-1",
                                            isCompleted && "text-green-700",
                                            isCurrent && "text-indigo-700 text-base",
                                            isPending && "text-gray-400"
                                        )}
                                    >
                                        {step.name}
                                    </p>
                                    <p
                                        className={cn(
                                            "text-xs transition-all duration-300 line-clamp-2",
                                            (isCurrent || isCompleted) ? "text-gray-600" : "text-gray-400"
                                        )}
                                    >
                                        {step.description}
                                    </p>
                                </div>

                                {/* Hover tooltip for desktop */}
                                <div className="hidden md:block absolute -bottom-20 left-1/2 transform -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-20">
                                    <div className="bg-gray-900 text-white text-xs rounded-lg py-2 px-3 shadow-xl max-w-[180px]">
                                        <p className="font-semibold mb-1">{step.name}</p>
                                        <p className="text-gray-300">{step.description}</p>
                                        <div className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45" />
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Progress percentage indicator */}
            <div className="mt-6 text-center">
                <div className="inline-flex items-center gap-2 bg-white px-4 py-2 rounded-full shadow-md border border-gray-200">
                    <div className="w-2 h-2 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full animate-pulse" />
                    <span className="text-sm font-semibold text-gray-700">
                        Step {currentStep} of {steps.length}
                    </span>
                    <span className="text-xs text-gray-500">
                        ({Math.round(progress)}% Complete)
                    </span>
                </div>
            </div>
        </div>
    );
};
