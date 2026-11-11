import { useCallback, useEffect, useState } from "react";
import App from "./App";
import Landing from "./pages/Landing";
import { useApp } from "./context/useApp";

/**
 * Two routes, driven by the URL hash so the landing page is genuinely linkable
 * without pulling in a router dependency:
 *   `#/`      the marketing landing page (default, and any in-page anchor)
 *   `#/app`   the demo app shell
 */
const APP_ROUTE = "#/app";

function currentRoute() {
  return window.location.hash.startsWith(APP_ROUTE) ? "app" : "landing";
}

export default function Root() {
  const { setRole } = useApp();
  const [route, setRoute] = useState<"landing" | "app">(currentRoute);

  useEffect(() => {
    const onHashChange = () => setRoute(currentRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const launchDemo = useCallback(() => {
    // The demo always opens in Customer view, whatever the last session ended on.
    setRole("customer");
    window.location.hash = APP_ROUTE;
    window.scrollTo({ top: 0 });
  }, [setRole]);

  const goToLanding = useCallback(() => {
    window.location.hash = "#/";
    window.scrollTo({ top: 0 });
  }, []);

  if (route === "app") return <App onExitToLanding={goToLanding} />;
  return <Landing onLaunch={launchDemo} />;
}
