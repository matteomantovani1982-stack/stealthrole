"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
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
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
          Something went wrong
        </h2>
        <p style={{ fontSize: 14, color: "rgba(12,16,48,0.62)", marginBottom: 24 }}>
          {error.message || "An unexpected error occurred."}
        </p>
        <button
          onClick={reset}
          style={{
            padding: "10px 24px",
            borderRadius: 8,
            border: "none",
            background: "linear-gradient(135deg, #5B6CFF, #9F7AEA)",
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}
