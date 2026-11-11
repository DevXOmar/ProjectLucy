"""UPI syntax previews only. All seeded recipients are synthetic and unverified.

Formatting a URI provides neither merchant authorization nor payment settlement.
No live provider adapter or payment handoff is enabled in this application.
"""

from __future__ import annotations

import re
from urllib.parse import quote, urlencode

UPI_CURRENCY = "INR"
PAYTM_SCHEME = "paytmmp://pay"
UPI_SCHEME = "upi://pay"

# NPCI/UPI handle format: identifier@psp-handle.
VPA_PATTERN = re.compile(r"^[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}$")


def is_valid_vpa(vpa: str) -> bool:
    """True when the string is a structurally valid UPI virtual payment address."""
    return bool(VPA_PATTERN.match(vpa or ""))


def vpa_for_merchant(name: str, suffix: str = "paytm", unique_hint: int | None = None) -> str:
    """Build a plausible merchant VPA such as ``sharmakirana@paytm`` from a shop name."""
    words = [re.sub(r"[^a-z0-9]", "", word.lower()) for word in name.split()]
    words = [word for word in words if word]
    handle = "".join(words[:2])[:18] or "merchant"
    if unique_hint is not None:
        handle = f"{handle}{unique_hint}"
    return f"{handle}@{suffix}"


def vpa_for_customer(name: str, customer_id: int, suffix: str = "paytm") -> str:
    """Build a plausible payer VPA such as ``aarav.reddy41@paytm`` from a customer name."""
    words = [re.sub(r"[^a-z0-9]", "", word.lower()) for word in name.split()]
    words = [word for word in words if word]
    handle = ".".join(words[:2])[:20] or "payer"
    return f"{handle}{customer_id}@{suffix}"


def upi_params(
    payee_vpa: str,
    payee_name: str,
    amount: float,
    note: str,
    order_id: str | None = None,
) -> dict[str, str]:
    """The standard NPCI UPI URI parameter set, in the conventional order."""
    params = {
        "pa": payee_vpa,
        "pn": payee_name,
        "am": f"{float(amount):.2f}",
        "cu": UPI_CURRENCY,
        "tn": note,
    }
    if order_id:
        # Preview reference only; not evidence of an authorized payment.
        params["tr"] = order_id
    return params


def build_upi_link(
    scheme: str,
    payee_vpa: str,
    payee_name: str,
    amount: float,
    note: str,
    order_id: str | None = None,
) -> str:
    """Percent-encode the UPI parameters onto a deep-link scheme.

    ``quote_via=quote`` keeps spaces as ``%20`` rather than ``+``, which is what
    UPI apps expect inside ``pn`` and ``tn``. ``@`` is left raw (RFC 3986 allows it
    in a query) because that is the form real merchant UPI links use.
    """
    query = urlencode(
        upi_params(payee_vpa, payee_name, amount, note, order_id),
        quote_via=quote,
        safe="@",
    )
    return f"{scheme}?{query}"


def payment_intents(
    payee_vpa: str,
    payee_name: str,
    amount: float,
    note: str,
    order_id: str | None = None,
) -> dict[str, str]:
    """Both deep links for one payment: the Paytm handler and the universal fallback."""
    return {
        "paytm_intent": build_upi_link(PAYTM_SCHEME, payee_vpa, payee_name, amount, note, order_id),
        "upi_intent": build_upi_link(UPI_SCHEME, payee_vpa, payee_name, amount, note, order_id),
    }
