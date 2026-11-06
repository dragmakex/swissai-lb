import { SwissAIOverview } from "@/features/swissai/pool-overview";
import { useSwissAIKeys } from "@/features/swissai/hooks";
import { RecentRequestHealth } from "@/features/swissai/recent-health";
import { downloadRequestLogs } from "@/features/swissai/request-log-export";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Columns3, RefreshCw, RotateCcw } from "lucide-react";

import { AlertMessage } from "@/components/alert-message";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SpinnerBlock } from "@/components/ui/spinner";
import { DashboardSkeleton } from "@/features/dashboard/components/dashboard-skeleton";
import { ConversationsView } from "@/features/dashboard/components/conversations-view";
import { ConversationTimeframeSelect } from "@/features/dashboard/components/filters/conversation-timeframe-select";
import { DashboardViewSelector } from "@/features/dashboard/components/filters/dashboard-view-selector";
import { OverviewTimeframeSelect } from "@/features/dashboard/components/filters/overview-timeframe-select";
import { RequestFilters } from "@/features/dashboard/components/filters/request-filters";
import { RecentRequestsTable } from "@/features/dashboard/components/recent-requests-table";
import { StatsGrid } from "@/features/dashboard/components/stats-grid";
import { TelemetryConsentDialog } from "@/features/settings/components/telemetry-consent-dialog";
import { useAuthStore, usePermission } from "@/features/auth/hooks/use-auth";
import { useDashboard, useDashboardProjections } from "@/features/dashboard/hooks/use-dashboard";
import { useConversations } from "@/features/dashboard/hooks/use-conversations";
import { useRequestLogTablePreferences } from "@/features/dashboard/hooks/use-request-log-table-preferences";
import { useRequestLogs } from "@/features/dashboard/hooks/use-request-logs";
import { REQUEST_LOG_COLUMN_OPTIONS } from "@/features/dashboard/request-log-columns";
import { buildDashboardView } from "@/features/dashboard/utils";
import {
  DEFAULT_OVERVIEW_TIMEFRAME,
  parseDashboardView,
  parseConversationTimeframe,
  parseOverviewTimeframe,
  type ConversationTimeframe,
  type OverviewTimeframe,
} from "@/features/dashboard/schemas";
import { useThemeStore } from "@/hooks/use-theme";
import { REQUEST_STATUS_LABELS } from "@/utils/constants";
import { getErrorMessageOrNull } from "@/utils/errors";
import { formatModelLabel, formatSlug } from "@/utils/formatters";
import { usePrivacyStore } from "@/hooks/use-privacy";

const MODEL_OPTION_DELIMITER = ":::";

type RetainedDashboardLoadError = {
  timeframe: OverviewTimeframe;
  message: string;
};

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const {
    visibleColumns,
    columnWidths,
    toggleColumn,
    setColumnWidth,
    restoreDefaultLayout,
  } = useRequestLogTablePreferences();
  const resolvedLanguage = i18n.resolvedLanguage;
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const isDark = useThemeStore((s) => s.theme === "dark");
  // Each surface follows the permission its backend route demands, not the
  // coarse `write` alias: conversations and archives need `conversations:read`,
  // account actions `accounts:write`, the API-key filter `api_keys:read`.
  const canReadApiKeys = usePermission("api_keys:read");
  const initialized = useAuthStore((state) => state.initialized);
  const hasConversationsRead = usePermission("conversations:read");
  const canReadConversations = initialized && hasConversationsRead;
  const overviewTimeframe = useMemo(
    () => parseOverviewTimeframe(searchParams.get("overviewTimeframe")),
    [searchParams],
  );
  const conversationTimeframe = useMemo(
    () => parseConversationTimeframe(searchParams.get("conversationTimeframe")),
    [searchParams],
  );
  const requestedDashboardView = useMemo(
    () => parseDashboardView(searchParams.get("view")),
    [searchParams],
  );
  const dashboardView = canReadConversations ? requestedDashboardView : "request-logs";
  useEffect(() => {
    if (!initialized || canReadConversations || searchParams.get("view") !== "conversations") {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete("view");
    setSearchParams(next, { replace: true });
  }, [initialized, canReadConversations, searchParams, setSearchParams]);
  // Conversation stats must follow the timeframe restored for the active
  // view, including when that state came from a bookmarked URL.
  const dashboardTimeframe =
    dashboardView === "conversations" ? conversationTimeframe : overviewTimeframe;
  const dashboardQuery = useDashboard(dashboardTimeframe);
  const keysQuery = useSwissAIKeys();
  const [retainedDashboardLoadError, setRetainedDashboardLoadError] =
    useState<RetainedDashboardLoadError | null>(null);
  const [overviewRetryTimeframe, setOverviewRetryTimeframe] =
    useState<OverviewTimeframe | null>(null);
  const projectionsQuery = useDashboardProjections(Boolean(dashboardQuery.data));
  const conversationsState = useConversations({
    enabled: canReadConversations && dashboardView === "conversations",
  });
  const { conversationsQuery } = conversationsState;
  // Read-only sessions never see the API-key filter control, so they must not
  // query with one either (URL-carried `apiKeyId` is dropped).
  const { filters, emptyStateFiltersApplied, logsQuery, optionsQuery, updateFilters } = useRequestLogs({
    enabled: dashboardView === "request-logs",
    allowApiKeyFilters: canReadApiKeys,
  });

  const activeListIsFetching = dashboardView === "request-logs"
    ? logsQuery.isFetching
    : conversationsQuery.isFetching;
  const isRefreshing = dashboardQuery.isFetching || projectionsQuery.isFetching || activeListIsFetching;

  const handleRefresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  }, [queryClient]);

  const handleOverviewTimeframeChange = useCallback(
    (timeframe: OverviewTimeframe) => {
      const next = new URLSearchParams(searchParams);
      if (timeframe === DEFAULT_OVERVIEW_TIMEFRAME) {
        next.delete("overviewTimeframe");
      } else {
        next.set("overviewTimeframe", timeframe);
      }
      setSearchParams(next);
    },
    [searchParams, setSearchParams],
  );

  const handleConversationTimeframeChange = useCallback(
    (timeframe: ConversationTimeframe) => {
      conversationsState.updateFilters({ timeframe, offset: 0 });
    },
    [conversationsState],
  );

  const handleDashboardViewChange = useCallback(
    (nextView: "request-logs" | "conversations") => {
      if (nextView === "conversations" && !canReadConversations) {
        return;
      }
      const next = new URLSearchParams(searchParams);
      if (nextView === "request-logs") {
        next.delete("view");
      } else {
        next.set("view", nextView);
      }
      setSearchParams(next);
    },
    [canReadConversations, searchParams, setSearchParams],
  );

  const handleConversationClick = useCallback(
    (conversationId: string) => {
      updateFilters({ conversationId, offset: 0 });
    },
    [updateFilters],
  );

  const handleConversationDismiss = useCallback(() => {
    updateFilters({ conversationId: null, offset: 0 });
  }, [updateFilters]);

  const overview = dashboardQuery.data;
  const logPage = logsQuery.data;

  const view = useMemo(() => {
    void resolvedLanguage;
    if (!overview) {
      return null;
    }
    return buildDashboardView(
      overview,
      logPage?.requests ?? [],
      {
        isDark,
        showAccountBurnrate: false,
      },
      projectionsQuery.data,
    );
  }, [overview, logPage, isDark, projectionsQuery.data, resolvedLanguage]);

  const accountOptions = useMemo(() => {
    const entries = new Map<string, { label: string; isEmail: boolean }>();
    for (const account of overview?.accounts ?? []) {
      const raw = account.displayName || account.email || account.accountId;
      const isEmail = !!account.email && raw === account.email;
      entries.set(account.accountId, { label: raw, isEmail });
    }
    for (const key of keysQuery.data ?? []) {
      entries.set(key.id, { label: key.name, isEmail: false });
    }
    for (const request of logPage?.requests ?? []) {
      if (request.modelSourceKind === "swissai" && request.modelSourceId && !entries.has(request.modelSourceId)) {
        entries.set(request.modelSourceId, { label: request.upstreamKeyLabel ?? request.modelSourceId, isEmail: false });
      }
    }
    return (optionsQuery.data?.accountIds ?? []).map((accountId) => {
      const entry = entries.get(accountId);
      return {
        value: accountId,
        label: entry?.label ?? accountId,
        isEmail: entry?.isEmail ?? false,
      };
    });
  }, [optionsQuery.data?.accountIds, overview?.accounts, keysQuery.data, logPage?.requests]);

  const apiKeyOptions = useMemo(
    () =>
      (optionsQuery.data?.apiKeys ?? []).map((option) => ({
        value: option.id,
        label: option.keyPrefix ? `${option.name} · ${option.keyPrefix}` : option.name,
      })),
    [optionsQuery.data?.apiKeys],
  );

  const modelOptions = useMemo(
    () =>
      (optionsQuery.data?.modelOptions ?? []).map((option) => ({
        value: `${option.model}${MODEL_OPTION_DELIMITER}${option.reasoningEffort ?? ""}`,
        label: formatModelLabel(option.model, option.reasoningEffort),
      })),
    [optionsQuery.data?.modelOptions],
  );

  const blurred = usePrivacyStore((s) => s.blurred);

  const conversationSummary = useMemo(() => {
    const conv = logPage?.conversation;
    if (!conv || !filters.conversationId) {
      return null;
    }
    const cost = t("dashboard.conversation.unknownCost");
    const count = conv.requestCount;
    const suffixParts: string[] = [];

    if (filters.timeframe !== "all") {
      suffixParts.push(filters.timeframe);
    }
    if (filters.statuses.length > 0) {
      const labels = filters.statuses.map(
        (s) => t(`dashboard.requestStatus.${s}`, { defaultValue: REQUEST_STATUS_LABELS[s] ?? s }),
      );
      suffixParts.push(labels.join(", "));
    }
    if (filters.modelOptions.length > 0) {
      const labels = filters.modelOptions.map((raw) => {
        const decoded = modelOptions.find((o) => o.value === raw);
        if (decoded) return decoded.label;
        // Decode from the filter value itself when options are stale/missing
        const [model, ...rest] = raw.split(MODEL_OPTION_DELIMITER);
        const effort = rest.join(MODEL_OPTION_DELIMITER);
        return formatModelLabel(model, effort || null);
      });
      suffixParts.push(labels.join(", "));
    }
    if (filters.accountIds.length > 0) {
      const labels = filters.accountIds.map((id) => {
        const opt = accountOptions.find((o) => o.value === id);
        if (!opt) return t("dashboard.filters.accounts"); // safe fallback: localized label
        const raw = opt.label;
        if (blurred && opt.isEmail) {
          return id.slice(0, 8);
        }
        return raw;
      });
      suffixParts.push(labels.join(", "));
    }
    if (filters.apiKeyIds.length > 0) {
      const labels = filters.apiKeyIds.map((id) => {
        const opt = apiKeyOptions.find((o) => o.value === id);
        return opt?.label ?? t("dashboard.filters.apiKeys"); // safe fallback
      });
      suffixParts.push(labels.join(", "));
    }
    if (filters.search) {
      suffixParts.push(`"${filters.search}"`);
    }

    const codeClass = "rounded bg-muted px-1 py-0.5 text-xs font-mono";

    if (suffixParts.length > 0) {
      return (
        <Trans
          i18nKey="dashboard.conversation.summaryWithFilters"
          values={{ id: filters.conversationId, count, cost, filters: suffixParts.join(", ") }}
          components={[
            <code key="id" className={codeClass} />,
            <code key="count" className={codeClass} />,
            <code key="cost" className={codeClass} />,
          ]}
        />
      );
    }
    return (
      <Trans
        i18nKey="dashboard.conversation.summary"
        values={{ id: filters.conversationId, count, cost }}
        components={[
          <code key="id" className={codeClass} />,
          <code key="count" className={codeClass} />,
          <code key="cost" className={codeClass} />,
        ]}
      />
    );
  }, [logPage?.conversation, filters, t, accountOptions, apiKeyOptions, modelOptions, blurred]);

  const statusOptions = useMemo(
    () =>
      (optionsQuery.data?.statuses ?? []).map((status) => ({
        value: status,
        label: t(`dashboard.requestStatus.${status}`, { defaultValue: REQUEST_STATUS_LABELS[status] ?? formatSlug(status) }),
      })),
    [optionsQuery.data?.statuses, t],
  );

  const dashboardLoadError = getErrorMessageOrNull(dashboardQuery.error);
  if (
    retainedDashboardLoadError !== null &&
    (overview || retainedDashboardLoadError.timeframe !== dashboardTimeframe)
  ) {
    setRetainedDashboardLoadError(null);
  } else if (
    !overview &&
    dashboardLoadError !== null &&
    (retainedDashboardLoadError === null ||
      retainedDashboardLoadError.message !== dashboardLoadError)
  ) {
    setRetainedDashboardLoadError({
      timeframe: dashboardTimeframe,
      message: dashboardLoadError,
    });
  }
  const displayedDashboardLoadError =
    dashboardLoadError ??
    (retainedDashboardLoadError?.timeframe === dashboardTimeframe
      ? retainedDashboardLoadError.message
      : null);
  const overviewRetryBusy =
    dashboardQuery.isFetching || overviewRetryTimeframe === dashboardTimeframe;
  const errorMessage =
    (overview ? dashboardLoadError : null) ||
    (dashboardView === "request-logs" && optionsQuery.error instanceof Error && optionsQuery.error.message) ||
    null;

  return (
    <div className="animate-fade-in-up space-y-8">
      <TelemetryConsentDialog />
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("dashboard.page.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("dashboard.page.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dashboardView === "request-logs" ? (
            <OverviewTimeframeSelect
              value={overviewTimeframe}
              onChange={handleOverviewTimeframeChange}
            />
          ) : null}
          {dashboardView === "conversations" ? (
            <ConversationTimeframeSelect
              value={conversationTimeframe}
              onChange={handleConversationTimeframeChange}
            />
          ) : null}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
            aria-label={t("dashboard.page.refresh")}
            title={t("dashboard.page.refresh")}
          >
            <RefreshCw className={`h-4 w-4${isRefreshing ? " animate-spin" : ""}`} aria-hidden="true" />
          </button>
        </div>
      </div>

      {errorMessage ? <AlertMessage variant="error">{errorMessage}</AlertMessage> : null}

      {(dashboardQuery.isPending || dashboardQuery.isFetching) &&
      !view &&
      displayedDashboardLoadError === null ? (
        <DashboardSkeleton />
      ) : !view ? (
        <div className="space-y-3 rounded-xl border bg-card p-4">
          <div role="alert">
            <AlertMessage variant="error">{displayedDashboardLoadError ?? "Request failed"}</AlertMessage>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-busy={overviewRetryBusy}
            disabled={overviewRetryBusy}
            onClick={() => {
              const retryTimeframe = dashboardTimeframe;
              setRetainedDashboardLoadError({
                timeframe: retryTimeframe,
                message: displayedDashboardLoadError ?? "Request failed",
              });
              setOverviewRetryTimeframe(retryTimeframe);
              void dashboardQuery.refetch().finally(() => {
                setOverviewRetryTimeframe((current) =>
                  current === retryTimeframe ? null : current,
                );
              });
            }}
          >
            {t("common.actions.retry")}
          </Button>
        </div>
      ) : (
        <>
          <StatsGrid stats={view.stats} />

          <SwissAIOverview />
          {dashboardView === "request-logs" ? <RecentRequestHealth requests={logPage?.requests ?? []} /> : null}

          <section className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <DashboardViewSelector
                value={dashboardView}
                onChange={handleDashboardViewChange}
                showConversations={canReadConversations}
              />
              <div className="h-px min-w-8 flex-1 bg-border" />
              {dashboardView === "request-logs" ? (
                <>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button type="button" variant="outline" size="sm">
                        <Columns3 className="mr-2 h-4 w-4" />
                        {t("dashboard.requests.columnLayout.columns", {
                          count: visibleColumns.length,
                        })}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-52">
                      <DropdownMenuLabel>
                        {t("dashboard.requests.columnLayout.visibleColumns")}
                      </DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      {REQUEST_LOG_COLUMN_OPTIONS.map((column) => {
                        const isVisible = visibleColumns.includes(column.id);
                        return (
                          <DropdownMenuCheckboxItem
                            key={column.id}
                            checked={isVisible}
                            disabled={isVisible && visibleColumns.length === 1}
                            onCheckedChange={() => toggleColumn(column.id)}
                            onSelect={(event) => event.preventDefault()}
                          >
                            {t(column.translationKey)}
                          </DropdownMenuCheckboxItem>
                        );
                      })}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button type="button" variant="outline" size="sm" disabled={!logPage?.requests.length}
                    onClick={() => downloadRequestLogs(logPage?.requests ?? [])}>
                    Export visible page
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={t("dashboard.requests.columnLayout.restoreDefault")}
                    title={t("dashboard.requests.columnLayout.restoreDefault")}
                    onClick={restoreDefaultLayout}
                  >
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                </>
              ) : null}
            </div>
            {canReadConversations && dashboardView === "conversations" ? (
              <ConversationsView state={conversationsState} accounts={overview?.accounts ?? []} />
            ) : (
              <>
                {logsQuery.error ? (
                  <div className="space-y-3 rounded-xl border bg-card p-4">
                    <div role="alert">
                      <AlertMessage variant="error">{logsQuery.error.message}</AlertMessage>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void logsQuery.refetch();
                      }}
                      disabled={logsQuery.isFetching}
                    >
                      {t("common.actions.retry")}
                    </Button>
                  </div>
                ) : null}
                {logsQuery.isPending && !logPage ? (
                  <div className="rounded-xl border bg-card py-8">
                    <SpinnerBlock />
                  </div>
                ) : logPage ? (
                  <>
                    <RequestFilters
                      filters={filters}
                      accountOptions={accountOptions}
                      apiKeyOptions={apiKeyOptions}
                      modelOptions={modelOptions}
                      statusOptions={statusOptions}
                      showApiKeyFilter={canReadApiKeys}
                      onSearchChange={(search) => updateFilters({ search, offset: 0 })}
                      onTimeframeChange={(timeframe) => updateFilters({ timeframe, offset: 0 })}
                      onAccountChange={(accountIds) => updateFilters({ accountIds, offset: 0 })}
                      onApiKeyChange={(apiKeyIds) => updateFilters({ apiKeyIds, offset: 0 })}
                      onModelChange={(modelOptionsSelected) =>
                        updateFilters({ modelOptions: modelOptionsSelected, offset: 0 })
                      }
                      onStatusChange={(statuses) => updateFilters({ statuses, offset: 0 })}
                      onConversationDismiss={handleConversationDismiss}
                      onReset={() =>
                        updateFilters({
                          search: "",
                          timeframe: "all",
                          accountIds: [],
                          apiKeyIds: [],
                          modelOptions: [],
                          statuses: [],
                          conversationId: null,
                          offset: 0,
                        })
                      }
                    />
                    {conversationSummary ? (
                      <div className="rounded-xl border bg-card p-4">
                        <p className="text-sm text-muted-foreground">{conversationSummary}</p>
                      </div>
                    ) : null}
                    <div className="transition-opacity duration-200">
                      <RecentRequestsTable
                        requests={view.requestLogs}
                        accounts={overview?.accounts ?? []}
                        total={logPage.total}
                        visibleColumns={visibleColumns}
                        columnWidths={columnWidths}
                        onColumnWidthChange={setColumnWidth}
                        limit={filters.limit}
                        offset={filters.offset}
                        hasMore={logPage.hasMore}
                        filtersApplied={emptyStateFiltersApplied}
                        onLimitChange={(limit) => updateFilters({ limit, offset: 0 })}
                        onOffsetChange={(offset) => updateFilters({ offset })}
                        onConversationClick={handleConversationClick}
                      />
                    </div>
                  </>
                ) : null}
              </>
            )}
          </section>
        </>
      )}


    </div>
  );
}
