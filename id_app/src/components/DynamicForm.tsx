import React, { useState } from 'react';
import { useJourneyStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface FormField {
    field: string; // name
    label: string;
    type: string; // TEXT, RADIO, FILE, NUMERIC
    is_required: boolean;
    regex?: string;
    options?: string; // JSON string for radio/select
}

interface Props {
    featureName: string;
    fields: FormField[];
}

export const DynamicForm: React.FC<Props> = ({ featureName, fields }) => {
    const { submitStep, isLoading } = useJourneyStore();
    const [formData, setFormData] = useState<Record<string, any>>({});

    const handleChange = (field: string, value: any) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        submitStep(formData);
    };

    return (
        <Card className="w-full max-w-md mx-auto mt-10">
            <CardHeader>
                <CardTitle>{featureName}</CardTitle>
                <CardDescription>Please provide the details below.</CardDescription>
            </CardHeader>
            <form onSubmit={handleSubmit}>
                <CardContent className="space-y-4">
                    {fields.map((field) => (
                        <div key={field.field} className="space-y-2">
                            <Label htmlFor={field.field}>
                                {field.label} {field.is_required && <span className="text-red-500">*</span>}
                            </Label>

                            {/* Render Logic */}
                            {field.type === 'TEXT' || field.type === 'string' ? (
                                <Input
                                    id={field.field}
                                    required={field.is_required}
                                    onChange={(e) => handleChange(field.field, e.target.value)}
                                />
                            ) : field.type === 'NUMERIC' ? (
                                <Input
                                    id={field.field}
                                    type="number"
                                    required={field.is_required}
                                    onChange={(e) => handleChange(field.field, e.target.value)}
                                />
                            ) : (
                                <Input
                                    id={field.field}
                                    placeholder={`Unsupported type: ${field.type}`}
                                    disabled
                                />
                            )}
                        </div>
                    ))}
                </CardContent>
                <CardFooter>
                    <Button type="submit" className="w-full" disabled={isLoading}>
                        {isLoading ? 'Verifying...' : 'Continue'}
                    </Button>
                </CardFooter>
            </form>
        </Card>
    );
};
