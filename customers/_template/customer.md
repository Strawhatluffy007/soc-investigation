# Customer: {{customer_name}}

## Environment
- Microsoft Sentinel workspace: <name>
- Microsoft Defender XDR: <yes/no>
- Identity: Microsoft Entra ID

## Settings
- default_lookback: 7d
- event_window: 1d
- allow_external_llm: false
- kql_require_time_filter: true
- kql_forbidden_tables:

## Sentinel Tables

### SigninLogs
Product: Microsoft Entra ID
Time field: TimeGenerated
- TimeGenerated
- UserPrincipalName
- IPAddress
- Location
- AppDisplayName
- ResultType
- ResultDescription
- ConditionalAccessStatus

## Investigation Notes
- Add customer-specific steps here, e.g. "VPN egress range 203.0.113.0/24 is expected".

## KQL Guidelines
- Always filter on the time field first.

## Ticket Requirements
- Severity must be set by the analyst.
