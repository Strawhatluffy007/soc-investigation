# Contoso: Defender XDR tables (streamed to Sentinel)

### DeviceProcessEvents
Product: Microsoft Defender for Endpoint
Time field: TimeGenerated
- TimeGenerated
- DeviceName
- DeviceId
- AccountName
- AccountDomain
- ActionType
- FileName
- FolderPath
- SHA256
- SHA1
- MD5
- ProcessCommandLine
- InitiatingProcessFileName
- InitiatingProcessCommandLine
- InitiatingProcessAccountName

### DeviceNetworkEvents
Product: Microsoft Defender for Endpoint
Time field: TimeGenerated
- TimeGenerated
- DeviceName
- ActionType
- RemoteIP
- RemotePort
- RemoteUrl
- LocalIP
- Protocol
- InitiatingProcessFileName
- InitiatingProcessCommandLine
- InitiatingProcessAccountName

### EmailEvents
Product: Microsoft Defender for Office 365
Time field: TimeGenerated
- TimeGenerated
- NetworkMessageId
- SenderFromAddress
- SenderMailFromAddress
- SenderIPv4
- RecipientEmailAddress
- Subject
- DeliveryAction
- DeliveryLocation
- ThreatTypes
- UrlCount
- AttachmentCount
