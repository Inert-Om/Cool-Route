// All backend calls live here, so components never contain raw fetch().
async function json(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export const getConfig = () => fetch("/api/config").then(json);
export const getScenarios = () => fetch("/api/scenarios").then(json);
export const getSegments = () => fetch("/api/segments").then(json);
export const getWaterPoints = () => fetch("/api/water-points").then(json);
export const getPlaces = () => fetch("/api/places").then(json);

export const getRoutes = (params) =>
  fetch("/api/route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  }).then(json);
