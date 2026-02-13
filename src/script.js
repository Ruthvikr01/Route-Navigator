// script.js
const svg = d3.select("#mapSvg");
const width = +svg.attr("width");
const height = +svg.attr("height");

// group layers
const gStates = svg.append("g").attr("id", "states-layer");
const gGraticule = svg.append("g").attr("id", "grid-layer");
const gRoutes = svg.append("g").attr("id", "route-layer");
const gCities = svg.append("g").attr("id", "cities-layer");

// UI elements
const sourceSel = document.getElementById("source");
const destSel = document.getElementById("destination");
const algSel = document.getElementById("algorithm");
const showBtn = document.getElementById("showBtn");
const zoomInBtn = document.getElementById("zoomIn");
const zoomOutBtn = document.getElementById("zoomOut");
const summaryBody = document.getElementById("summaryBody");
const segmentsBody = document.getElementById("segmentsBody");

// D3 projection & path
const projection = d3.geoAlbersUsa();
const pathGen = d3.geoPath().projection(projection);

// interactive zoom transform
const zoom = d3.zoom()
    .scaleExtent([0.35, 8])
    .on("zoom", (event) => {
      const t = event.transform;
      gStates.attr("transform", t);
      gGraticule.attr("transform", t);
      gRoutes.attr("transform", t);
      gCities.attr("transform", t);
    });

svg.call(zoom);

// global city data
let cities = [];
let idToCity = {};
let cityLatLon = {};
let topoStates = null;
let currentRouteSegments = null;
let citiesLoaded = false;
const US_TOPOJSON_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json";

// ----- Helpers -----
async function loadUSAtlas() {
  const res = await fetch(US_TOPOJSON_URL);
  if (!res.ok) throw new Error("Failed to load US topology: " + res.status);
  const topo = await res.json();
  topoStates = topojson.feature(topo, topo.objects.states);
}

async function loadCities() {
  const res = await fetch("/cities");
  if (!res.ok) throw new Error("Failed to load /cities: " + res.status);
  const data = await res.json();
  cities = (data.cities || []).slice();
  cities.forEach(c => {
    idToCity[c.id] = c;
    if (c.lat && c.lon) {
      cityLatLon[c.id] = { lat: +c.lat, lon: +c.lon };
    }
  });
}

// lat/lon for your cities
const HARDCODED_LATLON = {
  "CHI": {lat: 41.8781, lon: -87.6298},
  "STL": {lat: 38.6270, lon: -90.1994},
  "DAL": {lat: 32.7767, lon: -96.7970},
  "HOU": {lat: 29.7604, lon: -95.3698},
  "MEM": {lat: 35.1495, lon: -90.0490},
  "NAS": {lat: 36.1627, lon: -86.7816},
  "KC" : {lat: 39.0997, lon: -94.5786},
  "OMA": {lat: 41.2565, lon: -95.9345},
  "MSP": {lat: 44.9778, lon: -93.2650},
  "DSM": {lat: 41.5868, lon: -93.6250},
  "BIS": {lat: 46.8083, lon: -100.7837},
  "FGO": {lat: 46.8772, lon: -96.7898},
  "MKE": {lat: 43.0389, lon: -87.9065},
  "MAD": {lat: 43.0731, lon: -89.4012},
  "JAN": {lat: 32.2988, lon: -90.1848},
  "NOL": {lat: 29.9511, lon: -90.0715},
  "LIT": {lat: 34.7465, lon: -92.2896},
  "OKC": {lat: 35.4676, lon: -97.5164},
  "WIC": {lat: 37.6872, lon: -97.3301},
  "SAT": {lat: 29.4241, lon: -98.4936},
  "BIR": {lat: 33.5186, lon: -86.8104},
  "FSD": {lat: 43.5446, lon: -96.7311},
  "SPR": {lat: 37.2089, lon: -93.2923},
  "TUL": {lat: 36.15398, lon: -95.9928},
  "SHV": {lat: 32.5252, lon: -93.7502},
  "GRB": {lat: 44.5192, lon: -88.0198},
  "MOB": {lat: 30.6954, lon: -88.0399},
  "PEO": {lat: 40.6936, lon: -89.5890}
};

function prepareLatLon() {
  for (const id in HARDCODED_LATLON) {
    if (!cityLatLon[id]) cityLatLon[id] = HARDCODED_LATLON[id];
  }
  let i = 0;
  cities.forEach(c => {
    if (!cityLatLon[c.id]) {
      cityLatLon[c.id] = { lat: 36 + (i%5)*1.2, lon: -95 + Math.floor(i/5)*1.8 };
      i++;
    }
  });
}

// Draw states
function drawStates() {
  if (!topoStates) return;
  const features = topoStates.features || topoStates; // safety
  gStates.selectAll("path.state")
      .data(features)
      .join("path")
      .attr("class", "state")
      .attr("d", pathGen)
      .attr("fill", "#eaf2f5")
      .attr("stroke", "#c9dce3")
      .attr("stroke-width", 1)
      .attr("opacity", 0.95);
}

// Draw city nodes and labels
function drawCities() {
  const cityEntries = cities.map((c) => {
    const ll = cityLatLon[c.id];
    const p = projection([ll.lon, ll.lat]);
    if (!p) return null;
    return { id: c.id, name: c.name, state: c.state, x: p[0], y: p[1] };
  }).filter(d => d && d.x != null);

  const groups = gCities.selectAll("g.city").data(cityEntries, d => d.id);
  const enter = groups.enter().append("g").attr("class", "city");
  enter.append("circle").attr("r", 6).attr("fill", "#071422");
  enter.append("text").attr("font-size", 13).attr("dy", "0.35em").attr("x", 10).attr("fill", "#071422").attr("font-weight","600");

  groups.merge(enter)
      .attr("transform", d => `translate(${d.x},${d.y})`)
      .select("text")
      .text(d => d.id);

  groups.exit().remove();
}

function pointsToFeature(points) {
  const coords = points.map(p => [p.lon, p.lat]);
  return { type: "Feature", geometry: { type: "MultiPoint", coordinates: coords } };
}

// Draw route segments
function drawRouteSegments(segments) {
  gRoutes.selectAll("*").remove();

  if (!segments || !segments.length) {
    currentRouteSegments = null;
    return;
  }

  currentRouteSegments = segments.slice();

  segments.forEach((s, i) => {
    const a = cityLatLon[s.src_id];
    const b = cityLatLon[s.dst_id];
    if (!a || !b) return;
    const pa = projection([a.lon, a.lat]);
    const pb = projection([b.lon, b.lat]);
    if (!pa || !pb) return;

    gRoutes.append("line")
        .attr("x1", pa[0]).attr("y1", pa[1])
        .attr("x2", pb[0]).attr("y2", pb[1])
        .attr("stroke", "#e53935")
        .attr("stroke-width", 6)
        .attr("stroke-linecap", "round")
        .attr("opacity", 0.95);
    const mx = (pa[0] + pb[0]) / 2;
    const my = (pa[1] + pb[1]) / 2;
    gRoutes.append("text")
        .attr("x", mx)
        .attr("y", my - 10)
        .attr("text-anchor", "middle")
        .attr("font-size", 13)
        .attr("fill", "#0b53c3")
        .attr("stroke", "#fff")
        .attr("stroke-width", 3)
        .text(`${(s.real_dist||0).toFixed(1)} mi`);
    gRoutes.append("text")
        .attr("x", mx)
        .attr("y", my - 10)
        .attr("text-anchor", "middle")
        .attr("font-size", 13)
        .attr("fill", "#0b53c3")
        .text(`${(s.real_dist||0).toFixed(1)} mi`);
  });

  // red/green endpoint markers
  const first = segments[0], last = segments[segments.length-1];
  if (first) {
    const a = cityLatLon[first.src_id]; const pa = projection([a.lon,a.lat]);
    if (pa) {
      gRoutes.append("circle").attr("cx", pa[0]).attr("cy", pa[1]).attr("r", 8).attr("fill","#00c853").attr("stroke","#00c853").attr("stroke-width",4);
    }
  }
  if (last) {
    const b = cityLatLon[last.dst_id]; const pb = projection([b.lon,b.lat]);
    if (pb) {
      gRoutes.append("circle").attr("cx", pb[0]).attr("cy", pb[1]).attr("r", 8).attr("fill","#b20b0b").attr("stroke","#b20b0b").attr("stroke-width",4);
    }
  }
}

// Update UI summary and segments
function showSummaryAndSegments(data) {
  if(!data || !data.ok) {
    summaryBody.innerHTML = `<p class="muted">No route</p>`;
    segmentsBody.innerHTML = `<p class="muted">No segments</p>`;
    return;
  }

  const alg = data.algorithm_label || data.label || data.algorithm || "Route";
  const fromLabel = `${data.src_name || idToCity[data.src_id].name} (${data.src_id}, ${idToCity[data.src_id].state})`;
  const toLabel = `${data.dst_name || idToCity[data.dst_id].name} (${data.dst_id}, ${idToCity[data.dst_id].state})`;

  const total = (data.total_distance || 0);
  const gas = (data.gas_used || 0);
  const risk = (data.total_risk || 0);
  const bestDate = data.best_travel_date || data.best_date || "N/A";

  summaryBody.innerHTML = `
    <p><strong>Algorithm:</strong> ${alg}</p>
    <p><strong>From:</strong> ${fromLabel}</p>
    <p><strong>To:</strong> ${toLabel}</p>
    <p><strong>Total Distance:</strong> <b>${total.toFixed(2)}</b> mi</p>
    <p><strong>Total Gas Consumption:</strong> ${gas.toFixed(2)} gal</p>
    <p><strong>MPG:</strong> 45 mi/gal</p>
    <p><strong>Total Risk:</strong> ${risk.toFixed(2)}</p>
    <p><strong>Best Travel Date:</strong> ${bestDate}</p>
  `;

  const segs = data.segments || [];
  if (!segs.length) {
    segmentsBody.innerHTML = `<p class="muted">No segments</p>`;
    return;
  }
  let html = "<ol>";
  segs.forEach(s => {
    const srcN = s.src_name || idToCity[s.src_id].name;
    const dstN = s.dst_name || idToCity[s.dst_id].name;
    const srcSt = idToCity[s.src_id].state;
    const dstSt = idToCity[s.dst_id].state;
    html += `<li>${srcN} (${s.src_id}, ${srcSt}) → ${dstN} (${s.dst_id}, ${dstSt}) : ${(s.real_dist||0).toFixed(1)} miles</li>`;
  });
  html += "</ol>";
  segmentsBody.innerHTML = html;
}

zoomInBtn.addEventListener("click", () => {
  svg.transition().duration(350).call(zoom.scaleBy, 1.2);
});
zoomOutBtn.addEventListener("click", () => {
  svg.transition().duration(350).call(zoom.scaleBy, 1 / 1.2);
});

showBtn.addEventListener("click", async () => {
  if (!citiesLoaded) {
    console.log("Cities still loading… retrying in 200ms");
    setTimeout(() => showBtn.click(), 200);
    return;
  }

  const src = sourceSel.value;
  const dst = destSel.value;
  const alg = algSel.value || "BEST";
  if (!src || !dst) {
    alert("Select Source and Destination");
    return;
  }
  const q = `/route?src=${encodeURIComponent(src)}&dst=${encodeURIComponent(dst)}&alg=${encodeURIComponent(alg)}`;
  try {
    const res = await fetch(q);
    if (!res.ok) throw new Error("Server returned " + res.status);
    const data = await res.json();
    if (!data.ok) throw new Error(data.message || "No route returned");

    drawStates();
    drawCities();
    drawRouteSegments(data.segments || []);
    showSummaryAndSegments(data);
    focusToRoute(data.segments || []);
  } catch (err) {
    console.error(err);
    alert("Error fetching route: " + err);
  }
});

function focusToRoute(segments) {
  const ids = new Set();
  (segments || []).forEach(s => { ids.add(s.src_id); ids.add(s.dst_id); });
  const pts = Array.from(ids).map(id => cityLatLon[id]).filter(Boolean);
  if (!pts.length) return;
  const feature = pointsToFeature(pts);
  projection.fitExtent([[80, 40], [width - 80, height - 40]], feature);

  drawStates();
  drawCities();
  if (currentRouteSegments) drawRouteSegments(currentRouteSegments);
}

(async function init() {
  try {
    await Promise.all([loadUSAtlas(), loadCities()]);
    prepareLatLon();
    cities.forEach(c => {
      const label = `${c.name} (${c.id}, ${c.state})`;
      const o1 = document.createElement("option"); o1.value = c.id; o1.text = label;
      sourceSel.appendChild(o1);
      const o2 = document.createElement("option"); o2.value = c.id; o2.text = label;
      destSel.appendChild(o2);
    });
    if (sourceSel.options.length) sourceSel.selectedIndex = 0;
    if (destSel.options.length > 1) destSel.selectedIndex = 1;
    const CST_states = new Set(["IL","MO","WI","IA","MN","NE","KS","ND","SD","AR","OK","TX","LA","MS","TN","KY","AL"]);
    const cstIDs = cities.filter(c => CST_states.has(c.state)).map(c => c.id);
    const focusIDs = cstIDs.length ? cstIDs : cities.map(c => c.id);

    const pts = focusIDs.map(id => cityLatLon[id]).filter(Boolean);
    if (pts.length) projection.fitExtent([[80,40],[width-80,height-40]], pointsToFeature(pts));
    else projection.translate([width/2, height/2]).scale(800);

    drawStates();
    drawCities();

    summaryBody.innerHTML = `<p class="muted">Choose source/destination and press <strong>Show Route</strong>.</p>`;
    segmentsBody.innerHTML = `<p class="muted">Segments appear here.</p>`;
    citiesLoaded = true;
  } catch (err) {
    console.error("Initialization failed:", err);
    alert("Initialization failed: " + err);
    summaryBody.innerHTML = `<p class="muted">Initialization error: ${err}</p>`;
  }
})();
