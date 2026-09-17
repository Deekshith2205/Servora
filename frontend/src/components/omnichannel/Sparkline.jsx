// A genuinely real sparkline — takes a plain array of numbers (real
// daily counts from analytics.trend/channel_trend, never invented) and
// draws it as a filled SVG path. No charting library: this is a dozen
// points on a line, not worth a dependency for.
export default function Sparkline({ values, color = "#2563EB", height = 32, width = 96 }) {
  if (!values || values.length < 2) {
    return <svg width={width} height={height} aria-hidden="true" />;
  }
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);

  const points = values.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return [x, y];
  });

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={areaPath} fill={color} opacity="0.12" />
      <path d={linePath} fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r="2.5" fill={color} />
    </svg>
  );
}
