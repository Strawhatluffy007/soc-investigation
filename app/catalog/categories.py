"""Group catalog tables into categories.

The names follow the Microsoft Defender portal's advanced hunting Schema tab
("Alerts & behaviors", "Apps & identities", "Email & collaboration", "Devices",
"Threat & vulnerability management", "Exposure management"). The Email &
collaboration list matches the tables Microsoft documents for that permission
(learn.microsoft.com/defender-xdr/advanced-hunting-overview#get-access).

Microsoft Learn has no per-table grouping for the Sentinel / Log Analytics
security tables, so the same names are reused for them, plus a few extra groups
for data that only Sentinel collects (network, cloud, threat intelligence).
A `Category:` line on a table in the catalog overrides these rules.
"""
from __future__ import annotations

CATEGORIES = (
    "Alerts & behaviors",
    "Apps & identities",
    "Email & collaboration",
    "Devices",
    "Threat & vulnerability management",
    "Exposure management",
    "Network",
    "Cloud infrastructure",
    "Data security & compliance",
    "Threat intelligence",
    "Business applications",
    "Microsoft Sentinel",
    "Other",
)

_EXACT = {
    # Alerts & behaviors
    "AlertInfo": 0, "AlertEvidence": 0, "BehaviorInfo": 0, "BehaviorEntities": 0, "SecurityAlert": 0,
    "AggregatedSecurityAlert": 0, "SecurityIncident": 0, "SecurityDetection": 0, "Anomalies": 0,
    "BehaviorAnalytics": 0, "UserAccessAnalytics": 0, "UserPeerAnalytics": 0, "DisruptionAndResponseEvents": 0,
    "ASimAlertEventLogs": 0, "CrowdStrikeAlerts": 0, "CrowdStrikeDetections": 0, "CrowdStrikeIncidents": 0,
    "CrowdStrikeCases": 0, "NetworkAccessAlerts": 0, "AWSGuardDuty": 0, "AWSSecurityHubFindings": 0,
    "GoogleCloudSCC": 0, "StorageMalwareScanningResults": 0,
    # Apps & identities
    "SigninLogs": 1, "AuditLogs": 1, "ADFSSignInLogs": 1, "CloudAppEvents": 1, "OAuthAppInfo": 1,
    "GraphApiAuditEvents": 1, "GraphAPIAuditEvents": 1, "MicrosoftServicePrincipalSignInLogs": 1,
    "OfficeActivity": 1, "EnrichedMicrosoft365AuditLogs": 1, "CopilotActivity": 1, "McasShadowItReporting": 1,
    "AgentsInfo": 1, "AIAgentsInfo": 1, "OktaSystemLogs": 1, "GoogleWorkspaceReports": 1,
    "ASimAuthenticationEventLogs": 1, "ASimUserManagementActivityLogs": 1, "PreAuthenticationDiscoveryLogs": 1,
    "GraphNotificationsActivityLogs": 1, "DataverseActivity": 1, "ProjectActivity": 1,
    "CrowdStrikeAuditEvents": 1,
    # Email & collaboration
    "UrlClickEvents": 2, "CampaignInfo": 2, "FileMaliciousContentInfo": 2, "CallActivityEvents": 2,
    # Devices
    "SecurityEvent": 3, "WindowsEvent": 3, "Event": 3, "Syslog": 3, "LinuxAuditLog": 3,
    "ASimProcessEventLogs": 3, "ASimFileEventLogs": 3, "ASimRegistryEventLogs": 3, "ASimAgentEventLogs": 3,
    "CrowdStrikeHosts": 3, "SecurityIoTRawEvent": 3,
    # Threat & vulnerability management
    "SecurityBaseline": 4, "SecurityBaselineSummary": 4, "SecurityRecommendation": 4, "ProtectionStatus": 4,
    "Update": 4, "QualysKnowledgeBase": 4, "CrowdStrikeVulnerabilities": 4,
    # Exposure management
    "SecurityAttackPathData": 5, "ASimAssetEntityLogs": 5,
    # Network
    "CommonSecurityLog": 6, "NetworkSessions": 6, "NSPAccessLogs": 6, "DnsAuditEvents": 6, "WireData": 6,
    "WindowsFirewall": 6, "IlumioInsights": 6, "RemoteNetworkHealthLogs": 6, "SentinelImpervaWAFCloudV2Logs": 6,
    "ASimNetworkSessionLogs": 6, "ASimDnsActivityLogs": 6, "ASimDhcpEventLogs": 6, "ASimWebSessionLogs": 6,
    # Cloud infrastructure
    "AzureActivity": 7, "AzureDiagnostics": 7, "AppServiceServerlessSecurityPluginData": 7,
    "HDInsightSecurityLogs": 7, "AADB2CRequestLogs": 1,
    # Data security & compliance
    "CommunicationComplianceActivity": 8, "MicrosoftPurviewInformationProtection": 8,
    "PurviewDataSensitivityLogs": 8,
    # Threat intelligence
    "AZFWThreatIntel": 9,
    # Microsoft Sentinel
    "Watchlist": 11, "ConfidentialWatchlist": 11, "SentinelHealth": 11, "SentinelAudit": 11,
    "HuntingBookmark": 11, "DynamicEventCollection": 11, "ASimAuditEventLogs": 11,
}

# First matching prefix wins, so more specific prefixes come first.
_PREFIX = (
    ("DeviceTvm", 4), ("DeviceBaseline", 4), ("DeviceBehavior", 0), ("Device", 3),
    ("SentinelBehavior", 0), ("SentinelAlibabaCloud", 7), ("Sentinel", 11),
    ("ExposureGraph", 5), ("Rapid7", 4),
    ("Email", 2), ("Message", 2),
    ("AADDomainServices", 1), ("AAD", 1), ("EntraId", 1), ("Identity", 1), ("MicrosoftGraph", 1),
    ("Power", 1), ("Salesforce", 10),
    ("DataSecurity", 8), ("DSM", 8), ("Purview", 8),
    ("ThreatIntel", 9),
    ("AZFW", 6), ("NetworkAccess", 6), ("ZTS", 6),
    ("ABAP", 10), ("SAP", 10),
    ("Cloud", 7), ("MDC", 7), ("AWS", 7), ("GCP", 7), ("GKE", 7), ("NCBM", 7),
)


def categorize(table: str) -> str:
    if table in _EXACT:
        return CATEGORIES[_EXACT[table]]
    for prefix, idx in _PREFIX:
        if table.startswith(prefix):
            return CATEGORIES[idx]
    return "Other"


def order(category: str) -> int:
    try:
        return CATEGORIES.index(category)
    except ValueError:
        return len(CATEGORIES) - 1  # custom names sort with "Other"
