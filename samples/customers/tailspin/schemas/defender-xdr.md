# Tailspin Toys: Microsoft Defender XDR (Advanced Hunting)

Tables grouped by the Defender portal's Schema categories. List format with role hints in brackets.

## Alerts & behaviors

### AlertInfo
Product: Microsoft Defender XDR
Category: Alerts & behaviors
Time field: Timestamp
Description: Alerts from Defender products.
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
Category: Alerts & behaviors
Time field: Timestamp
Description: Entities attached to alerts.
- Timestamp
- AlertId (alert_id)
- EntityType
- EvidenceRole
- DeviceName
- AccountUpn
- RemoteIP
- FileName
- SHA256
- RemoteUrl

## Apps & identities

### IdentityLogonEvents
Product: Microsoft Defender for Identity
Category: Apps & identities
Time field: Timestamp
Description: Authentication against on-prem AD and Entra ID.
- Timestamp
- AccountUpn
- AccountName
- AccountDomain
- DeviceName
- IPAddress
- ActionType
- LogonType
- Protocol
- FailureReason
- DestinationDeviceName

### CloudAppEvents
Product: Microsoft Defender for Cloud Apps
Category: Apps & identities
Time field: Timestamp
Description: Activity in cloud apps, including OAuth consent.
- Timestamp
- ActionType
- Application
- AccountDisplayName
- AccountObjectId
- IPAddress
- CountryCode
- ObjectName
- ObjectType
- RawEventData
- UserAgent

## Email & collaboration

### EmailEvents
Product: Microsoft Defender for Office 365
Category: Email & collaboration
Time field: Timestamp
Description: Delivered and blocked mail.
- Timestamp
- NetworkMessageId
- SenderFromAddress
- SenderIPv4
- RecipientEmailAddress
- Subject
- DeliveryAction
- ThreatTypes
- UrlCount
- AttachmentCount

### UrlClickEvents
Product: Microsoft Defender for Office 365
Category: Email & collaboration
Time field: Timestamp
Description: Safe Links clicks.
- Timestamp
- Url
- ActionType
- AccountUpn
- NetworkMessageId
- IPAddress
- IsClickedThrough

## Devices

### DeviceProcessEvents
Product: Microsoft Defender for Endpoint
Category: Devices
Time field: Timestamp
Description: Process creation.
- Timestamp
- DeviceId
- DeviceName
- AccountName
- AccountDomain
- FileName
- FolderPath
- SHA256
- ProcessCommandLine
- InitiatingProcessFileName
- InitiatingProcessCommandLine

### DeviceFileEvents
Product: Microsoft Defender for Endpoint
Category: Devices
Time field: Timestamp
Description: File creation, modification, rename and deletion.
- Timestamp
- DeviceId
- DeviceName
- ActionType
- FileName
- FolderPath
- PreviousFileName
- SHA256
- InitiatingProcessAccountName
- InitiatingProcessFileName
- RequestAccountName
- ShareName

### DeviceLogonEvents
Product: Microsoft Defender for Endpoint
Category: Devices
Time field: Timestamp
Description: Logons on devices.
- Timestamp
- DeviceId
- DeviceName
- AccountName
- AccountDomain
- LogonType
- ActionType
- RemoteIP
- RemoteDeviceName
- FailureReason
