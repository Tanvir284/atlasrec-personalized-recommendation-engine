async function waitForChart(page) {
  await page.waitForFunction(() => {
    const bars = [...document.querySelectorAll(".recharts-bar-rectangle")];
    const heights = bars.map(bar => Math.round(bar.getBoundingClientRect().height * 10) / 10);
    if (!heights.length || Math.max(...heights) < 10) return false;
    const signature = heights.join(",");
    const previous = window.__atlasrecChartReadiness;
    const stable = previous?.signature === signature ? previous.stable + 1 : 0;
    window.__atlasrecChartReadiness = { signature, stable };
    return stable >= 30;
  });
}
module.exports = { waitForChart };
