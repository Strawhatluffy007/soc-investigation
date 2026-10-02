# Customer: Tailspin Toys

## Environment
- Microsoft Defender XDR (Advanced Hunting) with Defender for Endpoint P2, Defender for Identity, Defender for Office 365 P2 and Defender for Cloud Apps
- No Sentinel workspace: use Advanced Hunting tables and the Timestamp column only
- Identity: on-prem AD (tailspin.local) synced to Microsoft Entra ID
- Domain controllers: TS-DC01, TS-DC02; file server: TS-FS01 (finance and design shares)
- Remote access: Always On VPN pool 10.99.0.0/16

## Settings
- default_lookback: 7d
- event_window: 2h
- allow_external_llm: false
- kql_require_time_filter: true
- kql_forbidden_tables: SecurityEvent, Syslog, SigninLogs

## Investigation Notes
- External LLM processing is not allowed under the Tailspin contract. Use the local rules engine only.
- Mass file renames or modifications on TS-FS01 (more than 200 files in 5 minutes by one account) must be treated as possible ransomware and escalated immediately.
- Service accounts start with svc-; interactive logons by them are always suspicious.
- OAuth consent to apps from unverified publishers needs approval from the identity team.

## KQL Guidelines
- Use Timestamp (not TimeGenerated) for every table.
- Join device events on DeviceId, not DeviceName.
- Limit result sets with `take 1000` while exploring.

## Ticket Requirements
- Ticket title format: "[Tailspin] <event type> - <device or account>".
- For ransomware suspicion state whether the device was isolated and by whom.
- Never include file share contents or file names from the finance share; give counts only.
