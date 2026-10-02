# Woodgrove Bank: Microsoft Sentinel (Log Analytics)

<!-- Generated from the schema catalog on 2026-10-02T19:19+00:00. Change it in Customer config → Schema selection; manual edits are overwritten on the next apply. -->

Id: sentinel
Origin: microsoft
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables-category
Time field: TimeGenerated

## Alerts & behaviors

### SecurityAlert
Product: Microsoft Sentinel (Log Analytics)
Category: Alerts & behaviors
Time field: TimeGenerated
Description: Categories: Security; Solutions: AzureSecurityOfThings, Security, SecurityCenter, SecurityCenterFree, SecurityInsights
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/securityalert

| Column | Type | Description |
|---|---|---|
| AlertLink | string |  |
| AlertName | string |  |
| AlertSeverity | string |  |
| AlertType | string |  |
| _BilledSize | real | The record size in bytes |
| CompromisedEntity | string |  |
| ConfidenceLevel | string |  |
| ConfidenceScore | real |  |
| Description | string |  |
| DisplayName | string |  |
| EndTime | datetime |  |
| Entities | string |  |
| ExtendedLinks | string |  |
| ExtendedProperties | string |  |
| _IsBillable | string | Specifies whether ingesting the data is billable. When _IsBillable is false ingestion isn't billed to your Azure account |
| IsIncident | bool |  |
| ProcessingEndTime | datetime |  |
| ProductComponentName | string |  |
| ProductName | string |  |
| ProviderName | string |  |
| RemediationSteps | string |  |
| ResourceId | string |  |
| SourceComputerId | string |  |
| StartTime | datetime |  |
| Status | string |  |
| SubTechniques | string |  |
| SystemAlertId | string |  |
| Tactics | string |  |
| Techniques | string |  |
| TimeGenerated | datetime |  |
| Type | string | The name of the table |
| VendorName | string |  |
| VendorOriginalId | string |  |
| WorkspaceResourceGroup | string |  |
| WorkspaceSubscriptionId | string |  |

## Apps & identities

### AuditLogs
Product: Microsoft Sentinel (Log Analytics)
Category: Apps & identities
Time field: TimeGenerated
Description: Categories: Azure Resources, Security; Solutions: LogManagement
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/auditlogs

| Column | Type | Description |
|---|---|---|
| AADOperationType | string | Type of the operation. Possible values are Add Update Delete and Other. |
| AADTenantId | string | ID of the ADD tenant |
| ActivityDateTime | datetime | Date and time the activity was performed in UTC. |
| ActivityDisplayName | string | Activity name or the operation name. Examples include Create User and Add member to group. For full list see Azure AD activity list. |
| AdditionalDetails | dynamic | Indicates additional details on the activity. |
| _BilledSize | real | The record size in bytes |
| Category | string | Currently Audit is the only supported value. |
| CorrelationId | string | Optional GUID that's passed by the client. Can help correlate client-side operations with server-side operations and is useful when tracking logs that span services. |
| DurationMs | long | Property is not used and can be ignored. |
| Id | string | GUID that uniquely identifies the activity. |
| Identity | string | Identity from the token that was presented when the request was made. The identity can be a user account system account or service principal. |
| InitiatedBy | dynamic | User or app initiated the activity. |
| _IsBillable | string | Specifies whether ingesting the data is billable. When _IsBillable is false ingestion isn't billed to your Azure account |
| Level | string | Message type. This is currently always Informational. |
| Location | string | Location of the datacenter. |
| LoggedByService | string | Service that initiated the activity (For example: Self-service Password Management Core Directory B2C Invited Users Microsoft Identity Manager Privileged Identity Management. |
| OperationName | string | Name of the operation. |
| OperationVersion | string | REST API version that's requested by the client. |
| Resource | string |  |
| ResourceGroup | string |  |
| ResourceId | string |  |
| ResourceProvider | string |  |
| Result | string | Result of the activity. Possible values are: success failure timeout unknownFutureValue. |
| ResultDescription | string | Additional description of the result. |
| ResultReason | string | Describes cause of failure or timeout results. |
| ResultSignature | string | Property is not used and can be ignored. |
| ResultType | string | Result of the operation. Possible values are Success and Failure. |
| SourceSystem | string | The type of agent the event was collected by. For example, OpsManager for Windows agent, either direct connect or Operations Manager, Linux for all Linux agents, or Azure for Azure Diagnostics |
| TargetResources | dynamic | Indicates information on which resource was changed due to the activity. Target Resource Type can be User Device Directory App Role Group Policy or Other. |
| TimeGenerated | datetime | Date and time the record was created. |
| Type | string | The name of the table |

### OfficeActivity
Product: Microsoft Sentinel (Log Analytics)
Category: Apps & identities
Time field: TimeGenerated
Description: Categories: Security; Solutions: AzureSentinelPrivatePreview, SecurityInsights
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/officeactivity

| Column | Type | Description |
|---|---|---|
| AADGroupId | string | Microsoft Entra ID group id |
| AADTarget | string | The user that the action (identified by the Operation property) was performed on |
| Activity | string | The activity that the user performed. |
| Actor | string | The user or service principal that performed the action |
| ActorContextId | string | The GUID of the organization that the actor belongs to |
| ActorIpAddress | string | The actor's IP address in IPV4 or IPV6 address format |
| AddOnGuid | string | The unique identifier of the add-on generated this event |
| AddonName | string | The name of the add-on that generated this event |
| AddOnType | string | The type of add-on that generated this event |
| AffectedItems | string | Information about each item in the group |
| AppAccessContext | dynamic | The application context for the user or service principal that performed the action. |
| AppDistributionMode | string | Application distribution mode |
| AppId | string | Application ID |
| Application | string | The application name |
| ApplicationId | string | SharePoint application ID |
| AppPoolName | string | The App pool name |
| ArtifactsShared | dynamic | The artifacts shared in the meeting. |
| Attendees | dynamic | The list of attendees for the meeting. |
| AzureActiveDirectory_EventType | string | The type of Azure AD event |
| AzureADAppId | string | Teams Application Azure AD ID |
| _BilledSize | real | The record size in bytes |
| ChannelGuid | string | A unique identifier for the channel being audited |
| ChannelName | string | The name of the channel being audited |
| ChannelType | string | The type of channel being audited (Standard/Private) |
| ChatName | string | The name of the chat |
| ChatThreadId | string | The Id of the chat thread |
| Client | string | Details about the client device, device OS, and device browser that was used for the of the account login event |
| Client_IPAddress | string | The IP address of the device that was used when the operation was logged |
| ClientAppId | string | Client application ID |
| ClientInfoString | string | Information about the email client that was used to perform the operation |
| ClientIP | string | The IP address of the device that was used when the activity was logged |
| ClientMachineName | string | The machine name that hosts the Outlook client |
| ClientProcessName | string | The email client that was used to access the mailbox |
| ClientVersion | string | The version of the email client |
| CommunicationType | string | The type of communications that was conducted |
| CrossMailboxOperations | bool | Indicates if the operation involved more than one mailbox |
| CustomEvent | string | Optional string for custom events |
| DataCenterSecurityEventType | int | The type of dmdlet event in lock box |
| DestFolder | string | The destination folder |
| DestinationFileExtension | string | The file extension of a file that is copied or moved |
| DestinationFileName | string | The name of the file that is copied or moved |
| DestinationRelativeUrl | string | The URL of the destination folder where a file is copied or moved |
| DestMailboxId | string | Set only if the CrossMailboxOperations parameter is True |
| DestMailboxOwnerMasterAccountSid | string | Set only if the CrossMailboxOperations parameter is True |
| DestMailboxOwnerSid | string | Set only if the CrossMailboxOperations parameter is True |
| DestMailboxOwnerUPN | string | Set only if the CrossMailboxOperations parameter is True |
| DeviceInformation | string | The user device information. |
| EffectiveOrganization | string | The name of the tenant that the elevation/cmdlet was targeted at |
| ElevationApprovedTime | datetime | The timestamp for when the elevation was approved |
| ElevationApprover | string | The name of a Microsoft manager |
| ElevationDuration | int | The duration for which the elevation was active (in Hours) |
| ElevationRequestId | string | A unique identifier for the elevation request |
| ElevationRole | string | The role the elevation was requested for |
| ElevationTime | datetime | The start time of the elevation |
| Event_Data | string | Optional payload for custom events |
| EventSource | string | Identifies that an event occurred in SharePoint. Possible values are SharePoint or ObjectModel |
| ExtendedProperties | string | The extended properties of the Azure AD event |
| ExternalAccess | string | Specifies whether the cmdlet was run by a user in your organization |
| ExtraProperties | dynamic | A list of extra properties |
| Folder | string | The folder where a group of items is located |
| Folders | string | Information about the source folders involved in an operation |
| GenericInfo | string | Used for comments and other generic information |
| InternalLogonType | int | Reserved for internal use |
| InterSystemsId | string | The GUID that track the actions across components within the Office 365 service |
| IntraSystemId | string | The GUID that's generated by Microsoft Entra ID to track the action |
| _IsBillable | string | Specifies whether ingesting the data is billable. When _IsBillable is false ingestion isn't billed to your Azure account |
| IsJoinedFromLobby | bool | Indicates whether the user join from the lobby. |
| IsManagedDevice | bool | Indicates if operation was created by a device managed by the organization |
| Item | string | Represents the item upon which the operation was performed |
| ItemName | string | The string in the Subject field of the email message |
| ItemType | string | The type of object that was accessed or modified. See the ItemType table for details on the types of objects |
| JoinTime | datetime | The time the user joined the meeting. |
| LeaveTime | datetime | The time the user left the meeting. |
| ListItemUniqueId | string | The Guid of uniquely an identifiable item of list. This information is present only if it is applicable. |
| LoginStatus | int | This property is from OrgIdLogon.LoginStatus directly. The mapping of various interesting logon failures could be done by alerting algorithms |
| Logon_Type | string | Indicates the type of user who accessed the mailbox and performed the operation that was logged |
| LogonUserDisplayName | string | The user-friendly name of the user who performed the operation |
| LogonUserSid | string | The SID of the user who performed the operation |
| MachineDomainInfo | string | Information about device sync operations |
| MachineId | string | Information about device sync operations |
| MailboxGuid | string | The Exchange GUID of the mailbox that was accessed |
| MailboxOwnerMasterAccountSid | string | Mailbox owner account's master account SID |
| MailboxOwnerSid | string | The SID of the mailbox owner |
| MailboxOwnerUPN | string | The email address of the person who owns the mailbox that was accessed |
| MeetingDetailId | string | The meeting detail ID. |
| Members | dynamic | A list of users within a Team |
| MessageId | string | An identifier for a chat or channel message |
| ModifiedObjectResolvedName | string | This is the user friendly name of the object that was modified by the cmdlet |
| ModifiedProperties | string | The property is included for admin events, such as adding a user as a member of a site or a site collection admin group |
| Name | string | Only present for settings events. Name of the setting that changed |
| NewValue | string | Only present for settings events. New value of the setting |
| OfficeId | string | Unique identifier of an audit record |
| OfficeObjectId | string | For SharePoint and OneDrive for Business activity |
| OfficeTenantId | string | The office tenant id |
| OfficeWorkload | string | The Office 365 service where the activity occurred |
| OldValue | string | Only present for settings events. Old value of the setting |
| Operation | string | The name of the operation that the user is performing |
| OperationProperties | dynamic | Additional operation properties |
| OperationScope | string | The scope the operation was performed on |
| OrganizationId | string | The GUID for your organization's Office 365 tenant. This value will always be the same for your organization |
| OrganizationName | string | The name of the tenant |
| OriginatingServer | string | The name of the server from which the cmdlet was executed |
| Parameters | string | The name and value for all parameters that were used with the cmdlet that is identified in the Operations property |
| RecordType | string | The type of operation indicated by the record. See the AuditLogRecordType table for details on the types of audit log records |
| _ResourceId | string | A unique identifier for the resource that the record is associated with |
| ResultReasonType | string | Reason for the result reported in ResultType |
| ResultStatus | string | Indicates whether the action (specified in the Operation property) was successful or not |
| SendAsUserMailboxGuid | string | The Exchange GUID of the mailbox that was accessed to send email as |
| SendAsUserSmtp | string | SMTP address of the user who is being impersonated |
| SendonBehalfOfUserMailboxGuid | string | The Exchange GUID of the mailbox that was accessed to send mail on behalf of |
| SendOnBehalfOfUserSmtp | string | SMTP address of the user on whose behalf the email is sent |
| SensitivityLabelId | string | The current sensitivity label ID of the file. |
| SharingType | string | The type of sharing permissions that were assigned to the user that the resource was shared with. This user is identified by the UserSharedWith parameter |
| Site_ | string | The GUID of the site where the file or folder accessed by the user is located |
| Site_Url | string | The URL of the site where the file or folder accessed by the user is located |
| Source_Name | string | The entity that triggered the audited operation. Possible values are SharePoint or ObjectModel |
| SourceFileExtension | string | The file extension of the file that was accessed by the user |
| SourceFileName | string | The name of the file or folder accessed by the user |
| SourceRecordId | string | Unique identifier of an audit record |
| SourceRelativeUrl | string | The URL of the folder that contains the file accessed by the user |
| SourceSystem | string | The type of agent the event was collected by. For example, OpsManager for Windows agent, either direct connect or Operations Manager, Linux for all Linux agents, or Azure for Azure Diagnostics |
| SRPolicyId | string | Policy ID |
| SRPolicyName | string | Policy name |
| SRRuleMatchDetails | dynamic | Rule details |
| Start_Time | datetime | The date and time at which the cmdlet was executed |
| _SubscriptionId | string | A unique identifier for the subscription that the record is associated with |
| SupportTicketId | string | The customer support ticket ID for the action in 'act-on-behalf-of' situations |
| TabType | string | The type of tab that generated this event |
| TargetContextId | string | The GUID of the organization that the targeted user belongs to |
| TargetUserId | string | Target user id |
| TargetUserOrGroupName | string | Stores the UPN or name of the target user or group that a resource was shared with |
| TargetUserOrGroupType | string | Identifies whether the target user or group is a Member, Guest, Group, or Partner |
| TeamGuid | string | A unique identifier for the team being audited |
| TeamName | string | The name of the team being audited |
| TenantId | string | The Log Analytics workspace ID |
| TimeGenerated | datetime | The date and time in Coordinated Universal Time (UTC) when the user performed the activity |
| Type | string | The name of the table |
| UniqueSharingId | string | The unique sharing ID associated with the sharing operation. |
| UserAgent | string | The user agent |
| UserDomain | string | The domain of the user |
| UserId | string | The UPN (User Principal Name) of the user who performed the action (specified in the Operation property) that resulted in the record being logged |
| UserKey | string | An alternative ID for the user identified in the UserId property |
| UserSharedWith | string | The user that a resource was shared with |
| UserType | string | The type of user that performed the operation. See the UserType table for details on the types of users |

### SigninLogs
Product: Microsoft Sentinel (Log Analytics)
Category: Apps & identities
Time field: TimeGenerated
Description: Categories: Azure Resources, Security; Solutions: LogManagement
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/signinlogs

| Column | Type | Description |
|---|---|---|
| AADTenantId | string |  |
| Agent | dynamic | The agentic property for sign in logs. Includes the agentType and the parentAppId when the type is AgenticInstance. |
| AlternateSignInName | string | The identification that the user provided to sign in. It may be the userPrincipalName but it's also populated when a user signs in using other identifiers. |
| AppDisplayName | string | The application name displayed in the Azure Portal. |
| AppId | string | The application identifier in Microsoft Entra ID. |
| AppliedConditionalAccessPolicies | string |  |
| AppliedEventListeners | dynamic | Detailed information about the listeners, such as Azure Logic Apps and Azure Functions, that were triggered by the corresponding events in the sign-in event. |
| AppOwnerTenantId | string | The tenant identifier of the owenr of the application in Microsoft Entra ID. |
| AuthenticationAppDeviceDetails | string | Details of the app and device state used during the most recent authentication step using an authentication app. |
| AuthenticationAppPolicyEvaluationDetails | string | The details of the policies applied and enforced related to the authentication app during the latest signIn step. |
| AuthenticationContextClassReferences | string | Contains a collection of values that represent the conditional access authentication contexts applied to the sign-in. |
| AuthenticationDetails | string | The result of the authentication attempt and additional details on the authentication method. |
| AuthenticationMethodsUsed | string | The authentication methods used. Possible values: SMS, Authenticator App, App Verification code, Password, FIDO, PTA, or PHS. |
| AuthenticationProcessingDetails | string | Additional authentication processing details, such as the agent name in case of PTA/PHS or Server/farm name in case of federated authentication. |
| AuthenticationProtocol | string | Lists the protocol type or grant type used in the authentication. The possible values are: none, oAuth2, ropc, wsFederation, saml20, deviceCode. For authentications that use protocols other than the p |
| AuthenticationRequirement | string | This holds the highest level of authentication needed through all the sign-in steps, for sign-in to succeed. |
| AuthenticationRequirementPolicies | string | Sources of authentication requirement, such as conditional access, per-user MFA, identity protection, and security defaults. |
| AuthenticatorAppLocation | string | The location of the authenticator app. |
| AutonomousSystemNumber | string | The Autonomous System Number (ASN) of the network used by the actor. |
| _BilledSize | real | The record size in bytes |
| Category | string |  |
| ClientAppUsed | string | The legacy client used for sign-in activity. For example: Browser, Exchange ActiveSync, Modern clients, IMAP, MAPI, SMTP, or POP. |
| ClientCredentialType | string | The type of client credential used. Examples include client assertion, client secret, etc. |
| ClientSessionId | string | ID of the client session associated with the signIn. |
| ConditionalAccessAudiences | string | The audiences targeted by the conditional access policy. |
| ConditionalAccessPolicies | dynamic | A list of conditional access policies that are triggered by the corresponding sign-in activity. |
| ConditionalAccessStatus | string | The status of the conditional access policy triggered. Possible values: success, failure, or notApplied. |
| CorrelationId | string | The identifier that's sent from the client when sign-in is initiated. This is used for troubleshooting the corresponding sign-in activity when calling for support. |
| CreatedDateTime | datetime | The date and time the sign-in was initiated. The Timestamp type is always in UTC time. For example, midnight UTC on Jan 1, 2014 is 2014-01-01T00:00:00Z. |
| CrossTenantAccessType | string | Describes the type of cross-tenant access used by the actor to access the resource. |
| DeviceDetail | dynamic | The device information from where the sign-in occurred. Includes information such as deviceId, OS, and browser. |
| DurationMs | long |  |
| FederatedCredentialId | string | Federated Credential Id. |
| FlaggedForReview | bool | During a failed sign in, a user may click a button in the Azure portal to mark the failed event for tenant admins. If a user clicked the button to flag the failed sign in, this value is true. |
| GlobalSecureAccessIpAddress | string | Global secure IP address that user signed in from. |
| HomeTenantId | string | The tenant identifier of the user initiating the sign in. Not applicable in Managed Identity or service principal sign ins. |
| HomeTenantName | string | The tenant name of the external tenant who homes the entitity taking action in the customer's tenant. |
| Id | string | The identifier representing the sign-in activity. |
| Identity | string | The display name of the actor identified in the signin. |
| IncomingTokenType | string | The type of token utilized to signIn (examples: primary refresh token, saml assertion). |
| IPAddress | string | The IP address of the client from where the sign-in occurred. |
| IPAddressFromResourceProvider | string | The IP address a user used to reach a resource provider, used to determine Conditional Access compliance for some policies. For example, when a user interacts with Exchange Online, the IP address Exch |
| _IsBillable | string | Specifies whether ingesting the data is billable. When _IsBillable is false ingestion isn't billed to your Azure account |
| IsInteractive | bool | Indicates whether a user sign in is interactive. In interactive sign in, the user provides an authentication factor to Azure AD. These factors include passwords, responses to MFA challenges, biometric |
| IsRisky | bool |  |
| IsTenantRestricted | bool | Indicates if a signIn is under a tenant restrictions policy or not. |
| IsThroughGlobalSecureAccess | bool | Displays whether or not a user came through Global Secure Access service or not. |
| Level | string |  |
| Location | string | The 2 letter country code from where the sign-in occurred. Depending on IP address provided, this value may not always resolve to a city or region level of detail. |
| LocationDetails | dynamic | Provides the city, state, country/region and latitude and longitude from where the sign-in happened. |
| MfaDetail | dynamic | This property is deprecated. |
| NetworkLocationDetails | string | The network location details including the type of network used and its names. |
| OperationName | string |  |
| OperationVersion | string |  |
| OriginalRequestId | string | The request identifier of the first request in the authentication sequence. |
| OriginalTransferMethod | string | Transfer method used to initiate a session throughout all subsequent requests. |
| ProcessingTimeInMilliseconds | string |  |
| Resource | string |  |
| ResourceDisplayName | string | The name of the resource that the user signed in to. |
| ResourceGroup | string |  |
| ResourceId | string | The identifier of the resource that the user signed in to. |
| ResourceIdentity | string | The resource that the user signed in to. |
| ResourceOwnerTenantId | string | The tenant identifier of the owner of the resource referenced in the sign in. |
| ResourceProvider | string |  |
| ResourceServicePrincipalId | string | The identifier of the service principal representing the target resource in the sign-in event. |
| ResourceTenantId | string | The tenant identifier of the resource referenced in the sign in. |
| ResultDescription | string | Provides the error message or the reason for failure for the corresponding sign-in activity. |
| ResultSignature | string |  |
| ResultType | string | Provides the 5-6 digit error code that's generated during a sign-in event. 0 indicates success; other values are failures. You can find more information using the Azure AD Error Codes documentation or |
| RiskDetail | string | The reason behind a specific state of a risky user, sign-in, or a risk event. Possible values: none, adminGeneratedTemporaryPassword, userPerformedSecuredPasswordChange, userPerformedSecuredPasswordRe |
| RiskEventTypes | string | This property is deprecated. |
| RiskEventTypes_V2 | string | The list of risk event types associated with the sign-in. Possible values: unlikelyTravel, anonymizedIPAddress, maliciousIPAddress, unfamiliarFeatures, malwareInfectedIPAddress, suspiciousIPAddress, l |
| RiskLevel | string |  |
| RiskLevelAggregated | string | The aggregated risk level. Possible values: none, low, medium, high, or hidden. The value hidden means the user or sign-in was not enabled for Azure AD Identity Protection. Note: Details for this prop |
| RiskLevelDuringSignIn | string | The risk level during sign-in. Possible values: none, low, medium, high, or hidden. The value hidden means the user or sign-in was not enabled for Azure AD Identity Protection. Note: Details for this |
| RiskState | string | The risk state of a risky user, sign-in, or a risk event. Possible values: none, confirmedSafe, remediated, dismissed, atRisk, or confirmedCompromised. |
| RootActorID | string | The root actor virtual ID associated with the sign-in. |
| ServicePrincipalId | string | The application identifier used for sign-in. This field is populated when you are signing in using an application. |
| ServicePrincipalName | string | The application name used for sign-in. This field is populated when you are signing in using an application. |
| SessionId | string | Id of the session that was generated during the signIn. |
| SessionLifetimePolicies | string | Any conditional access session management policies that were applied during the sign-in event. |
| SignInIdentifier | string | The identification that the user provided to sign in. It may be the userPrincipalName but it's also populated when a user signs in using other identifiers. |
| SignInIdentifierType | string | The type of sign in identifier. Possible values are: userPrincipalName, phoneNumber, proxyAddress, qrCode, onPremisesUserPrincipalName. |
| SourceAppClientId | string | The Source App's Client ID for Target Identities. |
| SourceSystem | string | The type of agent the event was collected by. For example, OpsManager for Windows agent, either direct connect or Operations Manager, Linux for all Linux agents, or Azure for Azure Diagnostics |
| Status | dynamic | The sign-in status. Includes the error code and description of the error (in case of a sign-in failure). |
| TimeGenerated | datetime |  |
| TokenIssuerName | string | The name of the identity provider. For example, sts.microsoft.com. |
| TokenIssuerType | string | The type of identity provider. The possible values are: AzureAD, or ADFederationServices, AzureADBackupAuth, ADFederationServicesMFAAdapter, NPSExtension. |
| TokenProtectionStatusDetails | dynamic | Token protection creates a cryptographically secure tie between the token and the device it's issued to. This field indicates whether the signin token was bound to the device or not. |
| Type | string | The name of the table |
| UniqueTokenIdentifier | string | A unique base64 encoded request identifier used to track tokens issued by Azure AD as they are redeemed at resource providers. |
| UserAgent | string | The user agent information related to sign-in. |
| UserDisplayName | string | The display name of the user. |
| UserId | string | The identifier of the user. |
| UserPrincipalName | string | The UPN of the user. |
| UserType | string | Identifies whether the user is a member or guest in the tenant. Possible values are: member and guest. |

## Devices

### SecurityEvent
Product: Microsoft Sentinel (Log Analytics)
Category: Devices
Time field: TimeGenerated
Description: Categories: Security; Solutions: Security, SecurityInsights
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/securityevent

| Column | Type | Description |
|---|---|---|
| AccessMask | string | Hexadecimal mask for the requested or performed operation. |
| Account | string | The Security context for services or users. |
| AccountDomain | string | Subject's domain or computer name. |
| AccountExpires | string | The date when the account expires. |
| AccountName | string | The name of the account that requested the "remove domain trust" operation. |
| AccountSessionIdentifier | string | A unique identifier that is generated by the machine when the session is created. |
| AccountType | string | Identifies whether the account is a computer account (machine) or a user's. |
| Activity | string | The descriptive title of the event occurred. |
| AdditionalInfo | string | Additional information that is provided by the source, which do not mapped to other fields, represented by list. |
| AdditionalInfo2 | string | Additional information that is provided by the source, which do not mapped to other fields, represented by list. |
| AllowedToDelegateTo | string | The list of SPNs to which this account can present delegated credentials. |
| Attributes | string | Additional information about the event. |
| AuditPolicyChanges | string | Events that are generated when changes are made to the system audit policy or audit settings on a file or registry key. |
| AuditsDiscarded | int | Number of audit messages that were discarded. |
| AuthenticationLevel | int | Number of audit messages that were discarded. |
| AuthenticationPackageName | string | the name of loaded Authentication Package. The format is: DLL_PATH_AND_NAME: AUTHENTICATION_PACKAGE_NAME. |
| AuthenticationProvider | string | The identity of the provider responsible for the authentication process (can include a certificate authority, a username, a password authentication system, etc). |
| AuthenticationServer | string | The server in which located the authentication provider. |
| AuthenticationService | int | The service in which located the authentication provider. |
| AuthenticationType | string | the type of authentication that was used for the event (two-factor authentication, biometric authentication, etc). |
| AzureDeploymentID | string | Azure deployment ID of the cloud service the log belongs to. |
| _BilledSize | real | The record size in bytes |
| CACertificateHash | string | The hash value of the certificate authority's (CA) certificate that was used to authenticate the user who performed the event. |
| CalledStationID | string | Information about the ID of the station that initiated the action that led to the security event. |
| CallerProcessId | string | Hexadecimal Process ID of the process that attempted the logon. Process ID (PID) is a number used by the operating system to uniquely identify an active process. |
| CallerProcessName | string | Full path and the name of the executable for the process. |
| CallingStationID | string | Information about the ID of the station that initiated the action that led to the security event. |
| CAPublicKeyHash | string | Hash value that identifies the public key of a certification authority (CA) that issued a certificate. |
| CategoryId | string | The category of the security event that occurred (login attempt, data breach, etc). |
| CertificateDatabaseHash | string | Hash value that identifies the database that issued a certificate. |
| Channel | string | The channel to which the event was logged. |
| ClassId | string | 'Class Guid' attribute of device. |
| ClassName | string | 'Class' attribute of device. |
| ClientAddress | string | IP address of the computer from which the TGT request was received. |
| ClientIPAddress | string | IP address of the computer that initiated the action that led to the event. |
| ClientName | string | computer name from which the user was reconnected. Has 'Unknown' value for console session. |
| CommandLine | string | The command line arguments that were passed to an application or process that was involved in the event. |
| CompatibleIds | string | 'Compatible Ids' attribute of device. To see device properties, start Device Manager, open specific device properties, and click 'Details': |
| Computer | string | The name of the computer on which the event occurred. |
| Correlation | string | The activity identifiers that consumers can use to group related events together. |
| DCDNSName | string | The DNS name of the domain controller that was involved in the event. |
| DeviceDescription | string | the description of the device that was involved in the event. |
| DeviceId | string | The unique identifier of the device that was involved in the event. |
| DisplayName | string | It is a name, displayed in the address book for a particular account. This is usually the combination of the user's first name, middle initial, and last name. |
| Disposition | string | The event outcome/ resolution, such as whether the event was resolved or whether any action was taken in response to the event. |
| DomainBehaviorVersion | string | msDS-Behavior-Version domain attribute was modified. Numeric value. |
| DomainName | string | The name of removed trusted domain. |
| DomainPolicyChanged | string | Indicates whether any domain policies have been changed as part of the event (password policies, security policies, etc). |
| DomainSid | string | SID of the trust partner. This parameter might not be captured in the event, and in that case appears as 'NULL SID'. |
| EAPType | string | The type of Extensible Authentication Protocol (EAP) that was used for the event authentication process. |
| ElevatedToken | string | A 'Yes' or 'No' flag. If 'Yes', then the session this event represents is elevated and has administrator privileges. |
| ErrorCode | int | Contains error code for Failure events. For Success events this parameter has '0x0' value. |
| EventData | string | Event specific data associated with the event. |
| EventID | int | The identifier that the provider used to identify the event. |
| EventLevelName | string | The rendered message string of the level specified in the event. |
| EventRecordId | string | The record number assigned to the event when it was logged. |
| EventSourceName | string | The name of the software that logs the event (applicationor a succomponent). |
| ExtendedQuarantineState | string | The state of the network quarantine process, if applicable. Network quarantine is a process by which unauthorized devices are prevented from accessing a network until they meet certain security requir |
| FailureReason | string | textual explanation of Status field value. For this event, it typically has 'Account locked out' value. |
| FileHash | string | The hash value for any files that are were accessed or modified as part of the event, or any files that were used in the authentication or authorization process. |
| FilePath | string | Full path and filename of the key file on which the operation was performed. |
| FilePathNoUser | string | The path of any files that are related to the event, excluding the username or other user-specific information. |
| Filter | string | Filters that are used in the performed event. |
| ForceLogoff | string | '\Security Settings\Local Policies\Security Options\Network security: Force logoff when logon hours expire' group policy. |
| Fqbn | string | The fully qualified binary name (FQBN) for any files that are related to the event. |
| FullyQualifiedSubjectMachineName | string | The fully qualified domain name (FQDN) of the machine that initiated the event. |
| FullyQualifiedSubjectUserName | string | The username of the user or service that initiated the event in FQDN format. |
| GroupMembership | string | The list of group SIDs which logged account belongs to (member of). Event Viewer automatically tries to resolve SIDs and show the account name. If the SID cannot be resolved, you will see the source d |
| HandleId | string | Hexadecimal value of a handle to Object Name. This field can be used for correlation with other events. |
| HardwareIds | string | 'Hardware Ids' attribute of device. To see device properties, start Device Manager, open specific device properties, and click 'Details': |
| HomeDirectory | string | User's home directory. If homeDrive attribute is set and specifies a drive letter, homeDirectory should be a UNC path. The path must be a network UNC of the form \Server\Share\Directory. |
| HomePath | string | User's home path. The path must be a network UNC of the form \Server\Share\Directory. |
| InterfaceUuid | string | The unique identifier (UUID) for the network interface that was used for the event. |
| IpAddress | string | the network address (usually IPv4 or IPv6) associated with the event. |
| IpPort | string | The network port number associated with the event. |
| _IsBillable | string | Specifies whether ingesting the data is billable. When _IsBillable is false ingestion isn't billed to your Azure account |
| KeyLength | int | The length of NTLM Session Security key. Typically it has 128 bit or 56 bit length. |
| Keywords | string | A bitmask of the keywords defined in the event. |
| Level | string | Windows categorizes every event with a severity level. The levels in order of severity are information, verbose, warning, error and critical expressed in numbers. |
| LmPackageName | string | The name of the package or software component that is currently using the Local Security Authority (LSA) on the machine where the event is being generated. |
| LocationInformation | string | 'Location information' attribute of device. To see device properties, start Device Manager, open specific device properties, and click 'Details': |
| LockoutDuration | string | '\Security Settings\Account Policies\Account Lockout Policy\Account lockout duration' group policy. Numeric value. |
| LockoutObservationWindow | string | '\Security Settings\Account Policies\Account Lockout Policy\Reset account lockout counter after' group policy. Numeric value. |
| LockoutThreshold | string | '\Security Settings\Account Policies\Account Lockout Policy\Account lockout threshold' group policy. Numeric value. |
| LoggingResult | string | The result of the logon process. |
| LogonGuid | string | A GUID that can help you correlate this event with another event that can contain the same Logon GUID. |
| LogonHours | string | Hours that the account is allowed to logon to the domain. |
| LogonID | string | Hexadecimal value that can help you correlate this event with recent events that might contain the same Logon ID. |
| LogonProcessName | string | The name of registered logon process. |
| LogonType | int | The type of logon which was performed. |
| LogonTypeName | string | The type of logon or authentication event that is being captured by the event log (common values:Interactive, Network, RemoteInteractive, Unlock). |
| MachineAccountQuota | string | ms-DS-MachineAccountQuota domain attribute was modified. Numeric value. |
| MachineInventory | string | Information about the hardware configuration and software environment of the computer where the event is being generated. It can include different data points, for instance: the make and model of the |
| MachineLogon | string | Information about a successful logon event in the machine. |
| ManagementGroupName | string | Additional information based on the resource type. |
| MandatoryLabel | string | ID of integrity label which was assigned to the new process. |
| MaxPasswordAge | string | The period of time (in days) that a password can be used before the system requires the user to change it. |
| MemberName | string | The user account that was involved in the event. |
| MemberSid | string | The security identifier (SID) associated with the user account that was involved in the event. |
| MinPasswordAge | string | The period of time (in days) that a password must be used before the system requires the user to change it. |
| MinPasswordLength | string | The least number of characters that can make up a password for a user account. |
| MixedDomainMode | string | The domain mode of a system or domain controller. |
| NASIdentifier | string | The identifier of the network access server (NAS) that was involved in the event. |
| NASIPv4Address | string | The IPv4Address of the network access server (NAS) that was involved in the event, if applicable. |
| NASIPv6Address | string | The IPv6Address of the network access server (NAS) that was involved in the event, if applicable. |
| NASPort | string | the port on the network access server that was used in the event. |
| NASPortType | string | the type of network access server (NAS) used in the event. |
| NetworkPolicyName | string | The name of the network policy associated with the event. |
| NewDate | string | New date in UTC time zone. The format is YYYY-MM-DD. |
| NewMaxUsers | string | The new maximum number of users allowed for a resource in the event. |
| NewProcessId | string | Hexadecimal Process ID of the new process. Process ID (PID) is a number used by the operating system to uniquely identify an active process. |
| NewProcessName | string | Full path and the name of the executable for the new process. |
| NewRemark | string | The new value of network share 'Comments:' field. Has 'N/A' value if it isn't set. |
| NewShareFlags | string | The share flags associated with a resource in the event, for instance: information on whether the resource is read-only or read/write, whether it is hidden, and other parameters that can affect access |
| NewTime | string | New time that was set in UTC time zone. The format is YYYY-MM-DDThh:mm:ss.nnnnnnnZ |
| NewUacValue | string | Specifies flags that control password, lockout, disable/enable, script, and other behavior for the user account. |
| NewValue | string | New value for changed registry key value. |
| NewValueType | string | New type of changed registry key value. |
| ObjectName | string | Name and other identifying information for the object for which access was requested. For example, for a file, the path would be included. |
| ObjectServer | string | Contains the name of the Windows subsystem calling the routine. |
| ObjectType | string | The type of an object that was accessed during the operation. |
| ObjectValueName | string | The name of modified registry key value. |
| OemInformation | string | The original equipment manufacturer (OEM) associated with a device or system in the event. |
| OldMaxUsers | string | The previous maximum number of users allowed for a resource in the event. |
| OldRemark | string | the old value of network share 'Comments:' field. Has 'N/A' value if it isn't set. |
| OldShareFlags | string | The previous share flags associated with a resource in the event, for instance: information on whether the resource is read-only or read/write, whether it is hidden, and other parameters that can affe |
| OldUacValue | string | Specifies flags that control password, lockout, disable/enable, script, and other behavior for the user account. This parameter contains the previous value of userAccountControl attribute of user obje |
| OldValue | string | Old value for changed registry key value. |
| OldValueType | string | Old type of changed registry key value. |
| Opcode | string | The opcode element is defined by the SystemPropertiesType complex type. |
| OperationType | string | The type of operation which was performed on an object |
| PackageName | string | The name of the LAN Manager sub-package (NTLM-family protocol name) that was used during logon. |
| ParentProcessName | string | The name of the parent process associated with the event. |
| PasswordHistoryLength | string | \Security Settings\Account Policies\Password Policy\Enforce password history" group policy. Numeric value. |
| PasswordLastSet | string | Last time the account's password was modified. |
| PasswordProperties | string | The password policies or properties associated with the event, for example: password length, complexity and expiration date. |
| PreviousDate | string | The previous date associated with the event. |
| PreviousTime | string | Previous time in UTC time zone. The format is YYYY-MM-DDThh:mm:ss.nnnnnnnZ. |
| PrimaryGroupId | string | Relative Identifier (RID) of user's object primary group. |
| PrivateKeyUsageCount | string | The number of times a private key has been used. |
| PrivilegeList | string | The privileges, including user, group, or system privileges associated with the event. |
| Process | string | The name of the process that generates the event. |
| ProcessId | string | Identifies the process that generated the event. |
| ProcessName | string | Full path and the name of the executable for the process. |
| ProfilePath | string | Specifies a path to the account's profile. This value can be a null string, a local absolute path, or a UNC path. |
| Properties | string | Depends on Object Type. This field can be empty or contain the list of the object properties that were accessed. |
| ProtocolSequence | string | Information about the protocol used for an authentication attempt. |
| ProxyPolicyName | string | Name of the policy that was used to configure the proxy server for connecting to the network. |
| QuarantineHelpURL | string | URL that provides help with troubleshooting a network quarantine issue. |
| QuarantineSessionID | string | Identifier of the session where the file was assessed for quarantine. |
| QuarantineSessionIdentifier | string | Identifier of the session where the file was assessed for quarantine. |
| QuarantineState | string | It shows whether the file is quarantined. |
| QuarantineSystemHealthResult | string | Report that shows the status of the files that have been quarantined. |
| RelativeTargetName | string | Relative name of the accessed target file or folder. This file-path is relative to the network share. If access was requested for the share itself, then this field appears as "". |
| RemoteIpAddress | string | The IP address of the computer that initiated a remote connection. |
| RemotePort | string | The port number of the remote computer that initiated a connection. |
| Requester | string | The event requester identifier. |
| RequestId | string | A unique identifier that's associated with particular requests, such as those made over HTTP. |
| _ResourceId | string | A unique identifier for the resource that the record is associated with |
| RestrictedAdminMode | string | Only populated for RemoteInteractive logon type sessions. This is a Yes/No flag indicating if the credentials provided were passed using Restricted Admin mode. Restricted Admin mode was added in Win8. |
| RowsDeleted | string | The number of rows that were deleted as a part of a particular operation. |
| SamAccountName | string | logon name for account used to support clients and servers from previous versions of Windows (pre-Windows 2000 logon name). |
| ScriptPath | string | Specifies the path of the account's logon script. |
| SecurityDescriptor | string | Information about the security settings and permissions of a particular object or resource. |
| ServiceAccount | string | The security context that the service will run as when started. |
| ServiceFileName | string | Indicates the type of service that was registered with the Service Control Manager. |
| ServiceName | string | The name of installed service. |
| ServiceStartType | int | Contains information about how a particular service should be started, whether it should be started automatically or manually. |
| ServiceType | string | Indicates the type of service that was registered with the Service Control Manager. |
| SessionName | string | The name of the session to which the user was reconnected. |
| ShareLocalPath | string | The local path of accessed network share. |
| ShareName | string | The name of accessed network share. The format is: \*\SHARE_NAME. |
| SidHistory | string | Contains previous SIDs used for the object if the object was moved from another domain. |
| SourceComputerId | string | Unique identifier assigned to each computer in a Windows domain. |
| SourceSystem | string | The type of agent the event was collected by. For example, OpsManager for Windows agent, either direct connect or Operations Manager, Linux for all Linux agents, or Azure for Azure Diagnostics |
| Status | string | The reason why logon failed. For this event, it typically has '0xC0000234' value. The most common status codes are listed in Table 12. Windows logon status codes. |
| StorageAccount | string | Sets the storage account access key. |
| SubcategoryGuid | string | The unique GUID of changed subcategory. |
| SubcategoryId | string | A unique identifier for a specific type of the event. |
| Subject | string | Information about the security principal (for instance: user account) that initiated the event. |
| SubjectAccount | string | Information about the account that is initiating the event. |
| SubjectDomainName | string | Information about the domain or workgroup to which the subject account belongs. |
| SubjectKeyIdentifier | string | A unique identifier for a particular certificate subject. |
| SubjectLogonId | string | A unique identifier for the logon session associated with the subject account. |
| SubjectMachineName | string | Information about the machine or system from which the event was created. |
| SubjectMachineSID | string | The security identifier (SID) for the machine that generated the event. |
| SubjectUserName | string | The name of the user account that generated the event. |
| SubjectUserSid | string | The security identifier (SID) for the user account that generated the event. |
| _SubscriptionId | string | A unique identifier for the subscription that the record is associated with |
| SubStatus | string | Additional information about logon failure. The most common substatus codes listed in the 'Table 12. Windows logon status codes'. |
| SystemProcessId | int | Identifies the process that generated the event. |
| SystemThreadId | int | Identifies the thread that generated the event. |
| SystemUserId | string | The ID of the user who is responsible for the event. |
| TableId | string | The specific data table identifier the event data is stored in. |
| TargetAccount | string | The account targeted by the event (user name, computer name, etc). |
| TargetDomainName | string | The name of the domain that the target account belongs to. |
| TargetInfo | string | Additional information about the event target (for example: the path to a file or folder, the name of a registry key, etc). |
| TargetLinkedLogonId | string | Information that helps to link related events together by their logon attempt IDs. It can be useful in keeping all relevant events organized, tracking activity across multiple sessions, and identifyin |
| TargetLogonGuid | string | A globally unique identifier (GUID) associated with the logon session related to the event. |
| TargetLogonId | string | A unique identifier associated with the logon session related to the event. |
| TargetOutboundDomainName | string | The domain that the account specified in the TargetAccount field was authenticated against during an outbound authentication attempt. |
| TargetOutboundUserName | string | The name of the user account that was authenticated during an outbound authentication attempt. |
| TargetServerName | string | The name of the server on which the new process was run. Has "localhost" value if the process was run locally. |
| TargetSid | string | The security identifier (SID) of the server on which the new process was run. |
| TargetUser | string | The user account identifier that generated the new process. |
| TargetUserName | string | The name of the user account that generated the new process. |
| TargetUserSid | string | The security identifier (SID) associated with the user or resource involved in the event. |
| Task | int | The task defined in the event. |
| TemplateContent | string | The content of the event message or notification in a structured form. |
| TemplateDSObjectFQDN | string | FQDN of the DS object that represents the GPO template. |
| TemplateInternalName | string | The internal name of the GPO template. |
| TemplateOID | string | the unique identifier for the template that was used to create the event. |
| TemplateSchemaVersion | string | Version of the template schema that defines the data to include with an event. |
| TemplateVersion | string | Version of the template that defines the data to include with an event. |
| TenantId | string | The Log Analytics workspace ID |
| TimeGenerated | datetime | The time stamp when the event was generated on the computer. |
| TokenElevationType | string | Type of token that was assigned to a new process in accordance with User Account Control Policy. |
| TransmittedServices | string | The list of transmitted services. Transmitted services are populated if the logon was a result of a S4U (Service For User) logon process. S4U is a Microsoft extension to the Kerberos Protocol to allow |
| Type | string | The name of the table |
| UserAccountControl | string | Shows the list of changes in userAccountControl attribute. You will see a line of text for each change. |
| UserParameters | string | If you change any setting using Active Directory Users and Computers management console in Dial-in tab of user's account properties, then you will see <value changed, but not displayed> in this field. |
| UserPrincipalName | string | Internet-style login name for the account, based on the Internet standard RFC 822. By convention this should map to the account's email name. |
| UserWorkstations | string | Contains the list of NetBIOS or DNS names of the computers from which the user can logon. Each computer name is separated by a comma. The name of a computer is the sAMAccountName property of a compute |
| VendorIds | string | 'Hardware Ids' attribute of device. To see device properties, start Device Manager, open specific device properties, and click 'Details'. |
| Version | int | Contains the version number of the event's definition. |
| VirtualAccount | string | A 'Yes' or 'No' flag, which indicates if the account is a virtual account (e.g., 'Managed Service Account'), which was introduced in Windows 7 and Windows Server 2008 R2 to provide the ability to iden |
| Workstation | string | The name of the machine that was used to perform the event. |
| WorkstationName | string | Machine name from which a logon attempt was performed. |

## Cloud infrastructure

### AzureActivity
Product: Microsoft Sentinel (Log Analytics)
Category: Cloud infrastructure
Time field: TimeGenerated
Description: Categories: Azure Resources, Audit, Security; Solutions: LogManagement
Source: https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/azureactivity

| Column | Type | Description |
|---|---|---|
| ActivityStatus | string |  |
| ActivityStatusValue | string | Status of the operation in display-friendly format. Common values include Started, In Progress, Succeeded, Failed, Active, Resolved. |
| ActivitySubstatus | string |  |
| ActivitySubstatusValue | string | Substatus of the operation in display-friendly format. E.g. OK (HTTP Status Code: 200). |
| Authorization | string | Blob of RBAC properties of the event. Usually includes the "action", "role" and "scope" properties. Stored as string. The use of Authorization_d should be preferred going forward. |
| Authorization_d | dynamic | Blob of RBAC properties of the event. Usually includes the "action", "role" and "scope" properties. Stored as dynamic column. |
| _BilledSize | real | The record size in bytes |
| Caller | string | GUID of the caller. |
| CallerIpAddress | string | IP address of the user who has performed the operation UPN claim or SPN claim based on availability. |
| Category | string |  |
| CategoryValue | string | Category of the activity log e.g. Administrative, Policy, Security. |
| Claims | string | The JWT token used by Active Directory to authenticate the user or application to perform this operation in Resource Manager. The use of claims_d should be preferred going forward. |
| Claims_d | dynamic | The JWT token used by Active Directory to authenticate the user or application to perform this operation in Resource Manager. |
| CorrelationId | string | Usually a GUID in the string format. Events that share a correlationId belong to the same uber action. |
| EventDataId | string | Unique identifier of an event. |
| EventSubmissionTimestamp | datetime | Timestamp when the event became available for querying. |
| Hierarchy | string | Management group hierarchy of the management group or subscription that event belongs to. |
| HTTPRequest | string | Blob describing the Http Request. Usually includes the "clientRequestId", "clientIpAddress" and "method" (HTTP method. For example, PUT). |
| _IsBillable | string | Specifies whether ingesting the data is billable. When _IsBillable is false ingestion isn't billed to your Azure account |
| Level | string | Level of the event. One of the following values: Critical, Error, Warning, Informational and Verbose. |
| OperationId | string | GUID of the operation |
| OperationName | string |  |
| OperationNameValue | string | Identifier of the operation e.g. Microsoft.Storage/storageAccounts/listAccountSas/action. |
| Properties | string | Set of <Key Value> pairs (i.e. Dictionary) describing the details of the event. Stored as string. Usage of Properties_d is recommended instead. |
| Properties_d | dynamic | Set of <Key Value> pairs (i.e. Dictionary) describing the details of the event. Stored as dynamic column. |
| Resource | string |  |
| ResourceGroup | string | Resource group name of the impacted resource. |
| ResourceId | string |  |
| _ResourceId | string | A unique identifier for the resource that the record is associated with |
| ResourceProvider | string |  |
| ResourceProviderValue | string | Id of the resource provider for the impacted resource - e.g. Microsoft.Storage. |
| SourceSystem | string | The type of agent the event was collected by. For example, OpsManager for Windows agent, either direct connect or Operations Manager, Linux for all Linux agents, or Azure for Azure Diagnostics |
| SubscriptionId | string | Subscription ID of the impacted resource. |
| _SubscriptionId | string | A unique identifier for the subscription that the record is associated with |
| TenantId | string | The Log Analytics workspace ID |
| TimeGenerated | datetime | Timestamp when the event was generated by the Azure service processing the request corresponding the event. |
| Type | string | The name of the table |