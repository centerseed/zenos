"""MCP tool: analyze — governance health checks."""

from __future__ import annotations

import logging

from zenos.domain.governance import (
    compute_search_unused_signals,
    detect_invalid_document_titles,
    score_summary_quality,
)

from zenos.interface.mcp._common import _serialize, _unified_response, _error_response

logger = logging.getLogger(__name__)


async def analyze(
    check_type: str = "all",
    entity_id: str | None = None,
) -> dict:
    """執行 ontology 治理健康檢查。

    分析整個知識庫的品質、新鮮度和潛在盲點。
    結果可用來發現問題、建立改善任務。

    使用時機：
    - 定期健檢 → analyze(check_type="all")
    - 輕量 KPI 快照 → analyze(check_type="health")
    - 只看品質分數 → analyze(check_type="quality")
    - 找過時內容 → analyze(check_type="staleness")
    - 推斷盲點 → analyze(check_type="blindspot")
    - 只看 impacts 斷鏈 → analyze(check_type="impacts")
    - 只看文件一致性 → analyze(check_type="document_consistency")
    - 分析能見度風險 → analyze(check_type="permission_risk")
    - 找無效文件條目 → analyze(check_type="invalid_documents")
    - 清理孤立關聯 → analyze(check_type="orphaned_relationships")
    - 檢查 server 端 LLM 依賴與 provider 健康 → analyze(check_type="llm_health")
    不要用這個工具的情境：
    - 搜尋或列出條目 → 用 search
    - 更新 ontology 內容 → 用 write

    Args:
        check_type: "all" / "health" / "quality" / "staleness" / "blindspot" / "impacts" /
                    "document_consistency" / "permission_risk" / "invalid_documents" /
                    "orphaned_relationships" / "llm_health"

    Returns:
        dict — 各 check_type 對應的子結構：
        - quality: {score, total_entities, issues[{entity_id, entity_name, defect}], ...}
                   含 L2 治理補充欄位（l2_impacts_repairs, l2_backfill_proposals, 等）
        - staleness: {warnings[{...}], count, document_consistency_warnings, document_consistency_count}
        - blindspots: {blindspots[{...}], count, task_signal_suggestions[{...}], task_signal_count}
        - permission_risk: {isolation_score, overexposure_score, warnings[{...}], summary}
        - impacts: quality.l2_impacts_validity（掛在 quality 子結構下）
        - document_consistency: {document_consistency_warnings[{...}], document_consistency_count}
        - invalid_documents: {items[{entity_id, current_title, source_uri, linked_entity_ids,
                             proposed_title, action}], count}
        - llm_health: {provider_status[{...}], dependency_points[{...}], findings[{...}], overall_level}
        - kpis: {total_items, unconfirmed_items, unconfirmed_ratio, blindspot_total,
                 duplicate_blindspots, duplicate_blindspot_rate, median_confirm_latency_days,
                 active_l2_missing_impacts, weekly_review_required}（check_type="all" 時包含）
    """
    from zenos.interface.mcp import _ensure_services, _ensure_governance_ai
    import zenos.interface.mcp as _mcp
    from zenos.infrastructure.context import current_partner_id as _current_partner_id
    from zenos.infrastructure.sql_common import get_pool, upsert_health_cache

    await _ensure_services()
    results: dict = {}
    l2_repairs: list[dict] = []

    def _is_concrete_impacts_description(description: str) -> bool:
        desc = (description or "").strip()
        if not desc:
            return False
        if "→" in desc:
            left, right = desc.split("→", 1)
            return bool(left.strip()) and bool(right.strip())
        if "->" in desc:
            left, right = desc.split("->", 1)
            return bool(left.strip()) and bool(right.strip())
        return False

    async def _infer_l2_repairs() -> list[dict]:
        all_entities = await _mcp.ontology_service._entities.list_all()
        active_modules = [
            e for e in all_entities
            if e.type == "module" and e.status == "active" and e.id
        ]
        draft_modules = [
            e for e in all_entities
            if e.type == "module" and e.status == "draft" and e.id
        ]
        if not active_modules and not draft_modules:
            return []

        impact_entity_ids: set[str] = set()
        seen_rel_ids: set[str | None] = set()
        for ent in all_entities:
            if not ent.id:
                continue
            rels = await _mcp.ontology_service._relationships.list_by_entity(ent.id)
            for rel in rels:
                if rel.id in seen_rel_ids:
                    continue
                seen_rel_ids.add(rel.id)
                if rel.type != "impacts":
                    continue
                if not _is_concrete_impacts_description(rel.description):
                    continue
                impact_entity_ids.add(rel.source_entity_id)
                impact_entity_ids.add(rel.target_id)

        repairs = []
        for mod in active_modules:
            if mod.id in impact_entity_ids:
                continue
            repairs.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "severity": "red",
                "defect": "active_l2_missing_concrete_impacts",
                "repair_options": [
                    "補 impacts（A 改了什麼→B 的什麼要跟著看）",
                    "降級為 L3",
                    "重新切粒度",
                ],
            })
        for mod in draft_modules:
            override = (
                mod.details.get("manual_override_reason")
                if mod.details and isinstance(mod.details, dict)
                else None
            )
            repairs.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "severity": "yellow",
                "defect": "draft_l2_pending_confirmation",
                "manual_override_reason": override,
                "repair_options": [
                    "補 impacts 後 confirm",
                    "降級為 L3",
                ],
            })
        return repairs

    async def _list_saturated_entities() -> list[dict]:
        """Fast listing of (entity, department) saturation groups (>= 20 active).

        Diagnose-only: no LLM call. Use _consolidate_one(entity_id) to run
        the actual LLM proposal for a single entity (DF-20260419-L2c).
        """
        _erepo = _mcp.entry_repo
        if _erepo is None:
            return []
        saturated = await _erepo.list_saturated_entities(threshold=20)
        return [
            {
                "entity_id": item["entity_id"],
                "entity_name": item["entity_name"],
                "active_count": item["active_count"],
                **({"department": item["department"]} if item.get("department") is not None else {}),
            }
            for item in saturated
        ]

    async def _consolidate_one(target_entity_id: str) -> dict | None:
        """Run LLM consolidation proposal for a single (entity, department) group.

        Returns {entity_id, entity_name, active_count, department, consolidation_proposal}
        or None if the entity isn't saturated / no LLM available.
        """
        _erepo = _mcp.entry_repo
        _gai = _mcp._governance_ai
        if _erepo is None or _gai is None:
            return None
        saturated = await _erepo.list_saturated_entities(threshold=20)
        match = next((s for s in saturated if s["entity_id"] == target_entity_id), None)
        if match is None:
            return None
        dept = match.get("department")
        all_entries = await _erepo.list_by_entity(target_entity_id, status="active")
        entries = [e for e in all_entries if e.department == dept]
        entry_dicts = [
            {"id": e.id, "type": e.type, "content": e.content}
            for e in entries
        ]
        proposal = _gai.consolidate_entries(target_entity_id, match["entity_name"], entry_dicts)
        result: dict = {
            "entity_id": target_entity_id,
            "entity_name": match["entity_name"],
            "active_count": match["active_count"],
            "consolidation_proposal": proposal.model_dump() if proposal else None,
        }
        if dept is not None:
            result["department"] = dept
        return result

    # DF-20260419-L2c: single-entity consolidation proposal. Separated
    # diagnosis (check_type="quality" lists saturated entities, no LLM) from
    # execution (check_type="consolidate" runs one LLM call for one entity).
    # Previously analyze(quality) did both synchronously in a loop, timing
    # out on any entity with 40+ entries.
    if check_type == "consolidate":
        if not entity_id:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="analyze(check_type='consolidate') 需要 entity_id（先用 quality 列 saturated 再 targeted call）",
            )
        proposal = await _consolidate_one(entity_id)
        if proposal is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=(
                    f"Entity '{entity_id}' 不在 saturation 清單（active entries < 20），"
                    "或 LLM 不可用。先跑 analyze(check_type='quality') 確認是否真的 saturated。"
                ),
            )
        return _unified_response(data=proposal)

    # DF-20260419-L2b: single-entity health audit.
    # Replaces Monitor's manual gather (get entity + list rels + list entries +
    # walk peer parents) with one server-side call. Returns six dimensions
    # per PLAN-zenos-dogfooding-loop L2 rules, plus rule-based anti-pattern
    # hits so governance audit can act without pulling the full corpus.
    if check_type == "entity_health":
        import re as _re

        if not entity_id:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="analyze(check_type='entity_health') 需要 entity_id",
            )
        entity = await _mcp.entity_repo.get_by_id(entity_id)
        if entity is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=f"Entity '{entity_id}' not found",
            )

        partner_dept = "all"
        try:
            from zenos.infrastructure.context import current_partner_department as _cpd
            partner_dept = str(_cpd.get() or "all")
        except Exception:
            pass

        # Dim 1 — summary
        summary_text = entity.summary or ""
        summary_dim = {
            "present": bool(summary_text),
            "length": len(summary_text),
            "over_limit": len(summary_text) > 300,
        }

        # Dim 2 — tags 4-dim
        tags = entity.tags
        missing = []
        if tags:
            if not (tags.what and (tags.what if isinstance(tags.what, list) else [tags.what])):
                missing.append("what")
            if not tags.why:
                missing.append("why")
            if not tags.how:
                missing.append("how")
            if not (tags.who and (tags.who if isinstance(tags.who, list) else [tags.who])):
                missing.append("who")
        else:
            missing = ["what", "why", "how", "who"]
        tags_dim = {"complete": not missing, "missing_dimensions": missing}

        # Dim 3 — relationships
        rels = await _mcp.relationship_repo.list_by_entity(entity_id)
        out_count = sum(1 for r in rels if r.source_entity_id == entity_id)
        in_count = sum(1 for r in rels if r.source_entity_id != entity_id)
        out_confirmed = sum(1 for r in rels if r.source_entity_id == entity_id and r.confirmed_by_user)
        in_confirmed = sum(1 for r in rels if r.source_entity_id != entity_id and r.confirmed_by_user)
        total_confirmed = out_confirmed + in_confirmed

        # Cross-subtree check: walk peers' L1 roots
        all_ents = await _mcp.entity_repo.list_all()
        emap = {e.id: e for e in all_ents if e.id}
        from zenos.application.knowledge.ontology_service import _find_product_root
        self_l1 = _find_product_root(entity_id, emap) if entity_id else None
        cross_subtree = 0
        for r in rels:
            peer_id = r.target_id if r.source_entity_id == entity_id else r.source_entity_id
            peer_l1 = _find_product_root(peer_id, emap) if peer_id else None
            if self_l1 and peer_l1 and peer_l1 != self_l1:
                cross_subtree += 1
        rels_dim = {
            "outgoing": out_count,
            "incoming": in_count,
            "outgoing_confirmed": out_confirmed,
            "incoming_confirmed": in_confirmed,
            "total_confirmed": total_confirmed,
            "orphan": total_confirmed < 2,
            "cross_subtree_count": cross_subtree,
        }

        # Dim 4 — entries saturation & anti-pattern scan
        entries = await _mcp.entry_repo.list_by_entity(entity_id, status="active", department=partner_dept)
        active_count = len(entries)
        saturation_level = "red" if active_count >= 20 else ("yellow" if active_count >= 15 else "green")

        # Rule-based anti-pattern detection (regex, no LLM)
        _commit_re = _re.compile(r"\bcommit\s+[0-9a-f]{7,40}\b", _re.IGNORECASE)
        _sha_re = _re.compile(r"\b[0-9a-f]{7,40}\b")
        _file_line_re = _re.compile(r"\w+\.py[:\s]+L?\d+|:\s*\d{2,4}\b")
        _call_arrow_re = _re.compile(r"→.+→|->.+->")
        _func_dunder_re = _re.compile(r"\b_\w+\(\)")

        def _classify_anti_pattern(text: str) -> list[str]:
            hits = []
            if _commit_re.search(text):
                hits.append("#5_commit_sha")
            elif _sha_re.search(text) and "commit" in text.lower():
                hits.append("#5_commit_sha")
            if _file_line_re.search(text):
                hits.append("#1_code_path_trace")
            if _call_arrow_re.search(text):
                hits.append("#1_call_path")
            if _func_dunder_re.search(text):
                hits.append("#2_internal_func")
            return hits

        anti_pattern_hits = []
        for e in entries:
            text = (e.content or "") + " " + (e.context or "")
            hits = _classify_anti_pattern(text)
            if hits:
                anti_pattern_hits.append({
                    "entry_id": e.id,
                    "type": e.type,
                    "content_preview": (e.content or "")[:80],
                    "patterns": hits,
                })

        entries_dim = {
            "active_count": active_count,
            "threshold": 20,
            "saturation_level": saturation_level,
            "anti_pattern_candidates": anti_pattern_hits,
            "anti_pattern_count": len(anti_pattern_hits),
        }

        # Dim 5 — granularity signal (v1 proxy: entry count + type diversity)
        type_diversity = len({e.type for e in entries}) if entries else 0
        granularity_dim = {
            "active_entries": active_count,
            "type_diversity": type_diversity,
            "split_signal": active_count >= 30 or (active_count >= 20 and type_diversity >= 4),
            "split_reason": (
                "entries >= 30" if active_count >= 30
                else ("entries >= 20 + type diversity >= 4" if active_count >= 20 and type_diversity >= 4 else None)
            ),
        }

        # Verdict
        issues = []
        if not summary_dim["present"]: issues.append("summary_missing")
        if summary_dim["over_limit"]: issues.append("summary_over_300")
        if missing: issues.append("tags_incomplete")
        if rels_dim["orphan"]: issues.append("orphan_insufficient_confirmed_rels")
        if cross_subtree: issues.append("cross_subtree_rels")
        if saturation_level == "red": issues.append("entries_saturated")
        if anti_pattern_hits: issues.append("entries_anti_pattern")
        if granularity_dim["split_signal"]: issues.append("split_candidate")
        verdict = "healthy" if not issues else "needs_review"

        suggested_actions = []
        for h in anti_pattern_hits:
            suggested_actions.append({
                "action": "archive_entry",
                "entry_id": h["entry_id"],
                "reason": f"anti-pattern {','.join(h['patterns'])}",
            })
        if saturation_level == "red":
            suggested_actions.append({
                "action": "consolidate_entries",
                "reason": f"active_count {active_count} >= threshold 20",
            })
        if rels_dim["orphan"]:
            suggested_actions.append({
                "action": "review_relationships",
                "reason": f"only {total_confirmed} confirmed rels (need ≥2)",
            })
        if granularity_dim["split_signal"]:
            suggested_actions.append({
                "action": "consider_split",
                "reason": granularity_dim["split_reason"],
            })

        return _unified_response(data={
            "entity_id": entity_id,
            "name": entity.name,
            "type": entity.type,
            "level": entity.level,
            "dimensions": {
                "summary": summary_dim,
                "tags": tags_dim,
                "relationships": rels_dim,
                "entries": entries_dim,
                "granularity": granularity_dim,
            },
            "issues": issues,
            "verdict": verdict,
            "suggested_actions": suggested_actions,
        })

    # ADR-020: lightweight health check — KPIs only, no heavy analysis
    if check_type == "health":
        health_signal = await _mcp.governance_service.compute_health_signal()
        # ADR-021: persist to DB cache for Dashboard consumption
        try:
            pool = await get_pool()
            pid = _current_partner_id.get() or ""
            if pid and health_signal:
                await upsert_health_cache(pool, pid, health_signal.get("overall_level", "green"))
        except Exception:
            pass  # cache write is additive; never break the main operation
        return _unified_response(data=health_signal)

    if check_type in ("all", "llm_health"):
        from zenos.infrastructure.context import current_partner_id as _current_partner_id

        results["llm_health"] = await _mcp.governance_service.analyze_llm_health(
            _current_partner_id.get()
        )

    if check_type in ("all", "quality"):
        # Gather entry counts per entity for sparsity check
        _entries_by_entity: dict[str, int] | None = None
        if _mcp.entry_repo is not None:
            try:
                all_entities_for_sparsity = await _mcp.ontology_service._entities.list_all()
                active_module_ids = [
                    e.id for e in all_entities_for_sparsity
                    if e.type == "module" and e.status == "active" and e.id
                ]
                _entries_by_entity = {}
                for eid in active_module_ids:
                    try:
                        cnt = await _mcp.entry_repo.count_active_by_entity(eid)
                        _entries_by_entity[eid] = cnt
                    except Exception:
                        _entries_by_entity[eid] = 0
            except Exception:
                logger.warning("Entry sparsity data collection failed", exc_info=True)

        report = await _mcp.governance_service.run_quality_check(entries_by_entity=_entries_by_entity)
        results["quality"] = _serialize(report)
        try:
            l2_repairs = await _infer_l2_repairs()
            active_repairs = [r for r in l2_repairs if r.get("defect") == "active_l2_missing_concrete_impacts"]
            draft_repairs = [r for r in l2_repairs if r.get("defect") == "draft_l2_pending_confirmation"]
            results["quality"]["active_l2_missing_impacts"] = len(active_repairs)
            results["quality"]["draft_l2_pending_confirmation"] = len(draft_repairs)
            if l2_repairs:
                results["quality"]["l2_impacts_repairs"] = l2_repairs
        except Exception:
            # Repair suggestion is additive and should not break quality report.
            logger.warning("L2 repairs inference failed", exc_info=True)
        try:
            backfill = await _mcp.governance_service.infer_l2_backfill_proposals()
            results["quality"]["l2_backfill_proposals"] = backfill
            results["quality"]["l2_backfill_count"] = len(backfill)
        except Exception:
            logger.warning("L2 backfill proposals failed", exc_info=True)

        # L2 governance: impacts target validity
        try:
            validity_report = await _mcp.governance_service.check_impacts_target_validity()
            results["quality"]["l2_impacts_validity"] = validity_report
        except Exception:
            logger.warning("L2 impacts target validity check failed", exc_info=True)

        # P0-2: quality correction priority
        try:
            priority_report = await _mcp.governance_service.run_quality_correction_priority()
            results["quality"]["quality_correction_priority"] = priority_report
        except Exception:
            logger.warning("Quality correction priority failed", exc_info=True)

        # L2 governance: stale L2 downstream (entity part from domain; task part here)
        try:
            downstream_entities = await _mcp.governance_service.find_stale_l2_downstream_entities()
            # Enrich with open tasks at interface layer (task_repo available here)
            _open_statuses = {"todo", "in_progress", "review"}
            all_tasks = await _mcp.task_service.list_tasks(limit=500)
            for entry in downstream_entities:
                mod_id = entry["stale_module_id"]
                affected_tasks = [
                    {"id": t.id, "title": t.title, "status": t.status}
                    for t in all_tasks
                    if mod_id in (t.linked_entities or [])
                    and t.status in _open_statuses
                ]
                entry["affected_tasks"] = affected_tasks
                entry["suggested_actions"] = [
                    "重新掛載到 active L2",
                    "更新引用",
                    "降級為 sources",
                ]
            results["quality"]["l2_stale_downstream"] = downstream_entities
        except Exception:
            logger.warning("L2 stale downstream check failed", exc_info=True)

        # L2 governance: reverse impacts check
        try:
            reverse_impacts = await _mcp.governance_service.check_reverse_impacts()
            results["quality"]["l2_reverse_impacts"] = reverse_impacts
        except Exception:
            logger.warning("L2 reverse impacts check failed", exc_info=True)

        # L2 governance: review overdue check
        try:
            overdue = await _mcp.governance_service.check_governance_review_overdue()
            results["quality"]["l2_governance_review_overdue"] = overdue
            results["quality"]["l2_review_overdue_count"] = len(overdue)
        except Exception:
            logger.warning("L2 governance review overdue check failed", exc_info=True)

        # Entry saturation detection (DF-20260419-L2c: list-only, no per-entity
        # LLM consolidate — that was the timeout source. Use
        # analyze(check_type="consolidate", entity_id=X) to generate a proposal
        # for a specific entity.)
        try:
            entry_saturation = await _list_saturated_entities()
            results["quality"]["entry_saturation"] = entry_saturation
            results["quality"]["entry_saturation_count"] = len(entry_saturation)
        except Exception:
            logger.warning("Entry saturation check failed", exc_info=True)

        # Search-unused signals
        try:
            if _mcp._tool_event_repo is not None:
                partner_id = _current_partner_id.get() or ""
                all_entities_for_signals = await _mcp.ontology_service._entities.list_all()
                usage_stats = await _mcp._tool_event_repo.get_entity_usage_stats(partner_id, days=30)
                search_unused = compute_search_unused_signals(usage_stats, all_entities_for_signals)
                if search_unused:
                    results["quality"]["search_unused_signals"] = search_unused
        except Exception:
            logger.warning("Search unused signals check failed", exc_info=True)

        # Summary quality flags
        try:
            all_entities_for_quality = await _mcp.ontology_service._entities.list_all()
            l2_entities = [
                e for e in all_entities_for_quality
                if e.type == "module" and e.status in ("active", "draft") and e.id
            ]
            summary_flags = []
            for e in l2_entities:
                quality = score_summary_quality(e.summary or "", e.type)
                if quality["quality_score"] != "good":
                    summary_flags.append({
                        "entity_id": e.id,
                        "entity_name": e.name,
                        **quality,
                    })
            if summary_flags:
                results["quality"]["summary_quality_flags"] = summary_flags
        except Exception:
            logger.warning("Summary quality flags check failed", exc_info=True)

    if check_type in ("all", "staleness", "document_consistency"):
        staleness_result = await _mcp.governance_service.run_staleness_check()
        staleness_warnings = staleness_result["warnings"]
        doc_consistency_warnings = staleness_result["document_consistency_warnings"]
        if check_type != "document_consistency":
            results["staleness"] = {
                "warnings": [_serialize(w) for w in staleness_warnings],
                "count": len(staleness_warnings),
                "document_consistency_warnings": doc_consistency_warnings,
                "document_consistency_count": len(doc_consistency_warnings),
            }
        if check_type == "document_consistency":
            results["document_consistency"] = {
                "document_consistency_warnings": doc_consistency_warnings,
                "document_consistency_count": len(doc_consistency_warnings),
            }

    if check_type in ("all", "blindspot"):
        blindspots = await _mcp.governance_service.run_blindspot_analysis()
        results["blindspots"] = {
            "blindspots": [_serialize(b) for b in blindspots],
            "count": len(blindspots),
        }
        try:
            task_signal_suggestions = await _mcp.governance_service.infer_blindspots_from_tasks()
            results["blindspots"]["task_signal_suggestions"] = task_signal_suggestions
            results["blindspots"]["task_signal_count"] = len(task_signal_suggestions)
        except Exception:
            logger.warning("Task signal blindspot inference failed", exc_info=True)
            results["blindspots"]["task_signal_suggestions"] = []
            results["blindspots"]["task_signal_count"] = 0

    if check_type == "impacts":
        try:
            validity_report = await _mcp.governance_service.check_impacts_target_validity()
            results.setdefault("quality", {})["l2_impacts_validity"] = validity_report
        except Exception:
            logger.warning("Impacts target validity check failed (impacts check_type)", exc_info=True)

    if check_type in ("all", "permission_risk"):
        from zenos.application.identity.permission_risk_service import PermissionRiskService
        risk_svc = PermissionRiskService(
            entity_repo=_mcp.ontology_service._entities,
            task_repo=_mcp.task_service._tasks,
        )
        results["permission_risk"] = await risk_svc.analyze_risk()

    if check_type in ("all", "invalid_documents"):
        all_doc_entities = await _mcp.ontology_service._entities.list_all(type_filter="document")
        invalid_docs = detect_invalid_document_titles(all_doc_entities)
        # Task 40: enrich each item with proposed_title and action
        from zenos.domain.source_uri_validator import GITHUB_BLOB_PATTERN
        for doc in invalid_docs:
            source_uri = doc["source_uri"]
            if source_uri and GITHUB_BLOB_PATTERN.match(source_uri):
                try:
                    from zenos.infrastructure.github_adapter import parse_github_url
                    _, _, path, _ = parse_github_url(source_uri)
                    proposed_title = path.rsplit("/", 1)[-1]
                except Exception:
                    proposed_title = None
                doc["proposed_title"] = proposed_title
                doc["action"] = "propose_title"
            elif not source_uri or not source_uri.startswith("http"):
                doc["proposed_title"] = None
                doc["action"] = "auto_archive"
            else:
                doc["proposed_title"] = None
                doc["action"] = "manual_review"
        results["invalid_documents"] = {
            "items": invalid_docs,
            "count": len(invalid_docs),
        }

    if check_type in ("all", "orphaned_relationships"):
        try:
            orphan_result = await _mcp.ontology_service.remove_orphaned_relationships()
            results["orphaned_relationships"] = orphan_result
        except Exception:
            logger.warning("Orphaned relationships check failed", exc_info=True)

    if not results:
        return _error_response(
            status="rejected",
            error_code="INVALID_INPUT",
            message=(
                f"Unknown check_type '{check_type}'. "
                "Use: all, health, quality, staleness, blindspot, impacts, "
                "document_consistency, permission_risk, invalid_documents, "
                "orphaned_relationships, llm_health"
            ),
        )

    if check_type == "all":
        try:
            # ADR-020: delegate KPI computation to GovernanceService (single source of truth)
            health_signal = await _mcp.governance_service.compute_health_signal()
            kpi_data = health_signal.get("kpis", {})

            # Backward-compatible flat KPI format for existing consumers
            results["kpis"] = {
                "total_items": sum(
                    1 for _ in []  # placeholder — computed below
                ),
                "unconfirmed_items": 0,
                "unconfirmed_ratio": kpi_data.get("unconfirmed_ratio", {}).get("value", 0),
                "blindspot_total": kpi_data.get("blindspot_total", {}).get("value", 0),
                "duplicate_blindspots": 0,  # detail not tracked in health signal
                "duplicate_blindspot_rate": kpi_data.get("duplicate_blindspot_rate", {}).get("value", 0),
                "median_confirm_latency_days": kpi_data.get("median_confirm_latency_days", {}).get("value", 0),
                "active_l2_missing_impacts": kpi_data.get("active_l2_missing_impacts", {}).get("value", 0),
                "bundle_highlights_coverage": kpi_data.get("bundle_highlights_coverage", {}).get("value", 1.0),
                "weekly_review_required": (
                    kpi_data.get("quality_score", {}).get("value", 0) < 70
                    or kpi_data.get("active_l2_missing_impacts", {}).get("value", 0) > 0
                ),
            }
            # Enrich with health signal levels
            results["health_signal"] = health_signal
            if l2_repairs:
                results["governance_repairs"] = l2_repairs
        except Exception:
            # KPI should be additive; never break main governance checks.
            pass

    return _unified_response(data=results)
