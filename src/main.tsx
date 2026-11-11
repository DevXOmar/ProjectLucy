import React from "react";
import ReactDOM from "react-dom/client";
import Root from "./Root";
import { AppProvider } from "./context/AppProvider";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProvider>
      <Root />
    </AppProvider>
  </React.StrictMode>
);
