import Link from "next/link";

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f4f5fb",
        fontFamily: "Inter, system-ui, sans-serif",
        color: "#0c1030",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 420, padding: 32 }}>
        <div
          style={{
            fontSize: 48,
            fontWeight: 800,
            color: "#5B6CFF",
            marginBottom: 8,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          404
        </div>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
          Page not found
        </h2>
        <p style={{ fontSize: 14, color: "rgba(12,16,48,0.62)", marginBottom: 24 }}>
          The page you&apos;re looking for doesn&apos;t exist.
        </p>
        <Link
          href="/"
          style={{
            display: "inline-block",
            padding: "10px 24px",
            borderRadius: 8,
            background: "linear-gradient(135deg, #5B6CFF, #9F7AEA)",
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            textDecoration: "none",
          }}
        >
          Go home
        </Link>
      </div>
    </div>
  );
}
