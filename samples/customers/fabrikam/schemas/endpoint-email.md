# Fabrikam: Endpoint and email tables (Advanced Hunting)

### DeviceProcessEvents
Product: Microsoft Defender for Endpoint
Time field: Timestamp
- Timestamp
- DeviceName
- DeviceId
- AccountName
- AccountUpn
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
- ReportId

### DeviceNetworkEvents
Product: Microsoft Defender for Endpoint
Time field: Timestamp
- Timestamp
- DeviceName
- ActionType
- RemoteIP
- RemotePort
- RemoteUrl
- LocalIP
- Protocol
- InitiatingProcessFileName
- InitiatingProcessCommandLine

### DeviceFileEvents
Product: Microsoft Defender for Endpoint
Time field: Timestamp
- Timestamp
- DeviceName
- ActionType
- FileName
- FolderPath
- SHA256
- FileOriginUrl
- InitiatingProcessFileName

### EmailEvents
Product: Microsoft Defender for Office 365
Time field: Timestamp
- Timestamp
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

### EmailUrlInfo
Product: Microsoft Defender for Office 365
Time field: Timestamp
- Timestamp
- NetworkMessageId
- Url
- UrlDomain
