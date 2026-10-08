"""5-tier permission model (Project Report, Section 19).

Level 0  Read/search/analyze                       -> automatic
Level 1  Notes, drafts, tests, generated files      -> automatic
Level 2  Project/system changes, deployments        -> approval/configurable
Level 3  Messages, email, public posts               -> explicit confirmation
Level 4  Payments, purchases, financial, locks       -> explicit confirmation, always

Tools declare their level. Levels 0-1 execute immediately. Level 2+ creates a
pending action that must be approved via /api/actions/{id}/approve before it
runs. Every call — auto or approved — is logged.
"""

from enum import IntEnum


class PermissionLevel(IntEnum):
    READ = 0
    GENERATE = 1
    SYSTEM_CHANGE = 2
    COMMUNICATE = 3
    FINANCIAL = 4


AUTO_LEVELS = {PermissionLevel.READ, PermissionLevel.GENERATE}
APPROVAL_REQUIRED_LEVELS = {
    PermissionLevel.SYSTEM_CHANGE,
    PermissionLevel.COMMUNICATE,
    PermissionLevel.FINANCIAL,
}


def requires_approval(level: PermissionLevel) -> bool:
    return level in APPROVAL_REQUIRED_LEVELS
