# Customer: Woodgrove Bank

<!-- Fictional sample customer. All names, domains and IPs are made up (RFC 5737 / RFC 3849 ranges). -->

## Environment
- Microsoft Sentinel workspace: law-woodgrove-soc-prod (UK South)
- Microsoft Defender XDR: yes (Defender for Endpoint P2, Defender for Office 365 P2, Defender for Identity)
- Identity: Microsoft Entra ID, hybrid with on-prem AD (woodgrove.local); MFA enforced via Conditional Access
- Mail domain: woodgrovebank.com
- Endpoints: ~1,800 Windows 11 laptops, 120 Windows Server 2022, macOS for design team
- Remote access: Always-On VPN, egress 198.51.100.0/27; branch offices egress 203.0.113.64/26

## Settings
- default_lookback: 7d
- event_window: 1d
- allow_external_llm: true
- kql_require_time_filter: true
- kql_forbidden_tables: SecurityEvent
- schema_scope: selected

## Investigation Notes
- VPN egress 198.51.100.0/27 and branch range 203.0.113.64/26 are expected sources for sign-ins.
- Break-glass accounts (bg-admin01@woodgrovebank.com, bg-admin02@woodgrovebank.com) must never sign in; any sign-in is High severity.
- Payments team (group "SG-Payments") handles SWIFT; treat any alert on their devices as at least Medium.
- Service accounts start with svc- and should only log on to servers (DeviceName starting WGB-SRV-).
- Escalate confirmed compromise to the Woodgrove on-call: soc-escalation@woodgrovebank.com (fictional).

## KQL Guidelines
- Always filter on the time field first (Timestamp in Defender XDR, TimeGenerated in Sentinel).
- Prefer Defender XDR tables for endpoint and email; use Sentinel SigninLogs/AuditLogs for identity.
- SecurityEvent is not collected for this customer (forbidden) - use DeviceLogonEvents / IdentityLogonEvents.
- Limit result sets with `take 100` or `summarize` while scoping.

## Ticket Requirements
- Severity must be set by the analyst.
- Reference the Defender incident ID when one exists.
- Include the affected user's department (from IdentityInfo) when known.
- Never include passwords, tokens or full email bodies.
