import { useLayoutEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { getServiceReadiness } from "@/features/health/api";
import { useSwissAIPoolSettings } from "@/features/swissai/hooks";

export const STATUS_BAR_DEFAULT_HEIGHT_PX = 40;
export interface StatusBarProps { onHeightChange?: (height: number) => void }

export function StatusBar({ onHeightChange }: StatusBarProps = {}) {
  const ref = useRef<HTMLElement>(null);
  const ready = useQuery({ queryKey: ["health", "ready"], queryFn: getServiceReadiness, refetchInterval: 30000 });
  const settings = useSwissAIPoolSettings();
  useLayoutEffect(() => {
    if (!ref.current || !onHeightChange) return;
    const report = () => onHeightChange(Math.max(STATUS_BAR_DEFAULT_HEIGHT_PX, ref.current?.offsetHeight ?? 0));
    report(); const observer = new ResizeObserver(report); observer.observe(ref.current);
    return () => observer.disconnect();
  }, [onHeightChange]);
  return <footer ref={ref} className="fixed bottom-0 left-0 right-0 z-50 border-t bg-background/95 px-4 py-2 backdrop-blur-xl">
    <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted-foreground">
      <span>Service: {ready.data?.status === "ok" ? "Ready" : ready.isPending ? "Checking…" : "Not ready"}</span>
      <span>Routing: {settings.data?.strategy.replaceAll("_", " ") ?? "—"}</span>
      <span>SwissAI pricing: unknown</span><span>Version: {__APP_VERSION__}</span>
      <a className="ml-auto underline" href="https://github.com/dragmakex/swissai-lb" target="_blank" rel="noreferrer">SwissAI LB</a>
    </div>
  </footer>;
}
