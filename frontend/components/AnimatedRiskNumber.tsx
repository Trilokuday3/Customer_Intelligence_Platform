/** The one deliberate motion moment on Customer 360: the headline risk
 * number fades/scales in on load instead of appearing instantly, drawing
 * the eye to the single most important figure on the page. Every other
 * element on the page is static. Pure CSS (see .risk-reveal in
 * globals.css) rather than a JS rAF loop -- the number is correct in
 * the server-rendered HTML from the start, so there's no dependency on
 * client-side timing to show the right value. Respects
 * prefers-reduced-motion via the global media query in globals.css. */
export default function AnimatedRiskNumber({ probability }: { probability: number }) {
  const tone = probability >= 0.5 ? "text-risk" : "text-retain";
  return <span className={`risk-reveal tabular text-5xl font-medium ${tone}`}>{(probability * 100).toFixed(1)}%</span>;
}
