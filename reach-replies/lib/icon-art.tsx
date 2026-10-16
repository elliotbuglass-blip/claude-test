// The home-screen icon: "R&R" set heavy on black, monochrome like the page.
export function IconArt({ size }: { size: number }) {
  return (
    <div
      style={{
        width: size, height: size, background: "#0d0d0d", color: "#f2f1ef",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: size * 0.34, fontWeight: 800, letterSpacing: "-0.04em",
        fontFamily: "Helvetica, Arial, sans-serif",
      }}
    >
      R&amp;R
    </div>
  );
}
