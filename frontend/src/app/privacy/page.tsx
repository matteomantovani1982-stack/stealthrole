export default function PrivacyPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#03040f", color: "rgba(255,255,255,0.7)", fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif", padding: "60px 24px" }}>
      <div style={{ maxWidth: 680, margin: "0 auto" }}>
        <a href="/login" style={{ fontSize: 13, color: "#4d8ef5", textDecoration: "none", marginBottom: 32, display: "inline-block" }}>&larr; Back</a>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#fff", marginBottom: 8 }}>Privacy Policy</h1>
        <p style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", marginBottom: 32 }}>Last updated: April 2026</p>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>1. Information We Collect</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            We collect information you provide directly, such as your name, email address, and career preferences. We also collect usage data to improve the service.
          </p>
        </section>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>2. How We Use Your Information</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            Your information is used to provide career intelligence features, match you with relevant opportunities, and improve the platform experience.
          </p>
        </section>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>3. Data Security</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            We implement industry-standard security measures to protect your personal data. Your data is encrypted in transit and at rest.
          </p>
        </section>

        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>4. Data Sharing</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            We do not sell your personal data. We may share anonymized, aggregated data for analytics purposes. Your career data is never shared with employers without your explicit consent.
          </p>
        </section>

        <section>
          <h2 style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.85)", marginBottom: 8 }}>5. Contact</h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "rgba(255,255,255,0.55)" }}>
            Questions about your data? Contact us at <a href="mailto:support@stealthrole.com" style={{ color: "#4d8ef5" }}>support@stealthrole.com</a>.
          </p>
        </section>
      </div>
    </div>
  );
}
