from __future__ import annotations

from datetime import date

import pytest

from zenos.application.marketing_runtime import (
    adapt_platform_variants,
    build_intel_summary,
    build_postiz_payload,
    compose_style_layers,
    confirmed_topics_to_posts,
    generate_master_post,
    intel_writeback,
    load_postiz_credentials,
    plan_schedule,
    publish_with_postiz,
    run_with_retry,
)


class RetryableError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"status={status_code}")
        self.status_code = status_code


def _project():
    return {
        "strategy": {
            "audience": ["跑步新手"],
            "tone": "專業友善",
            "core_message": "先建立穩定訓練頻率",
            "platforms": ["Threads", "Blog"],
            "cta_strategy": "引導免費試用",
        }
    }


def test_compose_style_layers_stacks_and_skips_missing():
    merged = compose_style_layers(product_style="產品基底", platform_style="Threads 150 字內")
    assert "# Product Style" in merged
    assert "# Platform Style" in merged
    assert "# Project Style" not in merged


def test_plan_schedule_returns_one_to_two_week_plan():
    schedule = plan_schedule(strategy=_project()["strategy"], start_date=date(2026, 4, 20))
    assert 4 <= len(schedule) <= 14
    assert schedule[0]["date"] == "2026-04-20"
    assert {"date", "platform", "topic", "reason", "status"} <= schedule[0].keys()


def test_plan_schedule_preserves_confirmed_items():
    schedule = plan_schedule(
        strategy=_project()["strategy"],
        start_date=date(2026, 4, 20),
        existing_days=[
            {
                "date": "2026-04-20",
                "platform": "Threads",
                "topic": "既有主題",
                "reason": "已確認",
                "status": "confirmed",
            }
        ],
    )
    assert schedule[0]["topic"] == "既有主題"
    assert schedule[0]["status"] == "confirmed"


def test_confirmed_topics_turn_into_topic_planned_posts():
    posts = confirmed_topics_to_posts(
        [
            {"date": "2026-04-20", "platform": "Threads", "topic": "主題 A", "reason": "原因", "status": "confirmed"},
            {"date": "2026-04-21", "platform": "Blog", "topic": "主題 B", "reason": "原因", "status": "suggested"},
        ]
    )
    assert posts == [
        {
            "id": "post-1",
            "platform": "Threads",
            "title": "主題 A",
            "preview": "原因",
            "workflow_status": "topic_planned",
        }
    ]


def test_build_intel_summary_returns_trend_and_content_direction():
    intel = build_intel_summary(
        topic="跑步新手暖身",
        keyword_trends=["跑步暖身", "跑前拉伸", "慢跑新手"],
        high_performing_examples=["Threads 爆文 A", "Threads 爆文 B"],
    )
    assert intel["trend_summary"]
    assert len(intel["content_direction"]) >= 2


def test_intel_writeback_returns_document_and_entry():
    payload = intel_writeback(
        build_intel_summary(
            topic="跑步新手暖身",
            keyword_trends=["跑步暖身"],
            high_performing_examples=["爆文"],
        ),
        project_id="proj-1",
        topic="跑步新手暖身",
    )
    assert payload["document"]["doc_kind"] == "intel"
    assert payload["entry"]["type"] == "insight"


def test_run_with_retry_retries_retryable_errors():
    attempts = []

    def flaky():
        attempts.append("x")
        if len(attempts) < 3:
            raise RetryableError(429)
        return "ok"

    value, used_attempts = run_with_retry(flaky, sleep_fn=lambda _: None)
    assert value == "ok"
    assert used_attempts == 3


def test_generate_master_post_uses_strategy_intel_style_and_knowledge():
    merged_style = compose_style_layers(product_style="品牌基底", project_style="本專案偏教練語氣")
    intel = build_intel_summary(
        topic="跑步新手暖身",
        keyword_trends=["跑步暖身"],
        high_performing_examples=["爆文"],
    )
    post = generate_master_post(
        project=_project(),
        topic="跑步新手暖身",
        intel_summary=intel,
        style_markdown=merged_style,
        knowledge_map_summary="產品特色：漸進式課表",
    )
    assert post["workflow_status"] == "draft_generated"
    assert post["image_brief"]
    assert "產品特色：漸進式課表" in post["preview"]
    assert post["used_style_markdown"] == merged_style


def test_generate_master_post_revision_creates_new_version():
    first = generate_master_post(
        project=_project(),
        topic="跑步新手暖身",
        intel_summary=build_intel_summary(topic="跑步新手暖身", keyword_trends=["跑步暖身"], high_performing_examples=["爆文"]),
        style_markdown="品牌基底",
        knowledge_map_summary="產品特色",
    )
    second = generate_master_post(
        project=_project(),
        topic="跑步新手暖身",
        intel_summary=build_intel_summary(topic="跑步新手暖身", keyword_trends=["跑步暖身"], high_performing_examples=["爆文"]),
        style_markdown="品牌基底",
        knowledge_map_summary="產品特色",
        revision_note="CTA 更具體",
        previous_versions=[first],
    )
    assert second["version"] == first["version"] + 1
    assert "CTA 更具體" in second["preview"]


def test_adapt_platform_variants_generates_versions_with_platform_style():
    variants = adapt_platform_variants(
        master_post={"title": "主文案", "preview": "preview", "version": 2},
        platforms=["Threads", "IG"],
        platform_styles={"Threads": "150 字內", "IG": "多一點情緒"},
    )
    assert variants["Threads"]["workflow_status"] == "platform_adapted"
    assert "150 字內" in variants["Threads"]["preview"]
    assert "多一點情緒" in variants["IG"]["preview"]


def test_single_platform_revision_isolated():
    variants = adapt_platform_variants(
        master_post={"title": "主文案", "preview": "preview", "version": 2},
        platforms=["Threads", "IG"],
        existing_variants={
            "Threads": {"platform": "Threads", "title": "old", "preview": "old preview", "workflow_status": "platform_adapted"},
            "IG": {"platform": "IG", "title": "ig", "preview": "ig preview", "workflow_status": "platform_adapted"},
        },
        revision_platform="Threads",
        platform_styles={"Threads": "新 Threads 風格"},
    )
    assert "新 Threads 風格" in variants["Threads"]["preview"]
    assert variants["IG"]["preview"] == "ig preview"


def test_load_postiz_credentials_comes_from_infra_env():
    creds = load_postiz_credentials({"POSTIZ_BASE_URL": "https://postiz.example.com", "POSTIZ_API_TOKEN": "secret"})
    assert creds.base_url == "https://postiz.example.com"
    assert creds.api_token == "secret"
    with pytest.raises(ValueError):
        load_postiz_credentials({})


def test_build_postiz_payload_and_publish_dry_run():
    payload = build_postiz_payload(
        post={"title": "主文案", "preview": "preview", "platform": "Threads"},
        schedule_at="2026-04-20T10:00:00Z",
        channel_account_id="acct-1",
        dry_run=True,
    )
    assert payload["dry_run"] is True

    result = publish_with_postiz(
        post={"title": "主文案", "preview": "preview", "platform": "Threads"},
        schedule_at="2026-04-20T10:00:00Z",
        channel_account_id="acct-1",
        dry_run=True,
        env={"POSTIZ_BASE_URL": "https://postiz.example.com", "POSTIZ_API_TOKEN": "secret"},
        client=lambda *_args: {"job_id": "unused"},
    )
    assert result["workflow_status"] == "scheduled"
    assert result["postiz_job_id"] == "dry-run"


def test_publish_with_postiz_retries_and_updates_status():
    calls = []

    def client(_creds, payload):
        calls.append(payload)
        if len(calls) < 3:
            raise RetryableError(503)
        return {"job_id": "job-1", "status": "published", "published_at": "2026-04-20T10:00:00Z"}

    result = publish_with_postiz(
        post={"title": "主文案", "preview": "preview", "platform": "Threads"},
        schedule_at="2026-04-20T10:00:00Z",
        channel_account_id="acct-1",
        dry_run=False,
        env={"POSTIZ_BASE_URL": "https://postiz.example.com", "POSTIZ_API_TOKEN": "secret"},
        client=client,
        sleep_fn=lambda _: None,
    )
    assert result["workflow_status"] == "published"
    assert result["postiz_job_id"] == "job-1"
    assert result["attempts"] == 3
