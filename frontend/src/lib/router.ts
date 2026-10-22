/** Routeur minimal par hash (#/…) : adapté à une application locale, sans dépendance. */

import { useEffect, useState } from "react";

export type Route = { name: "convert"; id: string | null } | { name: "history" } | { name: "settings" };

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, "") || "/";
  const conversion = /^\/conversions\/([0-9a-f]{12})$/.exec(path);
  if (conversion?.[1]) return { name: "convert", id: conversion[1] };
  if (path === "/historique") return { name: "history" };
  if (path === "/reglages") return { name: "settings" };
  return { name: "convert", id: null };
}

export function navigate(path: string): void {
  window.location.hash = path;
}

/** Adresse d'une conversion. */
export const conversionPath = (id: string) => `/conversions/${id}`;

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
