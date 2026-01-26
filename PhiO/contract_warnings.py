"""Warning categories for contract validation.

Placed at repository root for stable imports (works from tests/ and scripts).
"""

class ContractWarning(UserWarning):
    """Warning that indicates a contract violation (can be promoted to error in CI)."""
    pass


class ContractInfoWarning(UserWarning):
    """Informational warning about the contract (should not fail tests)."""
    pass
