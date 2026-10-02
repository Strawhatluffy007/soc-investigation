"""Event types the local engine recognises, and what to do about each.

Each playbook lists:
  signals    regexes over the lowercased log; each hit adds weight
  keys       field names whose presence is evidence for this type
  tables     candidate tables, best first (filtered by the customer schema)
  hypotheses / unknowns / steps   starting points for the analyst

To teach the engine a new event type, add an entry here; no other code
changes are needed. Query shapes live in app/kql/generator.py.
"""
from __future__ import annotations

SIGNIN_TABLES = ["SigninLogs", "AADSignInEventsBeta", "EntraIdSignInEvents", "AADNonInteractiveUserSignInLogs",
                 "IdentityLogonEvents"]

PLAYBOOKS: dict[str, dict] = {
    "entra_signin": {
        "label": "Entra ID authentication",
        "product": "Microsoft Entra ID",
        "signals": [r"sign-?in", r"\bsigninlogs\b", r"\bresulttype\b", r"conditionalaccess", r"\bappdisplayname\b",
                    r"authenticationrequirement", r"aadsts\d+", r"login\.microsoftonline", r"\bclientappused\b"],
        "keys": ["ResultType", "AppDisplayName", "ConditionalAccessStatus", "AuthenticationRequirement",
                 "ClientAppUsed", "UserPrincipalName", "RiskLevelDuringSignIn"],
        "tables": SIGNIN_TABLES,
        "hypotheses": [
            ("The sign-in is legitimate activity by the account owner.",
             "Check whether the IP, location, device and app match the user's sign-in history."),
            ("The account's credentials are compromised and being used by a third party.",
             "Look for successful sign-ins from the same IP or new locations, MFA prompts and later mailbox/admin activity."),
            ("The source IP is attacking multiple accounts (password spray / brute force).",
             "Count distinct accounts targeted from the same IP and the failure/success ratio."),
        ],
        "unknowns": ["Whether the user recognises this sign-in", "Whether the source IP belongs to a corporate VPN/proxy",
                     "Whether MFA was satisfied by the legitimate user"],
        "steps": ["Review the user's sign-ins for the last 7-30 days and compare IP, location, device and app.",
                  "Check how many accounts the source IP touched, and whether any succeeded.",
                  "Check Entra ID risk detections / risky user state for the account.",
                  "If compromise is suspected: confirm with the user, revoke sessions and reset credentials per customer process."],
    },
    "mfa": {
        "label": "MFA event",
        "product": "Microsoft Entra ID",
        "signals": [r"\bmfa\b", r"multi-?factor", r"strong authentication", r"mfadenied", r"authenticator",
                    r"fraud ?report", r"500121", r"50074", r"50076", r"push notification", r"mfa fatigue"],
        "keys": ["AuthenticationDetails", "AuthenticationRequirement", "MfaDetail"],
        "tables": SIGNIN_TABLES + ["AuditLogs"],
        "hypotheses": [
            ("The user is being targeted with repeated MFA prompts (MFA fatigue).",
             "Count MFA prompts/denials for the user over a short window."),
            ("The password is already known to an attacker, who is now blocked only by MFA.",
             "Look for prior failed sign-ins and correct-password/MFA-required results from unfamiliar IPs."),
            ("A new MFA method was registered by someone other than the user.",
             "Review AuditLogs for authentication-method registration changes."),
        ],
        "unknowns": ["Whether the user approved or initiated the MFA request", "Whether authentication methods changed recently"],
        "steps": ["List MFA results for the user in the last 24-72h.", "Check AuditLogs for new authentication methods.",
                  "Contact the user to confirm whether they initiated the sign-ins."],
    },
    "impossible_travel": {
        "label": "Impossible / atypical travel",
        "product": "Microsoft Entra ID / Defender for Cloud Apps",
        "signals": [r"impossible travel", r"atypical travel", r"unfamiliar (sign-?in )?(properties|location)",
                    r"anonymous ip", r"new country", r"infrequent country"],
        "keys": ["Location", "LocationDetails", "RiskEventType"],
        "tables": SIGNIN_TABLES,
        "hypotheses": [
            ("The two sign-ins are from the same user using a VPN, proxy or mobile network.",
             "Check whether one of the IPs belongs to a known VPN/egress range for the customer."),
            ("A second party is using the account from another location.",
             "Compare device, user agent, app and session details of both sign-ins."),
        ],
        "unknowns": ["Whether either location is a corporate egress/VPN", "Whether both sign-ins came from the same device"],
        "steps": ["Pull both sign-ins and compare device ID, OS, browser and app.", "Check the IPs against customer VPN ranges.",
                  "Review activity after the second sign-in (mailbox rules, OAuth consents, file downloads)."],
    },
    "account_modification": {
        "label": "Account / directory modification",
        "product": "Microsoft Entra ID / Defender for Identity",
        "signals": [r"add member to role", r"add user", r"update user", r"reset (user )?password", r"change password",
                    r"disable account", r"auditlogs", r"operationname", r"targetresources", r"directory ?change",
                    r"4720|4722|4724|4738|4728|4732|4756", r"consent to application", r"add service principal"],
        "keys": ["OperationName", "TargetResources", "InitiatedBy", "ActivityDisplayName"],
        "tables": ["AuditLogs", "IdentityDirectoryEvents", "CloudAppEvents"],
        "hypotheses": [
            ("The change is a legitimate administrative action.", "Confirm with the initiating admin or a change ticket."),
            ("An attacker is establishing persistence (new account, credential, or app consent).",
             "Check what the initiator did before and after the change and whether they signed in from an unusual location."),
        ],
        "unknowns": ["Whether a change request exists for this action", "Whether the initiating account is itself compromised"],
        "steps": ["List all directory changes by the initiator in the window.", "Review the initiator's recent sign-ins.",
                  "Check whether the target object was used after the change."],
    },
    "privilege_escalation": {
        "label": "Privilege escalation",
        "product": "Microsoft Entra ID / Defender for Identity / Defender for Endpoint",
        "signals": [r"global administrator", r"privileged role", r"add member to role", r"\bpim\b", r"elevat",
                    r"domain admins", r"enterprise admins", r"sedebugprivilege", r"token manipulation", r"runas",
                    r"4672", r"4728|4732|4756", r"privilege escalation"],
        "keys": ["RoleName", "TargetResources"],
        "tables": ["AuditLogs", "IdentityDirectoryEvents", "DeviceEvents", "DeviceProcessEvents"],
        "hypotheses": [
            ("A legitimate admin or PIM activation granted the privilege.", "Match against PIM activation or change records."),
            ("An attacker escalated privileges after initial access.", "Look for unusual sign-ins or process activity by the actor just before."),
        ],
        "unknowns": ["Whether the elevation was approved", "What the elevated account did afterwards"],
        "steps": ["Identify who granted the role and from where.", "Review actions taken with the new privilege.",
                  "Remove unapproved privileges per customer process."],
    },
    "process_execution": {
        "label": "Process execution",
        "product": "Microsoft Defender for Endpoint",
        "signals": [r"processcommandline", r"initiatingprocess", r"process ?created", r"\bcmd\.exe\b", r"powershell",
                    r"rundll32", r"regsvr32", r"mshta", r"wscript|cscript", r"certutil", r"bitsadmin", r"-enc(odedcommand)?\b",
                    r"4688", r"processcreated", r"living off the land"],
        "keys": ["ProcessCommandLine", "InitiatingProcessFileName", "InitiatingProcessCommandLine", "FolderPath", "SHA256"],
        "tables": ["DeviceProcessEvents", "DeviceEvents", "DeviceImageLoadEvents"],
        "hypotheses": [
            ("The process is legitimate admin / software activity.", "Check the parent process, signer and prevalence across devices."),
            ("The process is attacker execution (LOLBin abuse, script, payload).",
             "Decode command lines, check the parent chain and any network or file activity that followed."),
        ],
        "unknowns": ["Whether the binary is signed / known-good", "How the process was launched (user, scheduled task, exploit)"],
        "steps": ["Build the process tree for the device around the event time.", "Check file prevalence (SHA256) across the estate.",
                  "Review network connections from the process.", "Isolate the device if malicious execution is confirmed."],
    },
    "network_connection": {
        "label": "Network connection",
        "product": "Microsoft Defender for Endpoint",
        "signals": [r"remoteip", r"remoteport", r"remoteurl", r"connectionsuccess", r"connectionattempt",
                    r"outbound", r"inbound", r"beacon", r"\bc2\b", r"command and control", r"firewall", r"dns query"],
        "keys": ["RemoteIP", "RemotePort", "RemoteUrl", "LocalIP", "Protocol"],
        "tables": ["DeviceNetworkEvents", "CommonSecurityLog", "DnsEvents"],
        "hypotheses": [
            ("The connection is normal application traffic.", "Check which process made it and how many other devices contact the same destination."),
            ("The device is communicating with attacker infrastructure (C2 / exfiltration).",
             "Look for periodic connections, rare destinations and data volume."),
        ],
        "unknowns": ["Reputation of the remote IP/domain (no threat intel lookup performed)", "Volume of data transferred"],
        "steps": ["Identify the initiating process and its parent.", "Count devices contacting the destination (prevalence).",
                  "Check reputation of the destination in your TI sources.", "Block the destination if malicious."],
    },
    "malware": {
        "label": "Malware detection",
        "product": "Microsoft Defender for Endpoint / Defender Antivirus",
        "signals": [r"malware", r"trojan", r"ransom", r"virus", r"threatname", r"antivirusdetection", r"quarantin",
                    r"backdoor", r"\bpua\b", r"wacatac", r"defender antivirus", r"detected", r"remediat"],
        "keys": ["ThreatName", "SHA256", "FileName", "FolderPath", "ActionType"],
        "tables": ["DeviceEvents", "DeviceFileEvents", "AlertEvidence", "AlertInfo", "DeviceProcessEvents"],
        "hypotheses": [
            ("Defender blocked the file before execution; impact is contained.", "Confirm the remediation action succeeded and the file did not run."),
            ("The malware executed before detection and may have persisted or spread.",
             "Look for process execution of the hash, persistence and lateral movement on and from the device."),
        ],
        "unknowns": ["Whether the file executed", "How the file arrived on the device (email, web, USB)"],
        "steps": ["Confirm the remediation status.", "Search for the hash across all devices.", "Find the file's origin (FileOriginUrl, email, download).",
                  "Run a full scan / isolate the device if execution is confirmed."],
    },
    "phishing": {
        "label": "Phishing / malicious email",
        "product": "Microsoft Defender for Office 365",
        "signals": [r"phish", r"spoof", r"malicious (url|link|attachment)", r"\bzap\b", r"safe ?links", r"credential harvest",
                    r"user reported", r"impersonation"],
        "keys": ["NetworkMessageId", "SenderFromAddress", "ThreatTypes", "Url", "UrlClickEvents"],
        "tables": ["EmailEvents", "EmailUrlInfo", "UrlClickEvents", "EmailAttachmentInfo", "EmailPostDeliveryEvents"],
        "hypotheses": [
            ("The email is a phishing attempt that was blocked or not interacted with.", "Check delivery action and URL clicks."),
            ("A recipient clicked the link and may have entered credentials.",
             "Check UrlClickEvents and sign-ins for recipients shortly after delivery."),
        ],
        "unknowns": ["Whether any recipient clicked or opened the content", "Whether credentials were entered"],
        "steps": ["List all recipients of the same sender / subject / URL.", "Check URL clicks for those recipients.",
                  "Purge remaining messages per customer process.", "Review sign-ins of users who clicked."],
    },
    "email": {
        "label": "Email event",
        "product": "Microsoft Defender for Office 365 / Exchange Online",
        "signals": [r"networkmessageid", r"senderfromaddress", r"recipientemailaddress", r"internetmessageid",
                    r"deliveryaction", r"subject:", r"\bmailbox\b", r"inbox rule", r"new-inboxrule", r"forwarding"],
        "keys": ["NetworkMessageId", "SenderFromAddress", "RecipientEmailAddress", "Subject", "DeliveryAction"],
        "tables": ["EmailEvents", "EmailUrlInfo", "EmailAttachmentInfo", "CloudAppEvents", "OfficeActivity"],
        "hypotheses": [
            ("This is normal mail flow.", "Check sender history and authentication results (SPF/DKIM/DMARC)."),
            ("The mailbox is being abused (forwarding rule, exfiltration, internal phishing).",
             "Check inbox rules and outbound mail from the account."),
        ],
        "unknowns": ["Sender authentication results", "Whether the mailbox has new rules or forwarding"],
        "steps": ["Look up all messages from the sender in the window.", "Check inbox rule / forwarding changes for the mailbox owner."],
    },
    "defender_alert": {
        "label": "Defender XDR alert",
        "product": "Microsoft Defender XDR",
        "signals": [r"\balertid\b", r"\bincidentid\b", r"detectionsource", r"servicesource", r"mitre", r"attacktechniques",
                    r"alertinfo", r"alertevidence", r"securityalert", r"\bseverity\b"],
        "keys": ["AlertId", "Title", "Severity", "DetectionSource", "ServiceSource", "AttackTechniques"],
        "tables": ["AlertInfo", "AlertEvidence", "SecurityAlert", "SecurityIncident"],
        "hypotheses": [
            ("The alert is a true positive for the described technique.", "Review all evidence entities and related alerts."),
            ("The alert is a false/benign positive (expected admin or software behaviour).", "Check whether the entity has a history of the same alert."),
        ],
        "unknowns": ["Whether related alerts exist on the same entities", "Whether the alert was already remediated automatically"],
        "steps": ["List all evidence for the alert.", "Find other alerts on the same device/user in the window.",
                  "Pivot into the underlying device/identity tables for raw activity."],
    },
    "cloud_alert": {
        "label": "Defender for Cloud / Azure event",
        "product": "Microsoft Defender for Cloud",
        "signals": [r"defender for cloud", r"azure security center", r"subscriptionid", r"resourcegroup", r"/subscriptions/",
                    r"azureactivity", r"operationnamevalue", r"microsoft\.(compute|storage|keyvault|network)"],
        "keys": ["SubscriptionId", "ResourceGroup", "ResourceId", "OperationNameValue", "CompromisedEntity"],
        "tables": ["SecurityAlert", "AzureActivity", "AzureDiagnostics"],
        "hypotheses": [
            ("The activity is an expected deployment or admin operation.", "Match against change records / deployment pipelines."),
            ("A cloud identity or resource is compromised.", "Review the caller's other operations and sign-ins."),
        ],
        "unknowns": ["Whether the caller is an approved automation identity", "Exposure of the affected resource"],
        "steps": ["List operations by the same caller.", "Check the affected resource's configuration changes."],
    },
    "device_logon": {
        "label": "Device / identity logon",
        "product": "Microsoft Defender for Endpoint / Defender for Identity",
        "signals": [r"logontype", r"logonsuccess", r"logonfailed", r"4624", r"4625", r"4648", r"remoteinteractive",
                    r"\brdp\b", r"\bntlm\b", r"kerberos", r"pass-the-(hash|ticket)", r"lateral movement"],
        "keys": ["LogonType", "AccountName", "AccountDomain", "RemoteDeviceName", "Protocol"],
        "tables": ["DeviceLogonEvents", "IdentityLogonEvents", "SecurityEvent"],
        "hypotheses": [
            ("The logon is normal user or service activity.", "Compare with the account's normal logon pattern and devices."),
            ("The account is being used for lateral movement.", "Look for the same account logging on to many devices in a short time."),
        ],
        "unknowns": ["Whether the account normally logs on to this device", "Source of the logon"],
        "steps": ["List logons by the account across devices.", "List logons to the device by other accounts.",
                  "Check for credential-theft indicators on the source device."],
    },
}

GENERIC = {
    "label": "Unclassified security event",
    "product": "Unknown",
    "tables": [],
    "hypotheses": [
        ("The event reflects normal activity.", "Establish a baseline for the involved entities."),
        ("The event is part of malicious activity.", "Pivot on each observable across the customer's tables."),
    ],
    "unknowns": ["Event type could not be determined from the log content"],
    "steps": ["Identify the log source and map it to a table in the customer schema.",
              "Pivot on the extracted observables across the available tables."],
}


def playbook(event_type: str) -> dict:
    return PLAYBOOKS.get(event_type, GENERIC)
