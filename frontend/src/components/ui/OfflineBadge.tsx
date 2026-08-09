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

function waitForController(): Promise<void> {
  if (navigator.serviceWorker.controller) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
      reject(new Error("Service worker control timeout"));
    }, 5000);
    function onControllerChange() {
      window.clearTimeout(timeout);
      resolve();
    }
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange, { once: true });
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

    async function register() {
      if (!("serviceWorker" in navigator)) return;
      try {
        const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
        const readyRegistration = await navigator.serviceWorker.ready;
        await waitForController();
        const worker = readyRegistration.active ?? registration.active ?? registration.waiting;
        if (!worker) return;
        const status = await askCoreStatus(worker);
        setCoreReady(status.ready);
      } catch {
        setRegistrationError(true);
      }
    }
    void register();

    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
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
