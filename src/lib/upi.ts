/** Preview construction only. Synthetic VPAs must never be used for live handoff. */
export const PAYTM_SCHEME = "paytmmp://pay";
export const UPI_SCHEME = "upi://pay";

export type UpiIntentInput = {
  payeeVpa: string;
  payeeName: string;
  amount: number;
  note: string;
  orderId?: string;
};

/** Percent-encode a UPI query value: spaces become %20, `@` stays raw as in real merchant links. */
function encodeUpiValue(value: string) {
  return encodeURIComponent(value).replace(/%40/g, "@");
}

export function upiParams({ payeeVpa, payeeName, amount, note, orderId }: UpiIntentInput) {
  const params: [string, string][] = [
    ["pa", payeeVpa],
    ["pn", payeeName],
    ["am", amount.toFixed(2)],
    ["cu", "INR"],
    ["tn", note]
  ];
  if (orderId) params.push(["tr", orderId]);
  return params;
}

export function buildUpiLink(scheme: string, input: UpiIntentInput) {
  const query = upiParams(input)
    .map(([key, value]) => `${key}=${encodeUpiValue(value)}`)
    .join("&");
  return `${scheme}?${query}`;
}

/** Both deep links for one payment: the Paytm handler and the universal UPI fallback. */
export function paymentIntents(input: UpiIntentInput) {
  return {
    paytmIntent: buildUpiLink(PAYTM_SCHEME, input),
    upiIntent: buildUpiLink(UPI_SCHEME, input)
  };
}

/** NPCI handle format check: identifier@psp. */
export function isValidVpa(vpa: string) {
  return /^[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}$/.test(vpa ?? "");
}
