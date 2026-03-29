"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { sendSignInLinkToEmail } from "firebase/auth";
import { useAuth } from "@/lib/auth";
import { getAuthInstance } from "@/lib/firebase";
import { AuthGuard } from "@/components/AuthGuard";
import { AppNav } from "@/components/AppNav";
import { LoadingState } from "@/components/LoadingState";
import type { Partner } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_MCP_API_URL || "https://zenos-mcp-165893875709.asia-east1.run.app";

function TeamPage() {
  const { user, partner } = useAuth();
  const router = useRouter();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Admin guard: redirect non-admin users
  useEffect(() => {
    if (partner && !partner.isAdmin) {
      router.replace("/");
    }
  }, [partner, router]);

  const fetchPartners = useCallback(async () => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/partners`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }
      const body = await res.json();
      const data = Array.isArray(body.partners) ? body.partners : [];
      setPartners(data as Partner[]);
    } catch (err) {
      console.error("Failed to fetch partners:", err);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (partner?.isAdmin) {
      fetchPartners();
    }
  }, [partner, fetchPartners]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || !inviteEmail.trim()) return;

    setInviting(true);
    setInviteMessage(null);

    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/partners/invite`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: inviteEmail.trim() }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }

      // Send Firebase email link
      const actionCodeSettings = {
        url: `${window.location.origin}/login`,
        handleCodeInApp: true,
      };
      await sendSignInLinkToEmail(
        getAuthInstance(),
        inviteEmail.trim(),
        actionCodeSettings
      );

      setInviteMessage({ type: "success", text: `已發送邀請信至 ${inviteEmail.trim()}` });
      setInviteEmail("");
      await fetchPartners();
    } catch (err) {
      console.error("Invite failed:", err);
      setInviteMessage({
        type: "error",
        text: err instanceof Error ? err.message : "邀請失敗，請稍後再試",
      });
    } finally {
      setInviting(false);
    }
  };

  const handleResendInvite = async (targetPartner: Partner) => {
    if (!user) return;
    setActionLoading(targetPartner.id);
    setInviteMessage(null);
    try {
      const actionCodeSettings = {
        url: `${window.location.origin}/login`,
        handleCodeInApp: true,
      };
      await sendSignInLinkToEmail(
        getAuthInstance(),
        targetPartner.email,
        actionCodeSettings
      );
      setInviteMessage({ type: "success", text: `已重新寄送邀請信至 ${targetPartner.email}` });
    } catch (err) {
      console.error("Resend invite failed:", err);
      setInviteMessage({
        type: "error",
        text: err instanceof Error ? err.message : "重新寄送失敗，請稍後再試",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteInvite = async (targetPartner: Partner) => {
    if (!user) return;
    if (!window.confirm(`確定要刪除 ${targetPartner.email} 的邀請嗎？`)) return;
    setActionLoading(targetPartner.id);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/partners/${targetPartner.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }
      await fetchPartners();
    } catch (err) {
      console.error("Delete invite failed:", err);
      setInviteMessage({
        type: "error",
        text: err instanceof Error ? err.message : "刪除邀請失敗，請稍後再試",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRoleChange = async (targetPartner: Partner, isAdmin: boolean) => {
    if (!user) return;
    setActionLoading(targetPartner.id);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/partners/${targetPartner.id}/role`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ isAdmin }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }
      await fetchPartners();
    } catch (err) {
      console.error("Role change failed:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStatusChange = async (
    targetPartner: Partner,
    status: "active" | "suspended"
  ) => {
    if (!user) return;
    setActionLoading(targetPartner.id);
    try {
      const token = await user.getIdToken();
      const res = await fetch(
        `${API_URL}/api/partners/${targetPartner.id}/status`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ status }),
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({ message: "Unknown error" }));
        throw new Error(body.message || body.detail || `Failed: ${res.status}`);
      }
      await fetchPartners();
    } catch (err) {
      console.error("Status change failed:", err);
    } finally {
      setActionLoading(null);
    }
  };

  if (!partner?.isAdmin) return null;

  const activeCount = partners.filter((p) => p.status === "active").length;
  const invitedCount = partners.filter((p) => p.status === "invited").length;

  return (
    <div className="min-h-screen">
      <AppNav />

      <main id="main-content" className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-white">Team</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {partners.length} members &middot; {activeCount} active
              {invitedCount > 0 && ` \u00B7 ${invitedCount} invited`}
            </p>
          </div>
        </div>

        {/* Invite Form */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <h3 className="text-sm font-medium text-white mb-4">Invite new member</h3>
          <form onSubmit={handleInvite} className="flex items-center gap-3">
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="email@example.com"
              aria-label="Invite member email"
              required
              className="flex-1 bg-background border border-border rounded-lg px-4 py-2 text-sm text-white placeholder-muted-foreground focus:outline-none focus:border-ring transition-colors"
            />
            <button
              type="submit"
              aria-label="Send invite"
              disabled={inviting || !inviteEmail.trim()}
              className="bg-primary hover:bg-primary/80 text-primary-foreground text-sm font-medium px-4 py-2 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {inviting ? "Sending..." : "Invite"}
            </button>
          </form>
          {inviteMessage && (
            <p
              className={`text-sm mt-3 ${
                inviteMessage.type === "success" ? "text-green-400" : "text-red-400"
              }`}
            >
              {inviteMessage.text}
            </p>
          )}
        </div>

        {/* Partner List */}
        {loading ? (
          <LoadingState label="Loading team members..." />
        ) : partners.length === 0 ? (
          <div className="text-center py-12 bg-card rounded-lg border border-border">
            <p className="text-muted-foreground">No team members yet.</p>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    Email
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    Name
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    Role
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    Status
                  </th>
                  <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-6 py-3">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {partners.map((p) => {
                  const isSelf = p.id === partner.id;
                  const isLoading = actionLoading === p.id;
                  return (
                    <tr
                      key={p.id}
                      className={`border-b border-border last:border-b-0 ${
                        p.status === "invited" ? "opacity-60" : ""
                      }`}
                    >
                      <td className="px-6 py-4 text-sm text-white">{p.email}</td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {p.displayName || "--"}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            p.isAdmin
                              ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                              : "bg-secondary text-muted-foreground border border-border"
                          }`}
                        >
                          {p.isAdmin ? "Admin" : "Member"}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={p.status} />
                      </td>
                      <td className="px-6 py-4 text-right">
                        {isSelf ? (
                          <span className="text-xs text-muted-foreground">You</span>
                        ) : (
                          <div className="flex items-center justify-end gap-2">
                            {p.status !== "invited" && (
                              <button
                                onClick={() => handleRoleChange(p, !p.isAdmin)}
                                aria-label={p.isAdmin ? `Set ${p.email} as member` : `Set ${p.email} as admin`}
                                disabled={isLoading}
                                className="text-xs text-muted-foreground hover:text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {p.isAdmin ? "Set Member" : "Set Admin"}
                              </button>
                            )}
                            {p.status === "active" && (
                              <button
                                onClick={() => handleStatusChange(p, "suspended")}
                                aria-label={`Suspend ${p.email}`}
                                disabled={isLoading}
                                className="text-xs text-red-400 hover:text-red-300 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Suspend
                              </button>
                            )}
                            {p.status === "suspended" && (
                              <button
                                onClick={() => handleStatusChange(p, "active")}
                                aria-label={`Activate ${p.email}`}
                                disabled={isLoading}
                                className="text-xs text-green-400 hover:text-green-300 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                Reactivate
                              </button>
                            )}
                            {p.status === "invited" && (
                              <>
                                <button
                                  onClick={() => handleResendInvite(p)}
                                  aria-label={`Resend invite to ${p.email}`}
                                  disabled={isLoading}
                                  className="text-xs text-muted-foreground hover:text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  Resend
                                </button>
                                <button
                                  onClick={() => handleDeleteInvite(p)}
                                  aria-label={`Delete invite for ${p.email}`}
                                  disabled={isLoading}
                                  className="text-xs text-red-400 hover:text-red-300 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  Delete
                                </button>
                              </>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: Partner["status"] }) {
  const styles = {
    active: "bg-green-500/10 text-green-400 border-green-500/20",
    invited: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    suspended: "bg-red-500/10 text-red-400 border-red-500/20",
  };

  const labels = {
    active: "Active",
    invited: "Invited",
    suspended: "Suspended",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <TeamPage />
    </AuthGuard>
  );
}
