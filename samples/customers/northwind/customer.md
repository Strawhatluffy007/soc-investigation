# Customer: Northwind Traders

## Environment
- Microsoft Sentinel workspace: northwind-sentinel (Log Analytics); no Defender XDR licence
- Identity: Microsoft Entra ID (cloud only), Microsoft 365 E3
- Perimeter: Palo Alto firewalls sending CEF to Sentinel (CommonSecurityLog) and Azure Firewall in the hub VNet
- Head office egress: 203.0.113.0/27; warehouse sites egress: 198.51.100.64/26
- Custom table PaloAltoThreat_CL from a Logstash pipeline (threat log fields only)

## Settings
- default_lookback: 14d
- event_window: 6h
- allow_external_llm: true
- kql_require_time_filter: true
- schema_scope: all

## Custom Tables

### PaloAltoThreat_CL
Product: Palo Alto Networks (Logstash)
Time field: TimeGenerated
Description: Threat log entries from the perimeter firewalls, parsed by Logstash.
- TimeGenerated
- SrcAddr (ip)
- DstAddr
- SrcUser_s (user)
- Threat_s
- ThreatCategory_s
- Severity_s
- Action_s (result)
- Url_s (url)
- DeviceName_s (device)

## Investigation Notes
- 203.0.113.0/27 and 198.51.100.64/26 are Northwind egress ranges and are expected sign-in sources.
- Mail forwarding to external domains is prohibited by policy; any new forwarding rule is at least Medium severity.
- Warehouse scanners (hosts named WH-SCN-*) talk only to 10.20.0.0/16; outbound internet traffic from them is suspicious.
- Azure subscription changes outside the change window (Mon-Fri 08:00-18:00 UTC) must be checked with the cloud team.

## KQL Guidelines
- Use TimeGenerated for all tables.
- Prefer `has` over `contains` on CommonSecurityLog for performance.
- Custom tables end in _CL; their string columns end in _s.

## Ticket Requirements
- Ticket title format: "[Northwind] <event type> - <user, host or IP>".
- Always list the firewall action (allowed / blocked) for network events.
- Do not paste full mail bodies into tickets; reference the message ID.
