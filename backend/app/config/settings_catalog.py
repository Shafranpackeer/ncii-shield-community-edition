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
        placeholder="NCII Shield <noreply@your-domain.example>",
    ),
    SettingDefinition(
        key="NOTICE_CONTACT_EMAIL",
        label="Notice contact email",
        description="Reply-to and contact footer email used in takedown templates.",
        category="White label",
        placeholder="takedown@your-domain.example",
    ),
    SettingDefinition(
        key="NOTICE_WEBSITE",
        label="Website",
        description="Public website or landing page shown in the footer.",
        category="White label",
        placeholder="https://your-domain.example",
    ),
    SettingDefinition(
        key="NOTICE_ORGANIZATION_URL",
        label="Organization URL",
        description="Optional fallback website used when NOTICE_WEBSITE is blank.",
        category="White label",
        placeholder="https://your-domain.example",
    ),
    SettingDefinition(
        key="NOTICE_SENDER_NAME",
        label="Sender name",
        description="Displayed in the signature block.",
        category="White label",
        placeholder="NCII Shield Takedown Team",
    ),
    SettingDefinition(
        key="NOTICE_SENDER_TITLE",
        label="Sender title",
        description="Displayed under the sender name.",
        category="White label",
        placeholder="Authorized Abuse Reporting Contact",
    ),
    SettingDefinition(
        key="NOTICE_ORGANIZATION",
        label="Organization",
        description="Brand shown in the signature block.",
        category="White label",
        placeholder="NCII Shield",
    ),
    SettingDefinition(
        key="NOTICE_CLIENT_NAME",
        label="Client name",
        description="Friendly label used in drafted notices.",
        category="White label",
        placeholder="the client",
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
