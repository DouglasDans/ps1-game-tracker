import { fmtTime } from './utils.js';

// Shared line-chart pieces (Stats › Evolução, Detail › Tempo por mês): plain
// SVG strings in a fixed viewBox `box` = { w, h, pad }, values in seconds.

// Gridline steps: the smallest that keeps ≤ 5 lines, so a month that has
// barely started (17 min) gets 15-min steps instead of one empty hour.
const STEPS = [900, 1800, 3600, 7200, 10800, 18000, 36000, 72000];

// n is the number of x slots; a series may stop short of it (future days).
export function lineScales(allValues, n, box) {
  const peak = Math.max(1, ...allValues);
  const step = STEPS.find(s => peak / s <= 5) ?? STEPS[STEPS.length - 1];
  const max = Math.ceil(peak / step) * step;
  const plotW = box.w - box.pad.left - box.pad.right;
  const plotH = box.h - box.pad.top - box.pad.bottom;
  return {
    step, max,
    x: i => box.pad.left + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW),
    y: secs => box.pad.top + plotH - (secs / max) * plotH,
  };
}

export function linePath(values, sc) {
  return values.map((v, i) => `${i ? 'L' : 'M'}${sc.x(i).toFixed(1)},${sc.y(v).toFixed(1)}`).join('');
}

function axisLabel(secs) {
  const h = Math.floor(secs / 3600), m = (secs % 3600) / 60;
  return h && m ? `${h}h${m}` : m ? `${m}m` : `${h}h`;
}

// Horizontal gridlines with hour labels + x labels ({ i, text } — text may hold a <tspan>).
export function lineAxes(sc, xLabels, box) {
  const grid = [];
  for (let s = 0; s <= sc.max; s += sc.step) {
    const y = sc.y(s).toFixed(1);
    grid.push(`<line class="evo-grid" x1="${box.pad.left}" x2="${box.w - box.pad.right}" y1="${y}" y2="${y}"/>`,
      `<text class="evo-axis" x="${box.pad.left - 14}" y="${y}" text-anchor="end" dominant-baseline="middle">${axisLabel(s)}</text>`);
  }
  const labels = xLabels.map(({ i, text }) =>
    `<text class="evo-axis" x="${sc.x(i).toFixed(1)}" y="${box.h - 18}" text-anchor="middle">${text}</text>`);
  return grid.join('') + labels.join('');
}

// The emphasized line: colored path + dots where dotAt(), value labels where labelAt().
export function lineFocus(values, sc, color, dotAt, labelAt) {
  const points = values.map((v, i) => {
    if (!dotAt(values, i)) return '';
    const x = sc.x(i).toFixed(1), y = sc.y(v).toFixed(1);
    const label = labelAt(values, i)
      ? `<text class="evo-value" x="${x}" y="${(sc.y(v) - 16).toFixed(1)}" text-anchor="middle">${fmtTime(v)}</text>` : '';
    return `<circle class="evo-dot" cx="${x}" cy="${y}" r="5" style="fill:${color}"/>${label}`;
  }).join('');
  return `<path class="evo-line-focus" d="${linePath(values, sc)}" style="stroke:${color}"/>${points}`;
}
