"""Role enumeration with precedence weights (per ``docs/rbac_matrix.md`` §2.2).

Defines the five end-user roles recognized by the RBAC layer and the
precedence rule ``Superuser > Manager > Session Admin > Driver > Passenger``.
Precedence is encoded as an integer weight on each enum member so that
``Role.satisfies()`` is a simple ``>=`` comparison and external code can
rank, sort, or compare roles without bespoke logic.

The weights are spaced 20 apart so future roles can be inserted without
renumbering (e.g. a new ``MODERATOR`` between ``SESSION_ADMIN`` and
``DRIVER`` could use 50).
"""

from __future__ import annotations

from enum import IntEnum


class Role(IntEnum):
    """End-user roles with precedence weights.

    Higher precedence implies the role satisfies every check that a
    lower-precedence role satisfies. The numeric values are not part of
    the public contract — they only support ordering via
    ``Role.satisfies()`` and are documented for reviewers.
    """

    SUPERUSER = 100
    MANAGER = 80
    SESSION_ADMIN = 60
    DRIVER = 40
    PASSENGER = 20

    def satisfies(self, required: Role) -> bool:
        """Return ``True`` if this role meets or exceeds ``required``.

        Implements the precedence rule from ``docs/rbac_matrix.md`` §2.2:
        a higher-ranked role satisfies any check that a lower-ranked role
        satisfies. Two roles of equal rank satisfy each other.
        """
        return int(self) >= int(required)


__all__ = ["Role"]
