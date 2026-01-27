# 🛡️ Kinetix Security Analysis & Threat Model

This document provides a comprehensive security review, STRIDE threat model, and risk analysis for the Kinetix Endpoint Management system.

---

## 1. Executive Summary
Kinetix is designed with a "Security-First" architecture. It employs industry-standard cryptographic primitives, robust authentication mechanisms, and proactive defense strategies. The pull-based architecture minimizes the attack surface by avoiding the need for open inbound ports on client devices. 

**v1.5.0 update:** Implemented Hybrid RSA-AES Token Handshake, Cryptographic Re-registration Challenges, HKDF-based Field Isolation, and multi-layer Command Injection protection.

---

## 2. Security Architecture Review

### 🔑 Authentication & Authorization
- **Hybrid Secure Handshake**: Transitioned to a "Zero-Knowledge" registration flow. Agents generate local RSA-4096 keypairs; the server delivers long-lived Refresh Tokens encrypted via a hybrid RSA-OAEP + AES (Fernet) envelope.
- **Cryptographic Identity**: Agents prove their identity during re-registration by signing payloads with their unique private key. The server verifies this against stored public keys, preventing device impersonation.
- **Persistent JWT Flow**: Dual-token model with 15m Access Tokens and 7d Refresh Tokens. Automatic token rotation is enabled to minimize the window of compromise.
- **Granular Permissions**: Strict RBAC enforcing the Principle of Least Privilege via custom Django permissions.

### 🔐 Cryptography
- **Field-Level Isolation (HKDF)**: Utilizes HKDF (HMAC-based Key Derivation) to derive unique encryption keys for every database field. A compromise of one column (e.g., agent tokens) does not expose other encrypted data (e.g., system secrets).
- **Hardened Hashing**: Explicit whitelist enforcement of SHA-256/SHA-512. Legacy/insecure algorithms (MD5, SHA-1) are strictly blocked at the utility layer.
- **Update Signing**: RSA-4096 with PSS padding and SHA-256 ensures non-repudiation and integrity of deployed software.
- **Secure Storage**: Agent private keys and tokens reside exclusively in the **Windows Credential Manager (DPAPI)**, never touching the disk in plain text.

### 🛡️ Defense-in-Depth
- **Command Injection Protection**: Triple-layer defense including API-level regex filtering, model-level validation, and shell-less execution (`shell=False`) on the agent.
- **MIME-Type Verification**: Uses `python-magic` to inspect "Magic Bytes," ensuring software updates match allowed executable types regardless of file extension.
- **NAT-Aware IP Mitigation**: Intelligent spoofing detection that prioritizes connection source (`REMOTE_ADDR`) while distinguishing between suspicious public IP mismatches and standard private NAT behavior.
- **Granular Throttling**: Per-device rate limiting prevents compromised agents from performing DDoS or brute-force attacks against the Command Center.

---

## 3. STRIDE Threat Model

| Category | Threat | Mitigation |
| :--- | :--- | :--- |
| **S**poofing | Attacker impersonates a managed device or the server. | **Server**: SSL/TLS verification. **Device**: Cryptographic signatures required for re-registration; RSA-handshake for tokens. |
| **T**ampering | Attacker modifies an update file or remote command. | **Updates**: RSA-4096 signatures + MIME verification. **Commands**: API/Model regex validation + shell-less execution. |
| **R**epudiation | Admin denies triggering a sensitive command. | **Audit Logs**: Database-backed trails with redacted sensitive metadata and throttled heartbeat tracking. |
| **I**nformation Disclosure | Attacker extracts secrets from the DB or logs. | **DB**: HKDF-isolated AES-256 encryption. **Logs**: Recursive scrubbing of sensitive keys (tokens, passwords). |
| **D**enial of Service | Attacker floods the API with requests. | **Throttling**: Per-device identity-aware rate limiting (300/min generic, 20/hr register). |
| **E**levation of Privilege | Compromised agent executes commands as SYSTEM. | **Isolation**: Pull-only architecture; server-side permission checks; shlex-split command execution. |

---

## 4. Risk Analysis

| Vulnerability | Likelihood | Impact | Risk Level | Mitigation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Remote Shell Injection** | Very Low | Critical | **High** | **Mitigated**: API/Model validators + Shell-less agent execution. |
| **Insecure Update Delivery** | Very Low | Critical | **Medium** | **Mitigated**: RSA-4096 signing + MIME-type content inspection. |
| **Refresh Token Interception** | Very Low | High | **Medium** | **Mitigated**: Hybrid RSA-AES encryption during handshake. |
| **IP Spoofing** | Low | Medium | **Low** | **Mitigated**: NAT-aware source prioritization and dashboard mismatch flags. |
| **Log Credential Leakage** | Very Low | Medium | **Low** | **Mitigated**: Recursive sanitization of all system and local agent logs. |

---

## 5. Code Review Findings

### 🛡️ Strengths
- **Zero-Knowledge Architecture**: Private keys never transit the network.
- **Cryptographic Isolation**: HKDF prevents cross-field decryption if a specific key is leaked.
- **Resilient Diagnostics**: PowerShell fallbacks ensure visibility in restricted environments without introducing injection risks.
- **Real-Time SPA Security**: Asynchronous table updates minimize full-page re-renders, reducing traditional XSS vectors.

---
**Security Status: HARDENED**
*Last Audit: January 2026*