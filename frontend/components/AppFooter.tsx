export function AppFooter() {
  const version = process.env.NEXT_PUBLIC_APP_VERSION || 'community';

  return (
    <footer className="app-footer">
      <div className="footer-copy">
        <strong>Update available</strong>
        <span>Version {version}. Pull the latest GitHub changes and rebuild with <code>docker compose up -d --build</code>.</span>
      </div>
      <div className="footer-links">
        <a href="/settings">Settings</a>
        <a href="https://github.com/" target="_blank" rel="noreferrer">GitHub</a>
      </div>
      <style jsx>{`
        .app-footer {
          display: flex;
          justify-content: space-between;
          gap: 16px;
          align-items: center;
          border-top: 1px solid rgba(15, 23, 42, 0.08);
          background: rgba(248, 250, 252, 0.96);
          color: #334155;
          padding: 14px 20px;
          font-size: 13px;
        }

        .footer-copy {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }

        .footer-copy strong {
          color: #0f172a;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-size: 11px;
        }

        .footer-copy code {
          background: #e2e8f0;
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 8px;
          padding: 2px 6px;
          color: #0f172a;
        }

        .footer-links {
          display: flex;
          gap: 14px;
          flex-wrap: wrap;
        }

        .footer-links a {
          color: #2563eb;
          text-decoration: none;
        }

        @media (max-width: 780px) {
          .app-footer {
            flex-direction: column;
            align-items: flex-start;
          }
        }
      `}</style>
    </footer>
  );
}
