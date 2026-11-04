# Agent Profile & Operating Principles Directory (`.agent/`)

This directory maintains the persistent role definitions, operating principles, and governance rules for autonomous agent instances operating within the **StockLamPlus** codebase.

---

## 1. Directory Architectural Role & Scope
- **Agent Identity Definition**: Houses dedicated markdown profiles (`agy[x].md`) specifying domain authority, assigned scopes, and operational guidelines.
- **Governance Hierarchy**: Establishes executive priority, where rules defined in an agent's individual profile supersede default configurations.
- **Workflow Integrity**: Ensures all agents comply with branch naming conventions, git identity requirements, English documentation rules, and testing gatekeeper workflows.

---

## 2. Itemized Breakdown of Directory Files
- **[`agy51.md`](file:///home/pluto/projects/StockLamPlus/.agent/agy51.md)**:
  - *Agent ID*: `agy51` (Frontend Engineer & UI Auditor).
  - *Domain Scope*: PySide6 user interface components, peripheral device hardware integration (Windows Raw Input / Linux evdev), multi-desk workstation segregation (Order Desk, Cashier Desk, Dispatch Desk, SAV Kanban), design system tokens, and accessibility standards.
  - *Git Requirements*: Exclusive work on `frontend/agy51-*` branches with author `MohammedBoure`.

---

## 3. Usage & Governance Notes
- Agent profiles are read at session initialization to configure behavioral guidelines and validation constraints.
- Modifying an agent profile immediately updates the governing principles for subsequent agent actions.
