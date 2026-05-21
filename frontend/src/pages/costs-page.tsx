/**
 * CostsPage - dashboard détaillé tokens & coûts (Phase 5).
 *
 * Affichage : KPIs (today / 7d / 30d), breakdown 7 jours, répartition par
 * projet sur 30 jours, export CSV pour facturation.
 */

import { useState } from 'react';

import { Spark } from '@/components/eldir/spark';
import { apiClient } from '@/lib/api/client';
import { useCostsDashboard } from '@/lib/api/queries';
import type { CostTotalsRead } from '@/lib/types/api';

export function CostsPage(): JSX.Element {
  const dashboard = useCostsDashboard();
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const date = new Date().toISOString().slice(0, 10);
      await apiClient.download('/costs/export.csv', `eldir-costs-${date}.csv`);
    } finally {
      setExporting(false);
    }
  };

  if (dashboard.isLoading) {
    return (
      <main className="p-6 font-mono text-sm text-eldir-gray">
        Chargement des coûts…
      </main>
    );
  }
  if (dashboard.isError || !dashboard.data) {
    return (
      <main className="p-6 font-mono text-sm text-eldir-red">
        Impossible de charger les coûts.
      </main>
    );
  }

  const data = dashboard.data;
  const dailyCosts = data.daily.map((d) => d.cost_usd);
  const dailyTokens = data.daily.map(
    (d) => d.input_tokens + d.output_tokens,
  );

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-4 md:p-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="eldir-caps">Costs</div>
          <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
            Tokens &amp; coûts
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-eldir-ink-2">
            Suivi en temps réel basé sur les <code className="font-mono">ResultMessage.usage</code> du
            Claude Agent SDK. Une ligne par tour, agrégée ci-dessous.
          </p>
        </div>
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2 disabled:opacity-50"
        >
          {exporting ? 'Export…' : 'Export CSV'}
        </button>
      </header>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <KpiCard label="Aujourd'hui" totals={data.today} />
        <KpiCard label="7 derniers jours" totals={data.last_7_days} />
        <KpiCard label="30 derniers jours" totals={data.last_30_days} />
      </section>

      <section>
        <div className="eldir-caps mb-2">Coût par jour (7 derniers jours)</div>
        <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
          {dailyCosts.some((c) => c > 0) ? (
            <>
              <Spark
                data={dailyCosts}
                width={720}
                height={80}
                fill="hsl(var(--eldir-orange) / 0.15)"
              />
              <div className="mt-3 grid grid-cols-7 gap-1 font-mono text-2xs text-eldir-gray">
                {data.daily.map((d) => (
                  <div key={d.day} className="text-center">
                    <div className="font-semibold text-eldir-ink">
                      ${d.cost_usd.toFixed(2)}
                    </div>
                    <div>{d.day.slice(5)}</div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="font-mono text-sm text-eldir-gray">
              Aucun coût enregistré pour les 7 derniers jours.
            </p>
          )}
        </div>
      </section>

      <section>
        <div className="eldir-caps mb-2">Tokens par jour</div>
        <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
          {dailyTokens.some((t) => t > 0) ? (
            <Spark
              data={dailyTokens}
              width={720}
              height={60}
              fill="hsl(var(--eldir-gold) / 0.15)"
            />
          ) : (
            <p className="font-mono text-sm text-eldir-gray">
              Aucun token consommé pour les 7 derniers jours.
            </p>
          )}
        </div>
      </section>

      <section>
        <div className="eldir-caps mb-2">Répartition par projet (30j)</div>
        <div className="overflow-hidden rounded-eldir border border-eldir-gray-3 bg-eldir-cream">
          {data.by_project.length === 0 ? (
            <p className="p-4 font-mono text-sm text-eldir-gray">
              Aucun coût rattaché à un projet sur cette période.
            </p>
          ) : (
            <table className="w-full font-mono text-xs">
              <thead className="border-b border-eldir-gray-3 bg-eldir-paper">
                <tr className="text-left text-eldir-gray">
                  <th className="px-3 py-2">Projet</th>
                  <th className="px-3 py-2 text-right">Input</th>
                  <th className="px-3 py-2 text-right">Output</th>
                  <th className="px-3 py-2 text-right">Coût</th>
                </tr>
              </thead>
              <tbody>
                {data.by_project.map((p) => (
                  <tr
                    key={p.project_id}
                    className="border-b border-eldir-gray-3/50 last:border-0"
                  >
                    <td className="px-3 py-2 text-eldir-ink">
                      {p.project_name ?? p.project_id.slice(0, 8)}
                    </td>
                    <td className="px-3 py-2 text-right text-eldir-ink-2">
                      {formatTokens(p.input_tokens)}
                    </td>
                    <td className="px-3 py-2 text-right text-eldir-ink-2">
                      {formatTokens(p.output_tokens)}
                    </td>
                    <td className="px-3 py-2 text-right font-semibold text-eldir-ink">
                      ${p.cost_usd.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </main>
  );
}

function KpiCard({
  label,
  totals,
}: {
  label: string;
  totals: CostTotalsRead;
}): JSX.Element {
  const totalTokens =
    totals.input_tokens +
    totals.output_tokens +
    totals.cache_read_tokens +
    totals.cache_write_tokens;
  const cacheRatio = totalTokens
    ? Math.round(((totals.cache_read_tokens) / totalTokens) * 100)
    : 0;
  return (
    <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
      <div className="eldir-caps">{label}</div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="font-mono text-2xl font-bold text-eldir-ink">
          ${totals.cost_usd.toFixed(2)}
        </span>
        <span className="font-mono text-2xs text-eldir-gray">
          {totals.num_turns} tour{totals.num_turns > 1 ? 's' : ''}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-1 font-mono text-2xs text-eldir-gray">
        <dt>Input</dt>
        <dd className="text-right text-eldir-ink-2">
          {formatTokens(totals.input_tokens)}
        </dd>
        <dt>Output</dt>
        <dd className="text-right text-eldir-ink-2">
          {formatTokens(totals.output_tokens)}
        </dd>
        <dt>Cache read</dt>
        <dd className="text-right text-eldir-ink-2">
          {formatTokens(totals.cache_read_tokens)}
        </dd>
        <dt>Cache write</dt>
        <dd className="text-right text-eldir-ink-2">
          {formatTokens(totals.cache_write_tokens)}
        </dd>
        {totalTokens > 0 && (
          <>
            <dt>Cache ratio</dt>
            <dd className="text-right text-eldir-orange">{cacheRatio}%</dd>
          </>
        )}
      </dl>
    </div>
  );
}

function formatTokens(n: number): string {
  if (n === 0) return '0';
  if (n < 1_000) return String(n);
  if (n < 1_000_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}
