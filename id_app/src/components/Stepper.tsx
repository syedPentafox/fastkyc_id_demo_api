import { FC } from 'react';
import { Check } from 'lucide-react';
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
    return (
        <div className="w-full max-w-4xl mx-auto mb-8">
            <div className="relative flex justify-between">
                {/* Progress Bar Background */}
                <div className="absolute top-1/2 left-0 w-full h-1 bg-gray-200 -translate-y-1/2 rounded-full -z-10" />

                {/* Active Progress Bar */}
                <div
                    className="absolute top-1/2 left-0 h-1 bg-blue-600 -translate-y-1/2 rounded-full transition-all duration-300 -z-10"
                    style={{
                        width: `${Math.min(((currentStep - 1) / (steps.length - 1)) * 100, 100)}%`
                    }}
                />

                {steps.map((step, index) => {
                    const isCompleted = step.step_number < currentStep;
                    const isCurrent = step.step_number === currentStep;

                    return (
                        <div key={step.step_number} className="flex flex-col items-center group">
                            <div
                                className={cn(
                                    "w-10 h-10 rounded-full flex items-center justify-center border-2 bg-white transition-all duration-300",
                                    isCompleted ? "border-blue-600 bg-blue-600 text-white" :
                                        isCurrent ? "border-blue-600 text-blue-600 scale-110 shadow-lg" :
                                            "border-gray-300 text-gray-400"
                                )}
                            >
                                {isCompleted ? <Check className="w-6 h-6" /> : <span>{step.step_number}</span>}
                            </div>

                            <div className="mt-2 text-center hidden sm:block">
                                <p className={cn(
                                    "text-sm font-semibold transition-colors",
                                    isCurrent || isCompleted ? "text-gray-900" : "text-gray-400"
                                )}>
                                    {step.name}
                                </p>
                                <p className="text-xs text-gray-500 max-w-[120px] truncate">
                                    {step.description}
                                </p>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
