# Customer: Contoso Ltd

## Environment
- Microsoft Sentinel workspace: contoso-sentinel-prod (Log Analytics)
- Microsoft Defender XDR connected to Sentinel (Device* and Email* tables available in Sentinel)
- Identity: Microsoft Entra ID, hybrid with on-prem AD (contoso.local)
- Corporate VPN egress: 198.51.100.0/24

## Settings
- default_lookback: 14d
- event_window: 1d
- allow_external_llm: true
- kql_require_time_filter: true

## Sentinel Tables

### SigninLogs
Product: Microsoft Entra ID
Time field: TimeGenerated
Description: Interactive user sign-ins.
- TimeGenerated
- UserPrincipalName (user)
- UserDisplayName
- IPAddress (ip)
- Location
- LocationDetails
- AppDisplayName (app)
- ClientAppUsed
- ResultType (result)
- ResultDescription
- ConditionalAccessStatus
- AuthenticationRequirement
- MfaDetail
- DeviceDetail
- UserAgent
- RiskLevelDuringSignIn
- RiskState
- CorrelationId

### AADNonInteractiveUserSignInLogs
Product: Microsoft Entra ID
Time field: TimeGenerated
- TimeGenerated
- UserPrincipalName
- IPAddress
- Location
- AppDisplayName
- ResultType
- ResultDescription
- UserAgent

### AuditLogs
Product: Microsoft Entra ID
Time field: TimeGenerated
- TimeGenerated
- OperationName
- Category
- Result
- InitiatedBy
- TargetResources
- AdditionalDetails
- CorrelationId

### SecurityAlert
Product: Microsoft Sentinel
Time field: TimeGenerated
- TimeGenerated
- AlertName
- AlertSeverity
- ProviderName
- ProductName
- Description
- Entities
- CompromisedEntity
- SystemAlertId

## Investigation Notes
- Sign-ins from 198.51.100.0/24 are the corporate VPN and are expected.
- Escalate any successful sign-in by a Tier-0 admin (accounts prefixed adm-) from a new country to the on-call lead.
- Check AADNonInteractiveUserSignInLogs as well as SigninLogs for token replay.

## KQL Guidelines
- Use TimeGenerated for all Sentinel tables.
- Prefer `=~` for UPN comparisons.

## Ticket Requirements
- Ticket title format: "[Contoso] <event type> - <user or host>".
- Severity must be set by the analyst using the Contoso matrix.
