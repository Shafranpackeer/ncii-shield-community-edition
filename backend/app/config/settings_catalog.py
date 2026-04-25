"""Catalog of editable runtime settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    description: str
    category: str
    docs_url: str | None = None
    secret: bool = False
    placeholder: str | None = None


SETTINGS_CATALOG: list[SettingDefinition] = [
    SettingDefinition(
        key="RESEND_API_KEY",
        label="Resend API key",
        description="Used for outbound email delivery and webhook tracking.",
        category="Email",
        docs_url="https://resend.com/docs/dashboard/api-keys/introduction",
        secret=True,
        placeholder="re_...",
    ),
    SettingDefinition(
        key="RESEND_FROM_EMAIL",
        label="From address",
        description="The sender identity shown on outgoing notices.",
        category="Email",
        docs_url="https://resend.com/docs",
        placeholder="",
    ),
    SettingDefinition(
        key="SERPER_API_KEY",
        label="Serper API key",
        description="Google results for discovery queries.",
        category="Discovery",
        docs_url="https://serper.dev/",
        secret=True,
        placeholder="serper_...",
    ),
    SettingDefinition(
        key="SERPAPI_KEY",
        label="SerpAPI key",
        description="Google/Yandex discovery queries through SerpAPI.",
        category="Discovery",
        docs_url="https://serpapi.com/",
        secret=True,
        placeholder="api_...",
    ),
    SettingDefinition(
        key="BING_API_KEY",
        label="Bing API key",
        description="Bing web and visual search fallback.",
        category="Discovery",
        docs_url="https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/create-bing-search-service-resource",
        secret=True,
        placeholder="Azure key",
    ),
]
