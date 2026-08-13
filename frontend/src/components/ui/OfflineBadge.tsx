"use client";

import { useEffect, useState } from "react";

interface CoreStatus {
  ready: boolean;
  cached: string[];
  missing: string[];
}

function askCoreStatus(worker: ServiceWorker): Promise<CoreStatus> {
  return new Promise((resolve, reject) => {
    const channel = new MessageChannel();
    const timeout = window.setTimeout(() => reject(new Error("Service worker status timeout")), 3000);
    channel.port1.onmessage = (event: MessageEvent<CoreStatus>) => {
      window.clearTimeout(timeout);
      resolve(event.data);
    };
    worker.postMessage({ type: "CORE_STATUS" }, [channel.port2]);
  });
}

export function OfflineBadge() {
  const [online, setOnline] = useState(true);
  const [coreReady, setCoreReady] = useState(false);
  const [registrationError, setRegistrationError] = useState(false);

  useEffect(() => {
    setOnline(navigator.onLine);
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);

    async function refreshOfflineStatus() {
      if (!("serviceWorker" in navigator)) {
        setRegistrationError(true);
        return;
      }
      try {
        const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
        const readyRegistration = await navigator.serviceWorker.ready;
        const worker = readyRegistration.active ?? registration.active ?? registration.waiting;
        if (!worker) throw new Error("Service worker is not active");
        const status = await askCoreStatus(worker);
        setCoreReady(status.ready);
        setRegistrationError(false);
      } catch {
        setRegistrationError(true);
      }
    }
    const onControllerChange = () => { void refreshOfflineStatus(); };
    navigator.serviceWorker?.addEventListener("controllerchange", onControllerChange);
    void refreshOfflineStatus();

    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      navigator.serviceWorker?.removeEventListener("controllerchange", onControllerChange);
    };
  }, []);

  const label = registrationError
    ? "Offline no disponible"
    : !online
      ? coreReady ? "Sin conexión · motor FREE listo" : "Sin conexión · instalación incompleta"
      : coreReady ? "Online · offline listo" : "Online · preparando offline";
  const colors = registrationError
    ? "bg-red-100 text-red-800"
    : !online
      ? "bg-amber-100 text-amber-900"
      : coreReady ? "bg-emerald-100 text-emerald-800" : "bg-white/80 text-gray-700";

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${colors}`} role="status" aria-live="polite" data-offline-ready={coreReady ? "true" : "false"}>
      {label}
    </span>
  );
}
