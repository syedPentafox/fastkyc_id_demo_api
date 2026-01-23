import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import { FormField } from '@/lib/types';

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
            try {
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
            } catch (e) {
                // Ignore invalid regex from backend to prevent crash
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
            
            // Check Mandatory
            if (field.is_mandatory && !value) {
                newErrors[field.field] = 'This field is required';
            }

            // Check Regex
            if (field.regex && value) {
                try {
                    const regexPattern = new RegExp(field.regex);
                    if (!regexPattern.test(value)) {
                        newErrors[field.field] = 'Invalid format';
                    }
                } catch (e) { }
            }
        });

        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors);
            return;
        }

        onSubmit(formData);
    };

    return (
        <Card className="w-full max-w-2xl mx-auto mt-6 shadow-lg border-border bg-card overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <CardHeader className="border-b border-border bg-muted/50">
                <CardTitle className="text-2xl font-bold text-foreground">
                    {featureName}
                </CardTitle>
                <CardDescription className="text-muted-foreground">
                    Please provide the required information below
                </CardDescription>
            </CardHeader>

            <form onSubmit={handleSubmit}>
                <CardContent className="space-y-6 pt-6 pb-6">
                    {fields.map((field) => {
                        const fieldType = (field.type || 'text').toUpperCase();
                        const isText = fieldType === 'TEXT' || fieldType === 'STRING' || fieldType === 'INPUT';
                        const isNumber = fieldType === 'NUMBER' || fieldType === 'NUMERIC' || fieldType === 'INTEGER';

                        return (
                            <div key={field.field} className="space-y-2 group">
                                <Label
                                    htmlFor={field.field}
                                    className="text-sm font-semibold text-foreground flex items-center gap-2"
                                >
                                    {field.label || field.field}
                                    {field.is_mandatory && (
                                        <span className="text-destructive text-base">*</span>
                                    )}
                                </Label>

                                {isText ? (
                                    <Input
                                        id={field.field}
                                        required={field.is_mandatory}
                                        onChange={(e) => handleChange(field.field, e.target.value, field.regex)}
                                        className={`border-input bg-background transition-all duration-200 focus:ring-2 focus:ring-primary/20 ${errors[field.field] ? 'border-destructive focus:ring-destructive/20' : 'focus:border-primary hover:border-primary/50'}`}
                                        placeholder={`Enter ${(field.label || field.field).toLowerCase()}`}
                                    />
                                ) : isNumber ? (
                                    <Input
                                        id={field.field}
                                        type="number"
                                        required={field.is_mandatory}
                                        onChange={(e) => handleChange(field.field, e.target.value, field.regex)}
                                        className={`border-input bg-background transition-all duration-200 focus:ring-2 focus:ring-primary/20 ${errors[field.field] ? 'border-destructive focus:ring-destructive/20' : 'focus:border-primary hover:border-primary/50'}`}
                                        placeholder={`Enter ${(field.label || field.field).toLowerCase()}`}
                                    />
                                ) : (
                                    <Input
                                        id={field.field}
                                        placeholder={`Unsupported type: ${field.type}`}
                                        disabled
                                        className="bg-muted border-input opacity-50 cursor-not-allowed"
                                    />
                                )}
                                
                                {errors[field.field] && (
                                    <p className="text-sm text-destructive flex items-center gap-1 animate-in slide-in-from-left-1">
                                        <span className="text-xs">⚠</span>
                                        {errors[field.field]}
                                    </p>
                                )}
                            </div>
                        );
                    })}
                </CardContent>

                <CardFooter className="pt-6 pb-6 bg-muted/10">
                    <Button
                        type="submit"
                        className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-6 rounded-lg shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
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
