"""Provider boundary: no live payment adapter is installed in Phase 0."""
from typing import Protocol

class PaymentProvider(Protocol):
    mode: str
    def initial_status(self) -> str: ...
    def verify_event(self, status: str) -> str: ...

class DemoPaymentProvider:
    mode = 'DEMO_SIMULATED'
    def initial_status(self):
        return 'PENDING'
    def verify_event(self, status):
        if status not in {'CONFIRMED', 'FAILED', 'CANCELLED'}:
            raise ValueError('Unsupported demo event')
        return self.mode

provider: PaymentProvider = DemoPaymentProvider()
