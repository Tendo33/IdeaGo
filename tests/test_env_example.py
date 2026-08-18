"""`.env.example` must describe settings that actually exist.

The audit found six drifted entries, including `ENVIRONMENT=testing` — a value
the validator rejects, so anyone copying the example and following the comment
got a server that refused to boot. Documentation drift of this kind is invisible
until someone new tries to deploy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ideago.config.settings import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def _declared_variables() -> dict[str, str]:
    declared: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        declared[key.strip()] = value.strip()
    return declared


def test_every_documented_variable_maps_to_a_setting() -> None:
    known = {name.upper() for name in Settings.model_fields}
    unknown = sorted(set(_declared_variables()) - known)

    assert not unknown, (
        f".env.example documents variables with no matching setting: {unknown}. "
        "Either add the field or delete the line."
    )


def test_example_environment_value_is_accepted() -> None:
    """The exact drift that made a copied example fail to boot."""
    value = _declared_variables()["ENVIRONMENT"]
    Settings(_env_file=None, environment=value)


@pytest.mark.parametrize(
    "name",
    [
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "AUTH_SESSION_SECRET",
        "FRONTEND_APP_URL",
        "TURNSTILE_SECRET_KEY",
        "TURNSTILE_SITE_KEY",
        "OPENAI_API_KEY",
        "FORWARDED_ALLOW_IPS",
        "DAILY_ANALYSIS_LIMIT",
        "AUTH_SESSION_CACHE_TTL_SECONDS",
    ],
)
def test_operationally_required_variables_are_documented(name: str) -> None:
    """A setting nobody knows about is a setting nobody configures."""
    assert name in _declared_variables(), f"{name} is missing from .env.example"


def test_numeric_examples_are_within_their_validated_ranges() -> None:
    """A documented value outside a field's bounds is a boot failure waiting."""
    declared = _declared_variables()
    numeric = {
        key: value
        for key, value in declared.items()
        if value and value.replace(".", "", 1).isdigit()
    }
    overrides = {key.lower(): value for key, value in numeric.items()}

    # Constructing with every documented numeric value must not raise.
    Settings(_env_file=None, **overrides)
