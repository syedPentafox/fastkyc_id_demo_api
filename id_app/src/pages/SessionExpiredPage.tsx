import { FC } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Clock, AlertTriangle } from 'lucide-react';
import { BrandHeader } from '@/components/BrandHeader';

const SessionExpiredPage: FC = () => {
    return (
        <div className="min-h-screen bg-background">
            <BrandHeader />
            <div className="flex items-center justify-center min-h-[80vh] px-4">
                <Card className="max-w-md w-full shadow-2xl border-0 bg-card/90 backdrop-blur animate-in fade-in zoom-in-95 duration-500">
                    <CardContent className="pt-12 pb-12 text-center">
                        <div className="w-20 h-20 bg-destructive/10 text-destructive rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl relative animate-pulse">
                            <Clock className="w-10 h-10" />
                            <div className="absolute -bottom-1 -right-1 bg-white rounded-full p-1">
                                <AlertTriangle className="w-6 h-6 text-yellow-500" />
                            </div>
                        </div>

                        <h2 className="text-3xl font-bold text-foreground mb-3">Session Expired</h2>

                        <p className="text-muted-foreground mb-8 text-lg leading-relaxed">
                            For your security, this verification session has timed out due to inactivity.
                        </p>

                        <div className="space-y-4">
                            <div className="text-sm text-muted-foreground bg-muted/50 p-4 rounded-lg border border-border">
                                Please request a new verification link to continue safely.
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default SessionExpiredPage;
