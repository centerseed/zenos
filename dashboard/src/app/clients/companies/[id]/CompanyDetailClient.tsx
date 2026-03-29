"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import {
  getCompany,
  updateCompany,
  getCompanyContacts,
  getCompanyDeals,
  createContact,
} from "@/lib/crm-api";
import type { Company, Contact, Deal } from "@/lib/crm-api";

// ─── New Contact Form ─────────────────────────────────────────────────────────

interface NewContactFormProps {
  companyId: string;
  token: string;
  onCreated: (contact: Contact) => void;
  onCancel: () => void;
}

function NewContactForm({ companyId, token, onCreated, onCancel }: NewContactFormProps) {
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const contact = await createContact(token, {
        companyId,
        name: name.trim(),
        title: title.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onCreated(contact);
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立失敗");
    }
    setSaving(false);
  }

  return (
    <form onSubmit={handleSubmit} className="bg-secondary/20 border border-border rounded-lg p-4 mt-3 space-y-3">
      <h4 className="text-sm font-medium text-foreground">新增聯絡人</h4>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">
            姓名 <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="王小明"
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            required
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">職稱</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="IT 主管"
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="wang@example.com"
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">電話</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="0912-345-678"
            className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-muted-foreground mb-1">備忘</label>
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="備注..."
          className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors"
        >
          取消
        </button>
        <button
          type="submit"
          disabled={saving || !name.trim()}
          className="px-3 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving ? "建立中..." : "新增"}
        </button>
      </div>
    </form>
  );
}

// ─── Editable Info Section ────────────────────────────────────────────────────

interface EditableInfoProps {
  company: Company;
  token: string;
  onUpdated: (company: Company) => void;
}

function EditableInfo({ company, token, onUpdated }: EditableInfoProps) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(company.name);
  const [industry, setIndustry] = useState(company.industry ?? "");
  const [sizeRange, setSizeRange] = useState(company.sizeRange ?? "");
  const [region, setRegion] = useState(company.region ?? "");
  const [notes, setNotes] = useState(company.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateCompany(token, company.id, {
        name: name.trim(),
        industry: industry.trim() || undefined,
        sizeRange: sizeRange.trim() || undefined,
        region: region.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onUpdated(updated);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "儲存失敗");
    }
    setSaving(false);
  }

  if (!editing) {
    return (
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-base font-semibold text-foreground">{company.name}</h3>
          <button
            onClick={() => setEditing(true)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            編輯
          </button>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">產業</dt>
            <dd className="text-foreground">{company.industry ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">規模</dt>
            <dd className="text-foreground">{company.sizeRange ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">地區</dt>
            <dd className="text-foreground">{company.region ?? "—"}</dd>
          </div>
        </dl>
        {company.notes && (
          <p className="mt-3 text-sm text-muted-foreground border-t border-border pt-3">
            {company.notes}
          </p>
        )}
        {company.zenosEntityId && (
          <div className="mt-3 border-t border-border pt-3">
            <Link
              href={`/knowledge-map?focus=${company.zenosEntityId}`}
              className="text-xs text-primary hover:underline"
            >
              在知識地圖查看 →
            </Link>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl p-5 space-y-3">
      <h3 className="text-sm font-semibold text-foreground">編輯公司資訊</h3>
      <div>
        <label className="block text-xs text-muted-foreground mb-1">
          公司名稱 <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">產業</label>
          <input
            type="text"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">規模</label>
          <input
            type="text"
            value={sizeRange}
            onChange={(e) => setSizeRange(e.target.value)}
            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-muted-foreground mb-1">地區</label>
        <input
          type="text"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>
      <div>
        <label className="block text-xs text-muted-foreground mb-1">備忘</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex justify-end gap-2">
        <button
          onClick={() => setEditing(false)}
          className="px-3 py-1.5 text-sm rounded-lg bg-secondary text-foreground hover:bg-secondary/80 transition-colors"
        >
          取消
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving ? "儲存中..." : "儲存"}
        </button>
      </div>
    </div>
  );
}

// ─── CompanyDetailPage ────────────────────────────────────────────────────────

function CompanyDetailPage() {
  const { user, partner } = useAuth();
  const params = useParams();
  const companyId = params.id as string;

  const [company, setCompany] = useState<Company | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState("");
  const [showContactForm, setShowContactForm] = useState(false);

  useEffect(() => {
    if (!user || !partner) return;

    async function load() {
      const t = await user!.getIdToken();
      setToken(t);
      try {
        const [fetchedCompany, fetchedContacts, fetchedDeals] = await Promise.all([
          getCompany(t, companyId),
          getCompanyContacts(t, companyId),
          getCompanyDeals(t, companyId),
        ]);
        setCompany(fetchedCompany);
        setContacts(fetchedContacts);
        setDeals(fetchedDeals);
      } catch (err) {
        console.error("Failed to load company:", err);
      }
      setLoading(false);
    }

    load();
  }, [user, partner, companyId]);

  if (loading) {
    return (
      <div className="min-h-screen">
        <AppNav />
        <div className="flex-1 flex items-center justify-center py-20">
          <LoadingState label="載入公司資料..." />
        </div>
      </div>
    );
  }

  if (!company) {
    return (
      <div className="min-h-screen">
        <AppNav />
        <main className="max-w-3xl mx-auto px-4 py-6">
          <p className="text-muted-foreground">找不到該公司</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <AppNav />
      <main id="main-content" className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/clients" className="hover:text-foreground transition-colors">
            客戶
          </Link>
          <span>/</span>
          <Link href="/clients/companies" className="hover:text-foreground transition-colors">
            公司列表
          </Link>
          <span>/</span>
          <span className="text-foreground">{company.name}</span>
        </div>

        {/* Editable company info */}
        <EditableInfo
          company={company}
          token={token}
          onUpdated={setCompany}
        />

        {/* Contacts */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-foreground">
              聯絡人 ({contacts.length})
            </h3>
            <button
              onClick={() => setShowContactForm((v) => !v)}
              className="text-xs text-primary hover:underline"
            >
              {showContactForm ? "取消" : "+ 新增聯絡人"}
            </button>
          </div>

          {showContactForm && (
            <NewContactForm
              companyId={companyId}
              token={token}
              onCreated={(c) => {
                setContacts((prev) => [c, ...prev]);
                setShowContactForm(false);
              }}
              onCancel={() => setShowContactForm(false)}
            />
          )}

          {contacts.length === 0 && !showContactForm ? (
            <p className="text-sm text-muted-foreground py-4">尚無聯絡人</p>
          ) : (
            <div className="space-y-2 mt-2">
              {contacts.map((contact) => (
                <div
                  key={contact.id}
                  className="bg-card border border-border rounded-lg px-4 py-3 flex items-center justify-between"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{contact.name}</p>
                    {contact.title && (
                      <p className="text-xs text-muted-foreground">{contact.title}</p>
                    )}
                  </div>
                  <div className="text-right text-xs text-muted-foreground space-y-0.5">
                    {contact.email && <p>{contact.email}</p>}
                    {contact.phone && <p>{contact.phone}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Deals */}
        <section>
          <h3 className="text-sm font-semibold text-foreground mb-3">
            商機 ({deals.length})
          </h3>
          {deals.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">尚無商機</p>
          ) : (
            <div className="space-y-2">
              {deals.map((deal) => (
                <Link
                  key={deal.id}
                  href={`/clients/deals/${deal.id}`}
                  className="block bg-card border border-border rounded-lg px-4 py-3 hover:bg-secondary/30 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">{deal.title}</p>
                    <span className="text-xs bg-secondary text-muted-foreground rounded-full px-2 py-0.5">
                      {deal.funnelStage}
                    </span>
                  </div>
                  {deal.amountTwd && (
                    <p className="text-xs text-muted-foreground mt-1">
                      NT$ {deal.amountTwd.toLocaleString()}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default function CompanyDetailClient() {
  return (
    <AuthGuard>
      <CompanyDetailPage />
    </AuthGuard>
  );
}
