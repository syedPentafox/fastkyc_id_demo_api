System Overview
This is a FastKYC ID Application API that orchestrates complex verification journeys by chaining together multiple API calls in a configurable flow. The system handles three main types of APIs:

Form APIs - Collect user input
Redirects APIs - Redirect users to external verification providers
Polling APIs - Check status of asynchronous verification processes
Architecture Components
1. Database Models (Core Entities)
Flow
 - A complete verification journey (e.g., "KYC Verification Flow")
FeatureFlow
 - A step within a flow (e.g., "Identity Verification Step")
FeatureMaster
 - Individual API endpoints (e.g., "Aadhaar Init", "Aadhaar Status")
ActiveFlow
 - Runtime instance tracking user's progress through a flow
FeatureApiDependency
 - Defines which APIs belong to which step and their execution order
2. Key Routers
flow_generation.py
 - Admin creates and activates flows
flow_journey.py
 - End-user starts the journey
journey_execution.py
 - Orchestrates step-by-step execution
How It Works: The Complete Flow
Phase 1: Flow Activation (Admin Side)
Endpoint: POST /api/flow/activate

Admin → Creates ActiveFlow instance
       → Generates JWT token with flow_id and customer_id
       → Returns redirect URL with token
       → End-user receives link like: https://app.com?tkn=<JWT>
What happens:

A unique 
ActiveFlow
 record is created with status 'active'
Initial state: current_step = 1, current_api_id = 0
Token contains: {flow_id, customer_id, end_customer_details}
Phase 2: Journey Initialization (End-User Side)
Endpoint: GET /api/flow/activate

End-user opens the link and the frontend calls this endpoint with the JWT token.

What happens:

Authenticates user via JWT
Fetches the complete flow structure with all steps and form fields
Returns journey metadata including:
Flow name and description
All steps with their features
Form fields for each feature
Current status
Phase 3: Journey Execution (The Core Orchestration)
This is where redirects and polling APIs work together!

3.1 Getting Current State
Endpoint: GET /api/journey/state

Function: 
resolve_journey_state()

This function determines what UI to show the user based on:

Current step number
Current API within that step
API type (form, redirects, or polling)
Logic Flow:

python
1. Check if flow is completed → Return MessageUI("Journey Completed")
2. Get current step and API from ActiveFlow state
3. Check API type:
   
   IF api_type == 'pooling' (polling):
      → Execute polling check
      → If SUCCESS: Advance to next API, recurse
      → If PENDING: Return PollingUI (keep polling)
      → If FAILED: Return MessageUI with error
   
   ELSE (form or redirect):
      → Fetch form fields
      → Return FormUI with input fields
3.2 Executing a Step
Endpoint: POST /api/journey/next

Function: 
execute_journey_step()

This is where the magic happens! Here's the detailed flow:

1. USER SUBMITS FORM DATA
   ↓
2. GET CURRENT API CONFIGURATION
   - Identify which API to call based on ActiveFlow state
   ↓
3. PREPARE DATA (Dependency Injection)
   - Merge user input with journey_state
   - If client_id exists in journey_state, inject it
   - For redirects: Add redirect_url and state parameters
   ↓
4. EXECUTE API via FastKYCConnector
   - Call external FastKYC API
   - Payload: {"feature": "aadhaar_init", "data": {...}}
   ↓
5. LOG THE TRANSACTION
   - Save request/response to JourneyLog
   ↓
6. HANDLE RESPONSE BASED ON API TYPE:
   ┌─────────────────────────────────────────┐
   │  IF API TYPE = "redirects"              │
   └─────────────────────────────────────────┘
   
   Response contains: {"data": {"url": "https://provider.com/verify", "client_id": "xyz"}}
   
   Actions:
   a) Extract client_id from response
   b) Store client_id in journey_state (for next API)
   c) Store redirect_url in journey_state (for recovery)
   d) ADVANCE TO NEXT API (which should be polling)
   e) Return RedirectUI with the URL
   
   Frontend receives RedirectUI → Opens URL in new window/iframe
   User completes verification on external site
   
   ┌─────────────────────────────────────────┐
   │  AFTER REDIRECT COMPLETES               │
   └─────────────────────────────────────────┘
   
   User returns to app → Frontend calls GET /journey/state
   
   resolve_journey_state() executes:
   - Sees current API is type 'pooling'
   - Calls execute_polling_check()
   
   ┌─────────────────────────────────────────┐
   │  POLLING MECHANISM                      │
   └─────────────────────────────────────────┘
   
   execute_polling_check():
   a) Get client_id from journey_state
   b) Call polling API with {"client_id": "xyz"}
   c) Check response status:
   
      IF status == "SUCCESS":
         - Extract updated client_id (if any)
         - Update journey_state
         - ADVANCE TO NEXT API
         - Return None (signals state changed)
         - Caller recurses to get new state
      
      IF status == "PENDING":
         - Return PollingUI
         - Frontend keeps polling GET /journey/state
      
      IF status == "FAILED":
         - Return MessageUI with error
   
   ┌─────────────────────────────────────────┐
   │  IF API TYPE = "form" (normal)          │
   └─────────────────────────────────────────┘
   
   Response: {"status": "SUCCESS", "data": {"client_id": "abc"}}
   
   Actions:
   a) Extract client_id (if present)
   b) Store in journey_state
   c) ADVANCE TO NEXT API
   d) Return next state (could be form, redirect, or polling)
The Redirect + Polling Pattern (Step-by-Step)
Let's trace a real example: Aadhaar Verification

Step 1: User Submits Aadhaar Number
POST /api/journey/next
Body: {"aadhaar_number": "1234-5678-9012"}
Current State:
- current_step: 1
- current_api_id: 0 (will fetch first API in step 1)
- API: "aadhaar_init" (type: "redirects")
Execution:
1. FastKYCConnector calls aadhaar_init API
2. Response: {
     "status": "SUCCESS",
     "data": {
       "url": "https://uidai.gov.in/verify?session=xyz",
       "client_id": "client_123"
     }
   }
3. System stores:
   journey_state = {
     "client_id": "client_123",
     "redirect_url": "https://uidai.gov.in/verify?session=xyz"
   }
4. System advances: current_api_id → next API (aadhaar_status)
5. Returns: RedirectUI(url="https://uidai.gov.in/verify?session=xyz")
Frontend Action:
- Opens redirect URL
- User completes OTP verification on UIDAI site
- User returns to app
Step 2: Frontend Polls for Status
GET /api/journey/state (called every 2-3 seconds)
Current State:
- current_step: 1
- current_api_id: <aadhaar_status API ID>
- API: "aadhaar_status" (type: "pooling")
Execution:
1. resolve_journey_state() detects api_type == 'pooling'
2. execute_polling_check() runs:
   - Gets client_id = "client_123" from journey_state
   - Calls FastKYC polling API with {"client_id": "client_123"}
3. First few calls return:
   {
     "status": "PENDING",
     "message": "Verification in progress"
   }
   
   → Returns PollingUI(message="Verification in progress...")
   → Frontend shows spinner, keeps polling
4. Eventually returns:
   {
     "status": "SUCCESS",
     "data": {
       "verified": true,
       "name": "John Doe",
       "client_id": "client_123_updated"
     }
   }
   
   → Updates journey_state with new client_id
   → Advances to next API/step
   → Recurses to get new state
   → Returns next FormUI or MessageUI
Key Design Patterns
1. State Machine Pattern
The 
ActiveFlow
 acts as a state machine:

State: 
(current_step, current_api_id, journey_state)
Transitions: 
advance_flow_state()
 moves to next API or step
Deterministic: 
resolve_journey_state()
 always returns same UI for same state
2. Dependency Injection via journey_state
python
journey_state = {
    "client_id": "xyz",  # From previous API
    "redirect_url": "...",  # For recovery
    # Any other data needed by subsequent APIs
}
Each API can:

Consume data from previous APIs (e.g., client_id)
Produce data for next APIs (e.g., verification results)
3. Recursive State Resolution
When polling succeeds:

python
if status == "SUCCESS":
    advance_flow_state()
    return None  # Signal to re-resolve
# In resolve_journey_state():
ui_result = execute_polling_check()
if ui_result is None:
    return resolve_journey_state()  # Recurse!
This automatically chains APIs without frontend intervention.

4. API Type Routing
python
if api_type == 'redirects':
    # Advance immediately, return RedirectUI
    advance_flow_state()
    return RedirectUI(url=...)
elif api_type == 'pooling':
    # Check status, advance only on success
    result = execute_polling_check()
    if result is None:  # Success
        return resolve_journey_state()  # Get next state
    return result  # PollingUI or MessageUI
else:  # form
    # Return FormUI for user input
    return FormUI(...)
Data Flow Diagram
┌─────────────┐
│   Admin     │
│  Activates  │
│    Flow     │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   ActiveFlow        │
│   created           │
│   JWT generated     │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  End User Opens     │
│  Link with Token    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  GET /flow/activate                     │
│  Returns flow structure                 │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  GET /journey/state                     │
│  Returns: FormUI (collect data)         │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  POST /journey/next                     │
│  Body: {aadhaar: "1234"}                │
│                                         │
│  1. Call aadhaar_init (redirects)       │
│  2. Get client_id + redirect_url        │
│  3. Store in journey_state              │
│  4. Advance to next API                 │
│  5. Return RedirectUI                   │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  User completes verification            │
│  on external site                       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  GET /journey/state (polling loop)      │
│                                         │
│  1. Detect api_type = 'pooling'         │
│  2. Call aadhaar_status with client_id  │
│  3. If PENDING → Return PollingUI       │
│  4. If SUCCESS → Advance → Recurse      │
│  5. Return next state                   │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Continue with next step...             │
│  (Could be another form/redirect/poll)  │
└─────────────────────────────────────────┘
Critical Implementation Details
1. Redirect API Handling
python
# In execute_journey_step()
if target_api_dep.api_type == "redirects":
    redirect_url = data.get("url")
    
    # Store for recovery
    journey_state["redirect_url"] = redirect_url
    flow.journey_state = journey_state
    
    # CRITICAL: Advance BEFORE returning
    advance_flow_state(session, flow, target_api_dep)
    
    # Return RedirectUI (frontend handles redirect)
    return JourneyState(ui=RedirectUI(url=redirect_url))
Why advance before returning?

Next API (polling) must be ready when user returns
Prevents race conditions
2. Polling API Handling
python
# In resolve_journey_state()
if target_api_dep.api_type == 'pooling':
    ui_result = execute_polling_check(...)
    
    if ui_result is None:  # Success!
        # State was advanced inside execute_polling_check
        return resolve_journey_state(...)  # Get new state
    
    return JourneyState(ui=ui_result)  # PollingUI or MessageUI
Polling check logic:

python
def execute_polling_check(...):
    result = connector.execute_feature(feature, {"client_id": client_id})
    
    if status == "SUCCESS":
        # Update journey_state with new data
        journey_state["client_id"] = new_client_id
        
        # Advance to next API
        advance_flow_state(...)
        
        # Return None to signal state change
        return None
    
    elif status == "PENDING":
        return PollingUI(message="Processing...")
    
    else:
        return MessageUI(status="FAILED", message=...)
3. Client ID Propagation
python
# In execute_journey_step()
journey_state = flow.journey_state or {}
final_data = input_data.copy()
# Inject client_id if exists
if "client_id" in journey_state:
    final_data["client_id"] = journey_state["client_id"]
# Call API with merged data
api_result = connector.execute_feature(feature, final_data)
# Extract and store new client_id
if "client_id" in api_result.get("data", {}):
    journey_state["client_id"] = api_result["data"]["client_id"]
    flow.journey_state = journey_state
Summary
The system orchestrates complex verification flows by:

Chaining APIs - Each API's output becomes input for the next
State Management - 
journey_state
 carries data between APIs
Type-Based Routing - Different handling for form/redirect/polling
Automatic Advancement - Redirects advance immediately, polling advances on success
Recursive Resolution - Successful polling triggers automatic progression
Frontend Polling - Client repeatedly calls /journey/state until completion
The redirect + polling pattern enables:

External verification (user leaves app)
Asynchronous processing (server-side status checks)
Seamless UX (automatic progression when ready)
Resilient flows (state persisted in database)
This architecture allows building complex multi-step verification journeys with minimal frontend logic - the backend orchestrates everything based on configuration!

