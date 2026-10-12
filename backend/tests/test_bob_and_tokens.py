"""
Unit and integration tests for IBM Bob Shell integration, LLMService, and Token/Cost accounting.
"""

import pytest
from backend.bob_client import BobClient, BobExecutionResult
from backend.llm_client import LLMService, TokenTracker
from backend.models import TokenUsage, TriageRequest, TriageResponse, TriageSummary, SalesRecommendationTier
from backend.pdf_generator import ExecutivePDFGenerator


def test_token_usage_model():
    """Verify TokenUsage dataclass and calculations."""
    usage = TokenUsage(
        input_tokens=1500,
        output_tokens=300,
        total_tokens=1800,
        cost_usd=0.0035,
        llm_provider="ibm_bob",
        llm_model="bob-shell",
        calls_count=2,
    )
    assert usage.input_tokens == 1500
    assert usage.output_tokens == 300
    assert usage.total_tokens == 1800
    assert usage.cost_usd == 0.0035
    assert usage.llm_provider == "ibm_bob"


def test_token_tracker_accumulation():
    """Verify TokenTracker records and aggregates multiple calls correctly."""
    tracker = TokenTracker(provider="ibm_bob", model="bob-shell")
    tracker.record(input_tokens=1000, output_tokens=100, cost_usd=0.002)
    tracker.record(input_tokens=500, output_tokens=50, cost_usd=0.001)

    model = tracker.to_model()
    assert model.input_tokens == 1500
    assert model.output_tokens == 150
    assert model.total_tokens == 1650
    assert model.cost_usd == 0.003
    assert model.calls_count == 2
    assert model.llm_provider == "ibm_bob"


def test_bob_client_initialization():
    """Verify BobClient binary resolution and availability checks."""
    client = BobClient(api_key="test-api-key")
    # Binary should resolve to standard path or 'bob'
    assert client.binary is not None
    assert client.api_key == "test-api-key"
    assert client.is_available() is True


def test_llm_service_provider_selection():
    """Verify LLMService provider resolution logic."""
    service_bob = LLMService(provider="ibm_bob", bobshell_api_key="key-123")
    assert service_bob.provider == "ibm_bob"
    assert service_bob.tracker.provider == "ibm_bob"

    service_gemini = LLMService(provider="gemini", gemini_api_key="key-abc")
    assert service_gemini.provider == "gemini"


def test_pdf_export_with_token_usage():
    """Verify ExecutivePDFGenerator renders PDF when token_usage is present."""
    report = {
        "project_name": "Test Token Workload",
        "primary_package_name": "nginx",
        "package_ecosystem": "container",
        "package_version": "1.24",
        "target_os": "RHEL9",
        "target_platform": "OPENSHIFT",
        "summary": {
            "total_packages": 1,
            "native_count": 1,
            "agnostic_count": 0,
            "substitute_count": 0,
            "unported_count": 0,
            "blocker_count": 0,
            "readiness_score_pct": 100.0,
            "recommendation": "Minimal Effort",
            "recommendation_reason": "Turnkey deployment ready.",
            "estimated_effort_pd": 0,
            "min_total_person_days": 0,
            "max_total_person_days": 0,
            "unported_transitive_deps_count": 0,
            "test_deps_unresolved_count": 0,
        },
        "packages": [],
        "token_usage": {
            "input_tokens": 16060,
            "output_tokens": 140,
            "total_tokens": 16200,
            "cost_usd": 0.032158,
            "llm_provider": "ibm_bob",
            "llm_model": "bob-shell",
            "calls_count": 1,
        }
    }
    pdf_bytes = ExecutivePDFGenerator.generate(report)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_token_stage_breakdown():
    """Verify TokenTracker records stage breakdowns and calculates percentages."""
    tracker = TokenTracker(provider="ibm_bob", model="bob-shell")
    tracker.record(input_tokens=1000, output_tokens=200, cost_usd=0.004, stage="Component Qualification")
    tracker.record(input_tokens=500, output_tokens=100, cost_usd=0.002, stage="Component Qualification")
    tracker.record(input_tokens=2000, output_tokens=400, cost_usd=0.008, stage="SIMD Architecture Complexity")
    tracker.record(input_tokens=300, output_tokens=50, cost_usd=0.001, stage="Executive Sales Proposal")

    usage = tracker.to_model()
    assert usage.calls_count == 4
    assert usage.input_tokens == 3800
    assert usage.output_tokens == 750
    assert usage.total_tokens == 4550
    assert round(usage.cost_usd, 3) == 0.015
    assert len(usage.breakdown) == 3

    # Breakdown should be sorted by cost descending
    top = usage.breakdown[0]
    assert top.stage == "SIMD Architecture Complexity"
    assert top.calls_count == 1
    assert top.cost_usd == 0.008
    assert top.percentage == pytest.approx(53.3, 0.1)

    second = usage.breakdown[1]
    assert second.stage == "Component Qualification"
    assert second.calls_count == 2
    assert second.total_tokens == 1800
    assert second.cost_usd == 0.006
    assert second.percentage == pytest.approx(40.0, 0.1)

    third = usage.breakdown[2]
    assert third.stage == "Executive Sales Proposal"
    assert third.calls_count == 1
    assert third.cost_usd == 0.001
    assert third.percentage == pytest.approx(6.7, 0.1)


def test_pdf_export_with_token_breakdown():
    """Verify ExecutivePDFGenerator renders PDF when stage breakdown is present in token_usage."""
    report = {
        "project_name": "Test Workload with Breakdown",
        "primary_package_name": "rocksdb",
        "target_os": "RHEL9",
        "target_platform": "OPENSHIFT",
        "summary": {
            "total_packages": 1,
            "native_count": 0,
            "agnostic_count": 0,
            "substitute_count": 0,
            "unported_count": 1,
            "blocker_count": 0,
            "readiness_score_pct": 50.0,
            "recommendation": "Moderate Porting Effort",
            "recommendation_reason": "SIMD porting needed.",
            "unported_transitive_deps_count": 0,
        },
        "packages": [],
        "token_usage": {
            "input_tokens": 5000,
            "output_tokens": 500,
            "total_tokens": 5500,
            "cost_usd": 0.011,
            "llm_provider": "ibm_bob",
            "llm_model": "bob-shell",
            "calls_count": 2,
            "breakdown": [
                {
                    "stage": "Component Qualification",
                    "calls_count": 1,
                    "input_tokens": 2000,
                    "output_tokens": 200,
                    "total_tokens": 2200,
                    "cost_usd": 0.0044,
                    "percentage": 40.0,
                },
                {
                    "stage": "SIMD Architecture Complexity",
                    "calls_count": 1,
                    "input_tokens": 3000,
                    "output_tokens": 300,
                    "total_tokens": 3300,
                    "cost_usd": 0.0066,
                    "percentage": 60.0,
                }
            ]
        }
    }
    pdf_bytes = ExecutivePDFGenerator.generate(report)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")

