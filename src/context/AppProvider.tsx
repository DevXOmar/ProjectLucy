import { ReactNode, useMemo, useState } from "react";
import type { Role } from "../lib/api";
import { AppContext } from "./AppContext";

export function AppProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>("customer");
  const [customerId, setCustomerId] = useState(6);
  const [merchantId, setMerchantId] = useState(1);

  const value = useMemo(
    () => ({ role, setRole, customerId, setCustomerId, merchantId, setMerchantId }),
    [role, customerId, merchantId]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
