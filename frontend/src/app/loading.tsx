export default function Loading() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f4f5fb",
      }}
    >
      <div
        style={{
          width: 24,
          height: 24,
          border: "2px solid #5B6CFF",
          borderTopColor: "transparent",
          borderRadius: "50%",
          animation: "spin 0.6s linear infinite",
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
