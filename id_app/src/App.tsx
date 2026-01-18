import { useEffect, useState } from 'react';
import { useJourneyStore } from './lib/store';
import { DynamicForm } from './components/DynamicForm';
import { Card, CardContent } from './components/ui/card';
import { Stepper } from './components/Stepper';

function App() {
  const { initSession, fetchFlowDetails, currentStepData, flowData, error, submitStep } = useJourneyStore();
  const [started, setStarted] = useState(false);

  // Simple heuristic: If we have currentStepData, we can try to find its step number? 
  // For now, let's assume strict linear: 1 when started, increment on Next? 
  // Better: Backend should trigger this. 
  // Let's stick to 1 for this turn or parse it from currentStepData if available.
  const [currentStep, setCurrentStep] = useState(1);

  useEffect(() => {
    const init = async () => {
      const params = new URLSearchParams(window.location.search);
      const token = params.get('tkn');

      if (token) {
        initSession(token);
        await fetchFlowDetails();

        if (!started) {
          await submitStep({});
          setStarted(true);
        }
      }
    };
    init();
  }, []);

  if (!started && !currentStepData) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="animate-pulse flex flex-col items-center">
          <div className="h-4 w-32 bg-gray-200 rounded mb-4"></div>
          <p className="text-gray-500">Loading your journey...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 font-sans text-gray-900">
      <div className="max-w-4xl mx-auto pt-8">
        {/* Header Section */}
        {flowData && (
          <div className="mb-8 text-center">
            <h1 className="text-3xl font-extrabold text-blue-900 tracking-tight">{flowData.flow_details.name}</h1>
            <p className="text-gray-600 mt-2">{flowData.flow_details.description}</p>
            {flowData.end_customer && (
              <p className="text-sm text-gray-500 mt-1">Welcome, <span className="font-medium text-gray-800">{flowData.end_customer.name}</span></p>
            )}
          </div>
        )}

        {/* Stepper */}
        {flowData?.steps && (
          <Stepper steps={flowData.steps} currentStep={currentStep} />
        )}

        {error && (
          <div className="max-w-md mx-auto mb-4 p-4 bg-red-100 text-red-700 rounded-md shadow-sm border border-red-200">
            {error}
          </div>
        )}

        {/* Form Area */}
        <div className="transition-all duration-500 ease-in-out">
          {currentStepData && currentStepData.action === 'NEXT_FORM' && (
            <DynamicForm
              featureName={currentStepData.title || currentStepData.feature_name}
              fields={currentStepData.form_fields}
            />
          )}

          {currentStepData && (currentStepData.action === 'STEP_COMPLETE' || currentStepData.action === 'JOURNEY_COMPLETE') && (
            <Card className="max-w-md mx-auto mt-6 text-center shadow-lg border-green-100">
              <CardContent className="pt-8 pb-8">
                <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckIcon className="w-8 h-8" />
                </div>
                <h2 className="text-2xl font-bold text-green-700 mb-2">Success!</h2>
                <p className="text-gray-600">{currentStepData.message}</p>

                {currentStepData.action === 'STEP_COMPLETE' && (
                  <button
                    onClick={async () => {
                      await submitStep({});
                      setCurrentStep(prev => prev + 1); // Optimistic Update
                    }}
                    className="mt-6 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-full transition-colors shadow-md hover:shadow-lg"
                  >
                    Continue to Next Step
                  </button>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function CheckIcon(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
  )
}

export default App;
