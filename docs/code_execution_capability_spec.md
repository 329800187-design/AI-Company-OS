# Code Execution Capability Specification

`code_execution` is currently a registered but disabled Boss action connector. It
must not execute code, system commands, or external operations in any deployment.
This document defines mandatory acceptance gates for any future proposal to enable
the capability.

## Mandatory implementation gates

1. Execution must run only inside an isolated sandbox, such as a container or
   virtualized environment. It must never directly access the host filesystem,
   processes, or credentials.
2. Allowed operations must be defined by an explicit allowlist. A blacklist,
   keyword filter, or prompt-only restriction is insufficient.
3. Every request must follow the governed `propose → preflight → approve →
   execute` sequence. No endpoint, API key, configuration, or connector may add
   a call-that-executes shortcut.
4. Resource limits must be configurable and enforced for execution duration,
   memory, and outbound network access.
5. An immutable audit log must record who initiated the request, when it ran,
   the approved operation, and its result. Credentials and secrets must never be
   included in the action payload or audit record.
6. Availability should be limited to an explicitly approved subscription tier
   and must be enforced at the request boundary.

## Current behavior

The current connector is intentionally inert: its preflight always reports that
the capability is unavailable, and any execution attempt is rejected before any
operation can occur.
