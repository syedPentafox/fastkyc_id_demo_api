# Efforts

1. 21-Jul-25 : 25-Jul-25
* Server Setup
2. 28-Jul-25 : 01-Aug-25
* Initial Requirement
3. 04-Aug-25 : 08-Aug-25
* Updated Requirement
4. 11-Aug-25 : 15-Aug-25
* Latest Enhanced Requirement
5. 19-Aug-25 : 23-Aug-25
* DB Transactions
* Entries for Internet Banking, Vishing, Demat, UPI, Credit Card
6. 25-Aug-25 : 29-Aug-25
* Auto Response
* RES check against acknowledgement_no in i4c_request
* Invalid RRN / Statement Unavailable handling
* POS string check handling
* Email & Phone from API
7. 01-Sep-25 : 05-Sep-25
* Branch code and Branch number to be taken from db
* Bank master to be taken from db
* Separate log files for each Job
* I4C Response table must also have request
* Separate table to store all actions being taken
    - RRN Validation
    - Balance Check
    - Hold Funds
    - Money Transfer
    - Money Withdrawal
* Any other handling
* Go Live

# Initial Requirement

```mermaid
flowchart TD
    Customer(["Customer"]) -- Reports Fraud --> NCRP(["NCRP System"])
    NCRP -- Send Fraud Alert via --> NCRPRequestAPI(["CyberCrime I4C Request API"])
    NCRPRequestAPI --> CompliancePortal(["KVB Compliance Portal"])
    CompliancePortal -- Balance Check --> CoreBanking(["I4C AccountStatement API"])
    CoreBanking -- Returns Balance Info --> CompliancePortal
    CompliancePortal -- Is Amount Available? --> Decision{"Amount Available?"}
    Decision -- Yes --> HoldFund["Invoke Hold Fund Maintenance API"]
    HoldFund --> HoldFundAPI(["Hold Fund Maintenance API"])
    HoldFundAPI --> RecoverySystems(["Internal / Interbank Recovery Systems"])
    RecoverySystems -- Send Hold Response --> HoldFundAPI
    HoldFundAPI -- Send Recovery Status --> NCRPCyberCrimeResponseAPI(["CyberCrime I4C Response API"])
    Decision -- No --> SplitHandling["Split Transaction Handling"]
    SplitHandling --> ATMPath["ATM Withdrawal Path"] & BankTransferPath["Bank Transfer Path"]
    ATMPath -- Invoke --> AccountStatementAPI(["I4C AccountStatement API"])
    AccountStatementAPI --> ATMPath
    AccountStatementAPI -- Send Recovery Status --> NCRPCyberCrimeResponseAPI
    BankTransferPath -- Invoke --> PaymentStatusInqAPI(["I4C PaymentStatusInq API"])
    PaymentStatusInqAPI --> BankTransferPath
    PaymentStatusInqAPI -- Send Recovery Status --> NCRPCyberCrimeResponseAPI
    NCRPCyberCrimeResponseAPI -- Forward Response --> NCRP

    %% Apply the pink api style to all API nodes
    NCRPRequestAPI:::api
    HoldFundAPI:::api
    NCRPCyberCrimeResponseAPI:::api
    AccountStatementAPI:::api
    PaymentStatusInqAPI:::api
    CoreBanking:::api

    classDef api fill:#f9f,stroke:#333,stroke-width:2px
```

# Updated Requirement

```mermaid
flowchart TD
    Customer(["Customer"]) -- Reports Fraud --> NCRP(["NCRP System"])
    NCRP -- Send Fraud Alert via --> NCRPRequestAPI(["CyberCrime I4C Request API"])
    NCRPRequestAPI --> CompliancePortal(["KVB Compliance Portal"])
    CompliancePortal -- Balance Check --> CoreBanking(["I4C AccountStatement API"])
    CoreBanking -- Returns Balance Info --> CompliancePortal
    CompliancePortal --> DebitCreditCheck{"Debit Flow or Credit Flow?"}
    
    %% DEBIT FLOW (New - Green)
    DebitCreditCheck -- DEBIT --> DebitHandling["Handle Single Transaction"]
    DebitHandling --> NEFTRTGSIMPSDebit["NEFT/RTGS/IMPS"] & UPIDebit["UPI"]
    NEFTRTGSIMPSDebit --> PaymentStatusInqDebit(["I4C PaymentStatusInq API"])
    PaymentStatusInqDebit --> NCRPCyberCrimeResponseAPI
    UPIDebit --> UPITransactionEnqDebit(["UPITransactionEnquiry API"])
    UPITransactionEnqDebit --> NCRPCyberCrimeResponseAPI
    
    %% CREDIT FLOW (Continue normal flow)
    DebitCreditCheck -- CREDIT --> Decision{"Amount Available?"}
    Decision -- Yes --> HoldFund["Invoke Hold Fund Maintenance API"]
    HoldFund --> HoldFundAPI(["Hold Fund Maintenance API"])
    HoldFundAPI --> RecoverySystems(["Internal / Interbank Recovery Systems"])
    RecoverySystems -- Send Hold Response --> HoldFundAPI
    HoldFundAPI --> NCRPCyberCrimeResponseAPI(["CyberCrime I4C Response API"])
    
    Decision -- No --> PartialHold["Hold Available Amount"]
    PartialHold --> PartialHoldAPI(["Hold Fund Maintenance API"])
    PartialHoldAPI --> PartialRecovery(["Internal / Interbank Recovery Systems"])
    PartialRecovery -- Send Hold Response --> PartialHoldAPI
    PartialHoldAPI --> PartialResponse(["CyberCrime I4C Response API"])
    PartialResponse --> SplitHandling["Split Transaction Handling (Sequential for Pending Amount)"]
    
    %% SPLIT TRANSACTION HANDLING (Enhanced - Green)
    SplitHandling --> NEFTRTGSIMPSPath["NEFT/RTGS/IMPS Path"] & UPIPath["UPI Path"] & ATMPath["ATM Path"] & POSPath["POS Path"] & CHQPath["CHQ PAID Path"] & AEPSPath["AEPS Path"]
    
    %% NEFT/RTGS/IMPS Path
    NEFTRTGSIMPSPath --> PaymentStatusInqAPI(["I4C PaymentStatusInq API"])
    PaymentStatusInqAPI --> NCRPCyberCrimeResponseAPI
    
    %% UPI Path
    UPIPath --> UPITransactionEnqAPI(["UPITransactionEnquiry API"])
    UPITransactionEnqAPI --> NCRPCyberCrimeResponseAPI
    
    %% ATM Path
    ATMPath --> NCRPCyberCrimeResponseAPI
    
    %% POS Path
    POSPath --> NCRPCyberCrimeResponseAPI
    
    %% CHQ PAID Path
    CHQPath --> NCRPCyberCrimeResponseAPI
    
    %% AEPS Path
    AEPSPath --> NCRPCyberCrimeResponseAPI
    
    NCRPCyberCrimeResponseAPI -- Forward Response --> NCRP

    %% Apply the pink api style to original API nodes
    NCRPRequestAPI:::api
    HoldFundAPI:::api
    CoreBanking:::api
    NCRPCyberCrimeResponseAPI:::api
    PartialHoldAPI:::api
    PartialResponse:::api

    %% Apply green style to new additions
    DebitCreditCheck:::new
    DebitHandling:::new
    NEFTRTGSIMPSDebit:::new
    UPIDebit:::new
    PaymentStatusInqDebit:::new
    UPITransactionEnqDebit:::new
    PartialHold:::new
    SplitHandling:::new
    NEFTRTGSIMPSPath:::new
    UPIPath:::new
    ATMPath:::new
    POSPath:::new
    CHQPath:::new
    AEPSPath:::new
    PaymentStatusInqAPI:::new
    UPITransactionEnqAPI:::new

    classDef api fill:#f9f,stroke:#333,stroke-width:2px
    classDef new fill:#9f9,stroke:#333,stroke-width:2px
```

# Latest Enhanced Requirement

```mermaid
flowchart TD
    Customer(["Customer"]) -- Reports Fraud --> NCRP(["NCRP System"])
    NCRP -- Send Fraud Alert via --> NCRPRequestAPI(["CyberCrime I4C Request API"])
    NCRPRequestAPI --> CompliancePortal(["KVB Compliance Portal"])
    CompliancePortal -- Balance Check --> CoreBanking(["I4C AccountStatement API"])
    CoreBanking -- Returns Balance Info --> CompliancePortal
    CompliancePortal --> RRNValidation{"RRN Validation (RRN, Amount, Transaction Date)"}
    
    %% RRN VALIDATION OUTCOMES (New - Purple)
    RRNValidation -- Transaction Found --> DebitCreditCheck{"Debit Flow or Credit Flow?"}
    RRNValidation -- Transaction NOT Found --> InvalidRRNResponse(["CyberCrime I4C Response API (Status 02)"])
    InvalidRRNResponse --> InvalidRRNEnd["End Process"]
    
    %% DEBIT FLOW (Enhanced - Purple for new additions)
    DebitCreditCheck -- DEBIT --> DebitHandling["Handle Single Transaction"]
    DebitHandling --> NEFTRTGSIMPSDebit["NEFT/RTGS/IMPS"] & UPIDebit["UPI"] & AEPSDebit["AEPS"] & CHQDebit["CHQ PAID"] & POSDebit["POS"] & ATMDebit["ATM"]
    
    NEFTRTGSIMPSDebit --> PaymentStatusInqDebit(["I4C PaymentStatusInq API"])
    PaymentStatusInqDebit --> NCRPCyberCrimeResponseAPI
    
    UPIDebit --> UPITransactionEnqDebit(["UPITransactionEnquiry API"])
    UPITransactionEnqDebit --> NCRPCyberCrimeResponseAPI
    
    AEPSDebit --> NCRPCyberCrimeResponseAPI
    CHQDebit --> NCRPCyberCrimeResponseAPI
    POSDebit --> NCRPCyberCrimeResponseAPI
    ATMDebit --> NCRPCyberCrimeResponseAPI
    
    %% CREDIT FLOW (Continue normal flow)
    DebitCreditCheck -- CREDIT --> Decision{"Amount Available?"}
    Decision -- Yes --> HoldFund["Invoke Hold Fund Maintenance API"]
    HoldFund --> HoldFundAPI(["Hold Fund Maintenance API"])
    HoldFundAPI --> RecoverySystems(["Internal / Interbank Recovery Systems"])
    RecoverySystems -- Send Hold Response --> HoldFundAPI
    HoldFundAPI --> NCRPCyberCrimeResponseAPI(["CyberCrime I4C Response API"])
    
    Decision -- No --> PartialHold["Hold Available Amount"]
    PartialHold --> PartialHoldAPI(["Hold Fund Maintenance API"])
    PartialHoldAPI --> PartialRecovery(["Internal / Interbank Recovery Systems"])
    PartialRecovery -- Send Hold Response --> PartialHoldAPI
    PartialHoldAPI --> PartialResponse(["CyberCrime I4C Response API"])
    PartialResponse --> SplitHandling["Split Transaction Handling (Sequential for Pending Amount)"]
    
    %% SPLIT TRANSACTION HANDLING (Enhanced - Green)
    SplitHandling --> NEFTRTGSIMPSPath["NEFT/RTGS/IMPS Path"] & UPIPath["UPI Path"] & ATMPath["ATM Path"] & POSPath["POS Path"] & CHQPath["CHQ PAID Path"] & AEPSPath["AEPS Path"]
    
    %% NEFT/RTGS/IMPS Path
    NEFTRTGSIMPSPath --> PaymentStatusInqAPI(["I4C PaymentStatusInq API"])
    PaymentStatusInqAPI --> NCRPCyberCrimeResponseAPI
    
    %% UPI Path
    UPIPath --> UPITransactionEnqAPI(["UPITransactionEnquiry API"])
    UPITransactionEnqAPI --> NCRPCyberCrimeResponseAPI
    
    %% ATM Path
    ATMPath --> NCRPCyberCrimeResponseAPI
    
    %% POS Path
    POSPath --> NCRPCyberCrimeResponseAPI
    
    %% CHQ PAID Path
    CHQPath --> NCRPCyberCrimeResponseAPI
    
    %% AEPS Path
    AEPSPath --> NCRPCyberCrimeResponseAPI
    
    NCRPCyberCrimeResponseAPI -- Forward Response --> NCRP

    %% Apply the pink api style to original API nodes
    NCRPRequestAPI:::api
    HoldFundAPI:::api
    CoreBanking:::api
    NCRPCyberCrimeResponseAPI:::api
    PartialHoldAPI:::api
    PartialResponse:::api

    %% Apply green style to previous new additions
    DebitCreditCheck:::new
    DebitHandling:::new
    NEFTRTGSIMPSDebit:::new
    UPIDebit:::new
    PaymentStatusInqDebit:::new
    UPITransactionEnqDebit:::new
    PartialHold:::new
    SplitHandling:::new
    NEFTRTGSIMPSPath:::new
    UPIPath:::new
    ATMPath:::new
    POSPath:::new
    CHQPath:::new
    AEPSPath:::new
    PaymentStatusInqAPI:::new
    UPITransactionEnqAPI:::new

    %% Apply purple style to latest enhancements
    RRNValidation:::enhanced
    InvalidRRNResponse:::enhanced
    InvalidRRNEnd:::enhanced
    AEPSDebit:::enhanced
    CHQDebit:::enhanced
    POSDebit:::enhanced
    ATMDebit:::enhanced

    classDef api fill:#f9f,stroke:#333,stroke-width:2px
    classDef new fill:#9f9,stroke:#333,stroke-width:2px
    classDef enhanced fill:#b9b,stroke:#333,stroke-width:2px
```