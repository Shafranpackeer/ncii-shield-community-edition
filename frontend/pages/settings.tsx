import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { configAPI, RuntimeSetting } from '../api/client';
import { useToast } from '../components/Toast';

type SettingsMap = Record<string, string>;

const brandLines = [
  'Created by Shafran Packeer',
  'shafranpackeer.com',
  'vesamuni.com',
];

export default function SettingsPage() {
  const router = useRouter();
  const toast = useToast();
  const [settings, setSettings] = useState<RuntimeSetting[]>([]);
  const [values, setValues] = useState<SettingsMap>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await configAPI.listSettings();
      setSettings(data.settings || []);
      const nextValues = (data.settings || []).reduce<SettingsMap>((acc, setting) => {
        acc[setting.key] = setting.value || '';
        return acc;
      }, {});
      setValues(nextValues);
    } catch (error) {
      console.error('Failed to load settings:', error);
      toast.push('Failed to load runtime settings.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const groupedSettings = useMemo(() => {
    return settings.reduce<Record<string, RuntimeSetting[]>>((groups, setting) => {
      const bucket = groups[setting.category] || [];
      bucket.push(setting);
      groups[setting.category] = bucket;
      return groups;
    }, {});
  }, [settings]);

  const updateSetting = (key: string, value: string) => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  const saveAll = async () => {
    setSaving(true);
    try {
      await configAPI.saveSettings(
        settings.map((setting) => ({
          key: setting.key,
          value: values[setting.key] ?? '',
        }))
      );
      toast.push('Runtime settings saved.', 'success');
      await loadSettings();
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.push('Failed to save runtime settings.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const copyEnv = async () => {
    const snippet = settings
      .map((setting) => `${setting.key}=${values[setting.key] ?? ''}`)
      .join('\n');
    await navigator.clipboard.writeText(snippet);
    toast.push('Copied .env snippet to clipboard.', 'success');
  };

  return (
    <div className="settings-page">
      <div className="settings-shell">
        <header className="settings-header">
          <div>
            <div className="eyebrow">Settings</div>
            <h1>Runtime configuration</h1>
            <p>Manage provider keys, sender identity, and white-label values without editing code.</p>
          </div>
          <div className="settings-actions">
            <button className="secondary-button" onClick={() => router.push('/')}>Back to dashboard</button>
            <button className="secondary-button" onClick={copyEnv} disabled={loading}>Copy .env</button>
            <button className="primary-button" onClick={saveAll} disabled={loading || saving}>
              {saving ? 'Saving…' : 'Save settings'}
            </button>
          </div>
        </header>

        <section className="info-strip">
          <div>
            <strong>Runtime behavior</strong>
            <p>These values are stored in Postgres and override matching environment variables for the running stack.</p>
          </div>
          <div>
            <strong>White label</strong>
            <p>If no website is set, notices fall back to the email domain or stay blank. No hardcoded brand domain is used.</p>
          </div>
          <div>
            <strong>Branding</strong>
            <p>{brandLines.join(' · ')}</p>
          </div>
        </section>

        {loading ? (
          <div className="settings-grid">
            {[1, 2, 3].map((item) => (
              <div key={item} className="setting-card skeleton-card" />
            ))}
          </div>
        ) : (
          Object.entries(groupedSettings).map(([category, categorySettings]) => (
            <section key={category} className="settings-group">
              <h2>{category}</h2>
              <div className="settings-grid">
                {categorySettings.map((setting) => (
                  <article key={setting.key} className="setting-card">
                    <div className="setting-head">
                      <div>
                        <div className="eyebrow">{setting.key}</div>
                        <h3>{setting.label}</h3>
                      </div>
                      {setting.docs_url && (
                        <a href={setting.docs_url} target="_blank" rel="noreferrer" className="docs-link">
                          How to get it
                        </a>
                      )}
                    </div>
                    <p className="muted">{setting.description}</p>
                    <div className="setting-input-row">
                      <input
                        type={setting.secret && !revealed[setting.key] ? 'password' : 'text'}
                        value={values[setting.key] ?? ''}
                        placeholder={setting.placeholder || ''}
                        onChange={(event) => updateSetting(setting.key, event.target.value)}
                        autoComplete="off"
                        spellCheck={false}
                      />
                      {setting.secret && (
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => setRevealed((current) => ({ ...current, [setting.key]: !current[setting.key] }))}
                        >
                          {revealed[setting.key] ? 'Hide' : 'Reveal'}
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))
        )}
      </div>

      <style jsx>{`
        .settings-page {
          min-height: 100vh;
          background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.06), transparent 34%),
            radial-gradient(circle at right 20%, rgba(45, 212, 191, 0.04), transparent 28%),
            linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
          color: #0f172a;
        }

        .settings-shell {
          max-width: 1180px;
          margin: 0 auto;
          padding: 28px 22px 56px;
        }

        .settings-header {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          align-items: flex-start;
          margin-bottom: 20px;
        }

        .settings-header h1 {
          font-size: clamp(2rem, 3vw, 3rem);
          margin: 8px 0 10px;
        }

        .settings-header p,
        .muted,
        .info-strip p {
          color: #475569;
          line-height: 1.55;
        }

        .settings-actions {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }

        .primary-button,
        .secondary-button,
        .ghost-button {
          border: 1px solid transparent;
          border-radius: 12px;
          padding: 10px 14px;
          font-weight: 700;
          cursor: pointer;
        }

        .primary-button {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          color: #f8fafc;
        }

        .secondary-button,
        .ghost-button {
          background: rgba(255, 255, 255, 0.9);
          color: #0f172a;
          border-color: rgba(15, 23, 42, 0.08);
        }

        .info-strip {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 24px;
        }

        .info-strip > div {
          background: rgba(255, 255, 255, 0.84);
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 18px;
          padding: 16px;
        }

        .settings-group {
          margin-top: 22px;
        }

        .settings-group h2 {
          font-size: 1.1rem;
          margin-bottom: 12px;
        }

        .settings-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
        }

        .setting-card {
          background: rgba(255, 255, 255, 0.84);
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 18px;
          padding: 16px;
          box-shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
        }

        .setting-head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: flex-start;
          margin-bottom: 8px;
        }

        .setting-card h3 {
          margin: 6px 0 0;
          font-size: 1.05rem;
        }

        .docs-link {
          color: #2563eb;
          text-decoration: none;
          white-space: nowrap;
        }

        .setting-input-row {
          display: flex;
          gap: 10px;
          align-items: center;
          margin-top: 12px;
        }

        .setting-input-row input {
          flex: 1;
          min-width: 0;
          border-radius: 12px;
          border: 1px solid rgba(15, 23, 42, 0.10);
          background: #f8fafc;
          color: #0f172a;
          padding: 12px 14px;
        }

        .eyebrow {
          color: #2563eb;
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .skeleton-card {
          min-height: 170px;
          background: linear-gradient(90deg, rgba(148,163,184,0.08), rgba(148,163,184,0.20), rgba(148,163,184,0.08));
          background-size: 200% 100%;
          animation: shimmer 1.4s infinite;
        }

        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }

        @media (max-width: 900px) {
          .settings-header,
          .settings-actions,
          .info-strip,
          .settings-grid {
            grid-template-columns: 1fr;
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
}
