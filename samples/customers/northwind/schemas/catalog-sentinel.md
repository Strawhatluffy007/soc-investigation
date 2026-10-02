# Northwind Traders: Microsoft Sentinel (Log Analytics)

<!-- Sample of a file written by Customer config → Schema selection → Apply (tables grouped by category). -->

Id: sentinel
Origin: microsoft
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables-index
Time field: TimeGenerated

## Alerts & behaviors

### SecurityIncident
Product: Microsoft Sentinel
Category: Alerts & behaviors
Time field: TimeGenerated
Description: Incidents created in Microsoft Sentinel.

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | When the incident record was written |
| IncidentNumber | int | Incident number shown in the portal |
| Title | string | Incident title |
| Severity | string | High, Medium, Low or Informational |
| Status | string | New, Active or Closed |
| Owner | dynamic | Assigned owner |
| AlertIds | dynamic | Alerts in the incident |
| IncidentUrl | string | Link to the incident in the portal |

## Apps & identities

### SigninLogs
Product: Microsoft Entra ID
Category: Apps & identities
Time field: TimeGenerated
Description: Interactive user sign-ins.

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | Sign-in time |
| UserPrincipalName | string | User principal name |
| IPAddress | string | Client IP address |
| Location | string | Country or region of the sign-in |
| AppDisplayName | string | Application name |
| ClientAppUsed | string | Client app (browser, mobile, legacy protocol) |
| ResultType | string | 0 for success, otherwise the error code |
| ResultDescription | string | Error description |
| ConditionalAccessStatus | string | success, failure or notApplied |
| UserAgent | string | User agent |
| RiskLevelDuringSignIn | string | Risk level at sign-in |
| CorrelationId | string | Correlation id |

### OfficeActivity
Product: Microsoft 365
Category: Apps & identities
Time field: TimeGenerated
Description: Exchange Online, SharePoint and Teams audit events.

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | Event time |
| UserId | string | User who performed the action |
| Operation | string | Operation name, e.g. New-InboxRule, Set-Mailbox |
| OfficeWorkload | string | Exchange, SharePoint, OneDrive or Teams |
| ResultStatus | string | Result of the operation |
| ClientIP | string | Client IP address |
| Parameters | string | Cmdlet parameters (Exchange) |
| OfficeObjectId | string | Object the action applied to |
| SourceFileName | string | File name (SharePoint / OneDrive) |

## Network

### CommonSecurityLog
Product: CEF (Palo Alto Networks)
Category: Network
Time field: TimeGenerated
Description: Common Event Format logs from network appliances.

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | Event time |
| DeviceVendor | string | Appliance vendor |
| DeviceProduct | string | Appliance product |
| DeviceName | string | Appliance host name |
| Activity | string | Event name |
| DeviceAction | string | allow, deny, drop, reset |
| SourceIP | string | Source IP |
| SourcePort | int | Source port |
| DestinationIP | string | Destination IP |
| DestinationPort | int | Destination port |
| SourceUserName | string | Source user |
| RequestURL | string | URL requested |
| ApplicationProtocol | string | Application |
| LogSeverity | string | Severity |

## Cloud infrastructure

### AzureActivity
Product: Azure Resource Manager
Category: Cloud infrastructure
Time field: TimeGenerated
Description: Control-plane operations on Azure resources.

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | Event time |
| Caller | string | User or service principal that made the change |
| CallerIpAddress | string | Caller IP |
| OperationNameValue | string | Operation, e.g. MICROSOFT.COMPUTE/VIRTUALMACHINES/WRITE |
| ActivityStatusValue | string | Start, Success or Failure |
| ResourceGroup | string | Resource group |
| _ResourceId | string | Resource id |
| SubscriptionId | string | Subscription |

## Threat intelligence

### AZFWThreatIntel
Product: Azure Firewall
Category: Threat intelligence
Time field: TimeGenerated
Description: Azure Firewall threat intelligence hits.

| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | Event time |
| SourceIp | string | Source IP |
| DestinationIp | string | Destination IP |
| DestinationPort | int | Destination port |
| Fqdn | string | Destination FQDN |
| Action | string | Allow or Deny |
| ThreatDescription | string | Threat intelligence description |
| Protocol | string | Protocol |
