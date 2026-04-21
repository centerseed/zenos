"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { LoadingState } from "@/components/LoadingState";
import { getCompanies, createCompany } from "@/lib/crm-api";
import type { Company } from "@/lib/crm-api";

// ─── New Company Form ─────────────────────────────────────────────────────────

interface NewCompanyModalProps {
  onClose: () => void;
  onCreated: (company: Company) => void;
  token: string;
}

function NewCompanyModal({ onClose, onCreated, token }: NewCompanyModalProps) {
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [sizeRange, setSizeRange] = useState("");
  const [region, setRegion] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const company = await createCompany(token, {
        name: name.trim(),
        industry: industry.trim() || undefined,
        sizeRange: sizeRange.trim() || undefined,
        region: region.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onCreated(company);
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立失敗");
    }
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-panel border bd-hair rounded-zen p-6 w-full max-w-md shadow-xl">
        <h3 className="text-base font-semibold text-foreground mb-4">新增公司</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs text-dim mb-1">
              公司名稱 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="台灣科技股份有限公司"
              className="w-full bg-base border bd-hair rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-dim focus:outline-none focus:ring-1 focus:ring-primary"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-dim mb-1">產業</label>
              <input
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="製造業"
                className="w-full bg-base border bd-hair rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-dim focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-dim mb-1">規模</label>
              <input
                type="text"
                value={sizeRange}
                onChange={(e) => setSizeRange(e.target.value)}
                placeholder="50-200 人"
                className="w-full bg-base border bd-hair rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-dim focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-dim mb-1">地區</label>
            <input
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="台北"
              className="w-full bg-base border bd-hair rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-dim focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div>
            <label className="block text-xs text-dim mb-1">備忘</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="備注..."
              rows={2}
              className="w-full bg-base border bd-hair rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-dim focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            />
          </div>
          {error && (
            <p className="text-xs text-red-400">{error}</p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-lg bg-soft text-foreground hover:bg-soft transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="px-4 py-2 text-sm rounded-lg bg-accent-soft text-primary-foreground hover:bg-accent-soft transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "建立中..." : "建立"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── CompaniesPage ────────────────────────────────────────────────────────────

function CompaniesPage() {
  const { user, partner } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [token, setToken] = useState("");

  useEffect(() => {
    if (!user || !partner) return;

    async function load() {
      const t = await user!.getIdToken();
      setToken(t);
      try {
        const fetched = await getCompanies(t);
        setCompanies(fetched);
      } catch (err) {
        console.error("Failed to load companies:", err);
      }
      setLoading(false);
    }

    load();
  }, [user, partner]);

  function handleCompanyCreated(company: Company) {
    setCompanies((prev) => [company, ...prev]);
    setShowModal(false);
  }

  return (
    <div className="min-h-screen">
      <main id="main-content" className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Link
              href="/clients"
              className="text-sm text-dim hover:text-foreground transition-colors"
            >
              ← 客戶
            </Link>
            <h2 className="text-lg font-semibold text-foreground">公司列表</h2>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="px-3 py-1.5 text-sm rounded-lg bg-accent-soft text-primary-foreground hover:bg-accent-soft transition-colors"
          >
            + 新增公司
          </button>
        </div>

        {loading ? (
          <LoadingState label="載入公司列表..." />
        ) : companies.length === 0 ? (
          <div className="text-center py-16 bg-panel rounded-zen border bd-hair">
            <p className="text-dim">尚無公司資料</p>
            <button
              onClick={() => setShowModal(true)}
              className="mt-3 px-4 py-2 text-sm rounded-lg bg-accent-soft text-primary-foreground hover:bg-accent-soft transition-colors"
            >
              新增第一家公司
            </button>
          </div>
        ) : (
          <div className="bg-panel border bd-hair rounded-zen overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bd-hair">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-dim uppercase tracking-wide">
                    公司名稱
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-dim uppercase tracking-wide hidden sm:table-cell">
                    產業
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-dim uppercase tracking-wide hidden md:table-cell">
                    規模
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-dim uppercase tracking-wide hidden md:table-cell">
                    地區
                  </th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => (
                  <tr
                    key={company.id}
                    className="border-b bd-hair last:border-0 hover:bg-soft transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/clients/companies/${company.id}`}
                        className="font-medium text-foreground hover:text-primary transition-colors"
                      >
                        {company.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-dim hidden sm:table-cell">
                      {company.industry ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-dim hidden md:table-cell">
                      {company.sizeRange ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-dim hidden md:table-cell">
                      {company.region ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {showModal && (
        <NewCompanyModal
          token={token}
          onClose={() => setShowModal(false)}
          onCreated={handleCompanyCreated}
        />
      )}
    </div>
  );
}

export default function Page() {
  return <CompaniesPage />;
}
