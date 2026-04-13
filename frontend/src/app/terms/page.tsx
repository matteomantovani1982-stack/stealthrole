export default function TermsPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#03040f", color: "rgba(255,255,255,0.7)", fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif", padding: "60px 24px" }}>
      <div style={{ maxWidth: 680, margin: "0 auto" }}>
        <a href="/login" style={{ fontSize: 13, color: "#4d8ef5", textDecoration: "none", marginBottom: 32, display: "inline-block" }}>&larr; Back</a>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#fff", marginBottom: 8 }}>Terms of Service</h1>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", marginBottom: 32 }}>Last updated: April 2026</p>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>1. Acceptance of Terms</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            By accessing or using StealthRole you agree to be bound by these Terms of Service. If you do not agree, please do not use the platform.
          </p>
        </section>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>2. Use of Service</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            StealthRole provides career intelligence tools including job matching, market signals, and application management. You agree to use these services only for lawful purposes and in accordance with these terms.
          </p>
        </section>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>3. Account Responsibility</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.
          </p>
        </section>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>4. Limitation of Liability</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            StealthRole is provided &quot;as is&quot; without warranties of any kind. We are not liable for any damages arising from your use of the platform.
          </p>
        </section>

        <section>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>5. Contact</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            Questions about these terms? Contact us at <a href="mailto:support@stealthrole.com" style={{ color: "#4d8ef5" }}>support@stealthrole.com</a>.
          </p>
        </section>
      </div>
    </div>
  );
}
