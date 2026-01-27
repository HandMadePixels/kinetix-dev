# 🛡️ Kinetix Security Analysis & Threat Model

This document provides a comprehensive security review, STRIDE threat model, and risk analysis for the Kinetix Endpoint Management system.

---

## 1. Executive Summary
Kinetix is designed with a "Security-First" architecture. It employs industry-standard cryptographic primitives, robust authentication mechanisms, and proactive defense strategies. The pull-based architecture minimizes the attack surface by avoiding the need for open inbound ports on client devices. 

**v1.4.0 update:** Implemented Persistent Token Handshake (Access + Refresh), secure DPAPI-backed token storage on agents, and centralized administrative environment management.

---

## 2. Security Architecture Review

### 🔑 Authentication & Authorization
- **Persistent Token Handshake**: Transitioned to a dual-token model. Agents use short-lived Access Tokens (15m) and long-lived Refresh Tokens (7d).
- **Handshake Resilience**: A custom `DeviceTokenRefreshSerializer` allows `Device` models to rotate tokens without triggering standard `User`-only blacklisting constraints, ensuring uptime.
- **Secure Token Storage**: Agents store secrets in the **Windows Credential Manager (DPAPI)** via the `keyring` library, preventing exposure via plain-text configuration files or memory dumps.
- **Granular Permissions**: Custom Django permissions (`can_execute_shell`, `can_control_services`, etc.) ensure the Principle of Least Privilege is enforced.

### 🔐 Cryptography
- **Update Signing**: RSA-4096 with PSS padding and SHA-256 ensures non-repudiation and integrity of deployed software.
- **Field-Level Encryption**: Sensitive database fields (API keys, SMTP passwords, JWT tokens) are encrypted using **AES-256 (Fernet)**.
- **CSRF Protection**: Utilizes standard Django CSRF middleware with a meta-tag fallback for AJAX, optimized for real-time dashboard responsiveness.

### 🛡️ Defense-in-Depth
- **Malware Scanning**: Integrated VirusTotal and ClamAV scanning for all uploads.
- **Diagnostic Resilience**: Data collection fallbacks (e.g., PowerShell `Get-HotFix`) use static command strings to prevent injection while ensuring visibility even if COM interfaces are restricted.
- **Rate Limiting**: Custom `RateLimitMiddleware` combined with DRF Throttling protects against brute-force and DoS attacks.
- **Asynchronous Audit Logging**: Request-level logging is handled via Celery tasks to prevent performance degradation and ensure traceability.

---

## 3. STRIDE Threat Model

| Category | Threat | Mitigation |
| :--- | :--- | :--- |
| **S**poofing | Attacker impersonates a managed device or the server. | **Server**: SSL/TLS certificate verification by agents. **Device**: JWT tokens linked to unique UUIDs; manual registration option. |
| **T**ampering | Attacker modifies an update file or remote command. | **Updates**: RSA-4096 digital signatures verified by the agent. **Commands**: Signed requests and HTTPS transport security. |
| **R**epudiation | Admin denies triggering a sensitive command (e.g., shell). | **Audit Logs**: Database-backed audit trails capturing `user_id`, `ip_address`, `timestamp`, and `action`. |
| **I**nformation Disclosure | Attacker extracts API keys or credentials from the database. | **Encryption**: Use of `EncryptedTextField` (AES-256) for all sensitive fields. |
| **D**enial of Service | Attacker floods the API with registration or poll requests. | **Rate Limiting**: Multi-layer throttling (IP-based, User-based, and Endpoint-specific). |
| **E**levation of Privilege | Compromised agent executes commands as SYSTEM on other devices. | **Isolation**: Agents only pull their own commands. No peer-to-peer communication. Server-side permission checks for every command creation. |

---

## 4. Risk Analysis

| Vulnerability | Likelihood | Impact | Risk Level | Mitigation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Remote Shell Abuse** | Low | Critical | **High** | **Mitigated**: Requires specific `can_execute_shell` permission; fully logged in audit trail. |
| **Insecure Update Delivery** | Very Low | Critical | **Medium** | **Mitigated**: RSA-4096 signing prevents unauthorized software execution. |
| **Refresh Token Theft** | Low | High | **Medium** | **Mitigated**: Tokens stored in encrypted DPAPI vault; server-side rotation enabled. |
| **Credential Exposure in Logs** | Medium | Medium | **Medium** | **Mitigated**: `custom_exception_handler` masks sensitive data; Fernet encryption for fields. |
| **AJAX CSRF Bypass** | Very Low | Medium | **Low** | **Trade-off**: `CSRF_COOKIE_HTTPONLY` disabled to support dashboard SPA features; mitigated by `SameSite=Strict`. |

---

## 5. Security Recommendations

### Short-Term
1. **Enable HTTPS**: Transition from HTTP to HTTPS for all production deployments.
2. **Rotate Keys**: Regularly rotate the `ENCRYPTION_KEY` and RSA Keypair.
3. **MFA Enforcement**: Implement Multi-Factor Authentication for Dashboard administrator logins.

### Long-Term
1. **Hardware Security**: Support for TPM-backed storage of agent private keys.
2. **IP Whitelisting**: Restrict access to the Command Center to specific VPN/Management subnets.
3. **Blacklist DB Scaling**: Implement a custom `OutstandingToken` model that supports `Device` instances for full Device-token blacklisting.

---

## 6. Code Review Findings

### 🛡️ Strengths
- **Credential Isolation**: Agent secrets never touch the disk in plain text; they reside in the OS secure vault.
- **Fail-Safe Registration**: Agents automatically re-verify identity and refresh public keys upon authentication failure (e.g., after a server reset).
- **Asynchronous Table Updates**: Use of targeted DOM updates instead of page reloads reduces XSS surface by avoiding full-page re-renders.
- **Robust Field Serialization**: Use of `DjangoJSONEncoder` for automatic UUID and datetime serialization in Audit Logs.

### ⚠️ Areas for Improvement
- **Shell Command Output**: Currently returns raw shell output. Large outputs could potentially cause DoS via log-filling.
- **IP Trust**: Currently trusts `X-Forwarded-For` for auditing. In environments with load balancers, a trusted proxy list should be enforced.

---
**Security Status: HARDENED**
*Last Audit: January 2026*
