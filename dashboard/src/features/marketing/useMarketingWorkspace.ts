import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import type {
  MarketingProject,
  MarketingProjectGroup,
  MarketingStyle,
  MarketingStyleBuckets,
  WeekPlan,
} from "@/lib/marketing-api";
import {
  createMarketingProject,
  createMarketingStyle,
  createMarketingTopic,
  getMarketingProjectDetail,
  getMarketingProjectGroups,
  getMarketingProjectStyles,
  reviewMarketingPost,
  updateMarketingProjectContentPlan,
  updateMarketingProjectStrategy,
  updateMarketingStyle,
} from "@/lib/marketing-api";
import type { FieldDiscussionConfig, PromptDraftDiscussionConfig } from "@/features/marketing/logic";

type Campaign = MarketingProject;
type CampaignGroup = MarketingProjectGroup;

export function useMarketingWorkspace() {
  const { user } = useAuth();
  const [campaignGroups, setCampaignGroups] = useState<CampaignGroup[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [projectStyles, setProjectStyles] = useState<MarketingStyleBuckets>({ product: [], platform: [], project: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewingPostId, setReviewingPostId] = useState<string | null>(null);
  const [creatingTopic, setCreatingTopic] = useState(false);
  const [creatingCampaign, setCreatingCampaign] = useState(false);
  const [savingStrategy, setSavingStrategy] = useState(false);
  const [savingPlan, setSavingPlan] = useState(false);
  const [savingStyle, setSavingStyle] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [activeFieldContext, setActiveFieldContext] = useState<FieldDiscussionConfig | undefined>();
  const [activePromptContext, setActivePromptContext] = useState<PromptDraftDiscussionConfig | undefined>();

  const loadCampaigns = useCallback(async () => {
    if (!user) return;
    setError(null);
    const token = await user.getIdToken();
    const data = await getMarketingProjectGroups(token);
    setCampaignGroups(data);
  }, [user]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    loadCampaigns()
      .catch((err) => setError(err instanceof Error ? err.message : "載入失敗"))
      .finally(() => setLoading(false));
  }, [user, loadCampaigns]);

  useEffect(() => {
    if (!user || !selectedId) {
      setSelectedCampaign(null);
      setProjectStyles({ product: [], platform: [], project: [] });
      setCopilotOpen(false);
      setActiveFieldContext(undefined);
      setActivePromptContext(undefined);
      return;
    }

    let alive = true;
    user
      .getIdToken()
      .then(async (token) => {
        const [detail, styles] = await Promise.all([
          getMarketingProjectDetail(token, selectedId),
          getMarketingProjectStyles(token, selectedId),
        ]);
        return { detail, styles };
      })
      .then(({ detail, styles }) => {
        if (!alive) return;
        setSelectedCampaign(detail);
        setProjectStyles(styles);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "載入活動失敗");
      });

    return () => {
      alive = false;
    };
  }, [user, selectedId]);

  const campaigns = useMemo(() => campaignGroups.flatMap((group) => group.projects), [campaignGroups]);
  const selectedFromList = useMemo(
    () => campaigns.find((campaign) => campaign.id === selectedId) || null,
    [campaigns, selectedId]
  );

  const handleReview = useCallback(
    async (postId: string, action: "approve" | "request_changes" | "reject") => {
      if (!user || !selectedId) return;
      const comment =
        action === "approve"
          ? ""
          : window.prompt(action === "request_changes" ? "請輸入修改意見" : "請輸入退回原因", "") || "";
      setReviewingPostId(postId);
      try {
        const token = await user.getIdToken();
        await reviewMarketingPost(token, postId, { action, comment });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, selectedId),
        ]);
        setCampaignGroups(list);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "審核失敗");
      } finally {
        setReviewingPostId(null);
      }
    },
    [user, selectedId]
  );

  const handleCreateTopic = useCallback(
    async ({ topic, platform, brief }: { topic: string; platform: string; brief: string }) => {
      if (!user || !selectedId) return;
      setCreatingTopic(true);
      try {
        const token = await user.getIdToken();
        await createMarketingTopic(token, selectedId, { topic, platform, brief });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, selectedId),
        ]);
        setCampaignGroups(list);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "建立主題失敗");
      } finally {
        setCreatingTopic(false);
      }
    },
    [user, selectedId]
  );

  const handleCreateCampaign = useCallback(
    async ({
      productId,
      name,
      description,
      projectType,
      dateRange,
    }: {
      productId: string;
      name: string;
      description: string;
      projectType: "long_term" | "short_term";
      dateRange?: { start: string; end: string } | null;
    }) => {
      if (!user) return;
      setCreatingCampaign(true);
      setError(null);
      try {
        const token = await user.getIdToken();
        const created = await createMarketingProject(token, {
          productId,
          name,
          description,
          projectType,
          dateRange,
        });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, created.id),
        ]);
        setCampaignGroups(list);
        setSelectedId(created.id);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "建立活動失敗");
      } finally {
        setCreatingCampaign(false);
      }
    },
    [user]
  );

  const handleSaveStrategy = useCallback(
    async (input: {
      audience: string[];
      tone: string;
      coreMessage: string;
      platforms: string[];
      frequency?: string;
      contentMix?: Record<string, number>;
      campaignGoal?: string;
      ctaStrategy?: string;
      referenceMaterials?: string[];
    }) => {
      if (!user || !selectedId) return;
      setSavingStrategy(true);
      setError(null);
      try {
        const token = await user.getIdToken();
        await updateMarketingProjectStrategy(token, selectedId, {
          ...input,
          expectedUpdatedAt: selectedCampaign?.strategy?.updatedAt,
        });
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, selectedId),
        ]);
        setCampaignGroups(list);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "儲存策略失敗");
      } finally {
        setSavingStrategy(false);
      }
    },
    [user, selectedId, selectedCampaign?.strategy?.updatedAt]
  );

  const handleSaveContentPlan = useCallback(
    async (contentPlan: WeekPlan[]) => {
      if (!user || !selectedId) return;
      setSavingPlan(true);
      setError(null);
      try {
        const token = await user.getIdToken();
        await updateMarketingProjectContentPlan(token, selectedId, contentPlan);
        const [list, detail] = await Promise.all([
          getMarketingProjectGroups(token),
          getMarketingProjectDetail(token, selectedId),
        ]);
        setCampaignGroups(list);
        setSelectedCampaign(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "儲存排程失敗");
      } finally {
        setSavingPlan(false);
      }
    },
    [user, selectedId]
  );

  const handleSaveStyle = useCallback(
    async (input: { id?: string; title: string; level: MarketingStyle["level"]; content: string; platform?: string }) => {
      if (!user || !selectedCampaign) return;
      setSavingStyle(true);
      setError(null);
      try {
        const token = await user.getIdToken();
        if (input.id) {
          await updateMarketingStyle(token, input.id, { title: input.title, content: input.content });
        } else {
          await createMarketingStyle(token, {
            title: input.title,
            level: input.level,
            content: input.content,
            productId: input.level === "project" ? undefined : selectedCampaign.productId || undefined,
            projectId: input.level === "project" ? selectedCampaign.id : undefined,
            platform: input.level === "platform" ? input.platform : undefined,
          });
        }
        const styles = await getMarketingProjectStyles(token, selectedCampaign.id);
        setProjectStyles(styles);
      } catch (err) {
        setError(err instanceof Error ? err.message : "儲存文風失敗");
      } finally {
        setSavingStyle(false);
      }
    },
    [user, selectedCampaign]
  );

  const handleOpenFieldCopilot = useCallback((config: FieldDiscussionConfig) => {
    setActivePromptContext(undefined);
    setActiveFieldContext(config);
    setCopilotOpen(true);
  }, []);

  const handleOpenPromptCopilot = useCallback((config: PromptDraftDiscussionConfig) => {
    setActiveFieldContext(undefined);
    setActivePromptContext(config);
    setCopilotOpen(true);
  }, []);

  const handleOpenGeneralCopilot = useCallback(() => {
    setActiveFieldContext(undefined);
    setActivePromptContext(undefined);
    setCopilotOpen(true);
  }, []);

  const productOptions = useMemo(() => {
    const seen = new Set<string>();
    return campaignGroups
      .map((group) => group.product)
      .filter((product) => {
        const key = product.id || product.name;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }, [campaignGroups]);

  return {
    activeFieldContext,
    activePromptContext,
    campaignGroups,
    copilotOpen,
    creatingCampaign,
    creatingTopic,
    error,
    handleCreateCampaign,
    handleCreateTopic,
    handleOpenFieldCopilot,
    handleOpenGeneralCopilot,
    handleOpenPromptCopilot,
    handleReview,
    handleSaveContentPlan,
    handleSaveStrategy,
    handleSaveStyle,
    loading,
    productOptions,
    projectStyles,
    reviewingPostId,
    savingPlan,
    savingStrategy,
    savingStyle,
    selectedCampaign,
    selectedFromList,
    selectedId,
    setCopilotOpen,
    setError,
    setSelectedId,
    user,
  };
}
