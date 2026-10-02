# Customer: Fabrikam Inc

## Environment
- Microsoft Defender XDR only (Advanced Hunting); no Sentinel workspace
- Identity: Microsoft Entra ID (cloud only)
- Mail: Exchange Online with Defender for Office 365 P2

## Settings
- default_lookback: 7d
- event_window: 12h
- allow_external_llm: false
- kql_require_time_filter: true
- kql_forbidden_tables: SigninLogs, AuditLogs, SecurityEvent

## Advanced Hunting Tables

### AADSignInEventsBeta
Product: Microsoft Entra ID (via Defender XDR)
Time field: Timestamp
- Timestamp
- AccountUpn (user)
- AccountDisplayName
- AccountObjectId
- IPAddress (ip)
- Country (location)
- City
- Application (app)
- ApplicationId
- ErrorCode (result)
- LogonType
- ClientAppUsed
- ConditionalAccessStatus
- RiskLevelDuringSignIn
- UserAgent
- DeviceName
- ReportId

### IdentityLogonEvents
Product: Microsoft Defender for Identity
Time field: Timestamp
- Timestamp
- AccountUpn
- AccountName
- DeviceName
- IPAddress
- ActionType
- LogonType
- Protocol
- FailureReason
- DestinationDeviceName

### AlertInfo
Product: Microsoft Defender XDR
Time field: Timestamp
- Timestamp
- AlertId (alert_id)
- Title
- Category
- Severity
- ServiceSource
- DetectionSource
- AttackTechniques

### AlertEvidence
Product: Microsoft Defender XDR
Time field: Timestamp
- Timestamp
- AlertId
- EntityType
- EvidenceRole
- AccountUpn
- DeviceName
- RemoteIP
- RemoteUrl
- FileName
- SHA256

## Investigation Notes
- Fabrikam has no Sentinel. Use Advanced Hunting tables only (30 days retention).
- Sign-in error code 0 means success in AADSignInEventsBeta.
- All phishing reports must include the full recipient list.

## KQL Guidelines
- Use Timestamp, never TimeGenerated.
- Do not reference SigninLogs or AuditLogs; they do not exist in this tenant.

## Ticket Requirements
- Include the AlertId if the event came from a Defender alert.
