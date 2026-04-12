from __future__ import annotations

TENANTS = [
    {"id": "acme-support", "label": "Acme Support", "tier": "internal", "region": "eu-central-1"},
    {"id": "acme-ops", "label": "Acme Ops", "tier": "production", "region": "eu-central-1"},
    {"id": "acme-finance", "label": "Acme Finance", "tier": "sensitive", "region": "eu-central-1"},
]

POLICY_BUNDLES = [
    {
        "id": "bundle_v8",
        "label": "Baseline Runtime Policy",
        "mode": "balanced",
        "controls": ["approval-gates", "prompt-injection-check", "tool-scope"],
    },
    {
        "id": "bundle_v9_strict",
        "label": "Strict Finance Policy",
        "mode": "strict",
        "controls": ["approval-gates", "write-downgrade", "finance-guardrail", "prompt-injection-check"],
    },
    {
        "id": "bundle_v9_readonly",
        "label": "Read-Only Constrained Policy",
        "mode": "readonly",
        "controls": ["deny-write", "retrieval-only", "approval-gates"],
    },
]
