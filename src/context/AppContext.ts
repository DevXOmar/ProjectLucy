import { createContext } from "react";
import type { Role } from "../lib/api";

export type AppState = {
  role: Role;
  setRole: (role: Role) => void;
  customerId: number;
  setCustomerId: (id: number) => void;
  merchantId: number;
  setMerchantId: (id: number) => void;
};

export const AppContext = createContext<AppState | null>(null);
