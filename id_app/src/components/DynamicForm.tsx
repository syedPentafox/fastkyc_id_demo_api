import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

interface FormField {
    field: string;
    label: string;
    type: string;
    is_required: boolean;
    regex?: string;
    options?: string;
}

interface Props {
    featureName: string;
    fields: FormField[];
    onSubmit: (data: any) => void;
    isLoading: boolean;
}

export const DynamicForm: React.FC<Props> = ({ featureName, fields, onSubmit, isLoading }) => {
    const [formData, setFormData] = useState<Record<string, any>>({});
    const [errors, setErrors] = useState<Record<string, string>>({});

    const handleChange = (field: string, value: any, regex?: string) => {
        setFormData(prev => ({ ...prev, [field]: value }));

        // Validate regex if provided
        if (regex && value) {
            const regexPattern = new RegExp(regex);
            if (!regexPattern.test(value)) {
                setErrors(prev => ({ ...prev, [field]: 'Invalid format' }));
            } else {
                setErrors(prev => {
                    const newErrors = { ...prev };
                    delete newErrors[field];
                    return newErrors;
                });
            }
        } else {
            // Clear error if no regex or empty value
            setErrors(prev => {
                const newErrors = { ...prev };
                delete newErrors[field];
                return newErrors;
            });
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        // Final validation check
        const newErrors: Record<string, string> = {};
        fields.forEach(field => {
            const value = formData[field.field];
            if (field.regex && value) {
                const regexPattern = new RegExp(field.regex);
                if (!regexPattern.test(value)) {
                    newErrors[field.field] = 'Invalid format';
                }
            }
        });

        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors);
            return;
        }

        onSubmit(formData);
    };

    return (
        <Card className="w-full max-w-2xl mx-auto mt-6 shadow-2xl border-indigo-100 bg-white overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500" />

            <CardHeader className="bg-gradient-to-br from-blue-50 to-indigo-50 border-b border-indigo-100">
                <CardTitle className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                    {featureName}
                </CardTitle>
                <CardDescription className="text-gray-600">
                    Please provide the required information below
                </CardDescription>
            </CardHeader>

            <form onSubmit={handleSubmit}>
                <CardContent className="space-y-6 pt-6 pb-6">
                    {fields.map((field) => (
                        <div key={field.field} className="space-y-2 group">
                            <Label
                                htmlFor={field.field}
                                className="text-sm font-semibold text-gray-700 flex items-center gap-2"
                            >
                                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 group-hover:bg-indigo-600 transition-colors" />
                                {field.label}
                                {field.is_required && (
                                    <span className="text-red-500 text-base">*</span>
                                )}
                            </Label>

                            {field.type === 'TEXT' || field.type === 'string' ? (
                                <>
                                    <Input
                                        id={field.field}
                                        required={field.is_required}
                                        onChange={(e) => handleChange(field.field, e.target.value, field.regex)}
                                        className={`border-gray-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200 bg-white hover:border-indigo-400 ${errors[field.field] ? 'border-red-500 focus:border-red-500 focus:ring-red-200' : ''
                                            }`}
                                        placeholder={`Enter ${field.label.toLowerCase()}`}
                                    />
                                    {errors[field.field] && (
                                        <p className="text-sm text-red-600 flex items-center gap-1">
                                            <span className="text-xs">⚠</span>
                                            {errors[field.field]}
                                        </p>
                                    )}
                                </>
                            ) : field.type === 'NUMERIC' ? (
                                <>
                                    <Input
                                        id={field.field}
                                        type="number"
                                        required={field.is_required}
                                        onChange={(e) => handleChange(field.field, e.target.value, field.regex)}
                                        className={`border-gray-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200 bg-white hover:border-indigo-400 ${errors[field.field] ? 'border-red-500 focus:border-red-500 focus:ring-red-200' : ''
                                            }`}
                                        placeholder={`Enter ${field.label.toLowerCase()}`}
                                    />
                                    {errors[field.field] && (
                                        <p className="text-sm text-red-600 flex items-center gap-1">
                                            <span className="text-xs">⚠</span>
                                            {errors[field.field]}
                                        </p>
                                    )}
                                </>
                            ) : (
                                <Input
                                    id={field.field}
                                    placeholder={`Unsupported type: ${field.type}`}
                                    disabled
                                    className="bg-gray-100 border-gray-300"
                                />
                            )}
                        </div>
                    ))}
                </CardContent>

                <CardFooter className="bg-gradient-to-br from-gray-50 to-blue-50 border-t border-gray-200 pt-6 pb-6">
                    <Button
                        type="submit"
                        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold py-6 rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <span className="flex items-center justify-center gap-2">
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Processing...
                            </span>
                        ) : (
                            'Continue'
                        )}
                    </Button>
                </CardFooter>
            </form>
        </Card>
    );
};
