const form        = document.querySelector("#download-form");
const queryInput  = document.querySelector("#query");
const logPre      = document.querySelector("#log-pre");
const filesEl     = document.querySelector("#files-list");
const statusBadge = document.querySelector("#status-badge");
const archiveBanner = document.querySelector("#archive-banner");
const archiveBtn  = document.querySelector("#archive-btn");
const archiveCount = document.querySelector("#archive-count");
const submitBtn   = document.querySelector("#submit-btn");
const refreshBtn  = document.querySelector("#refresh-btn");
const outputMode  = document.querySelector("#output-mode");
const customRow   = document.querySelector("#custom-row");
const autoZip     = document.querySelector("#auto-zip");
const formatSel   = document.querySelector("#format");
const qualitySel  = document.querySelector("#quality");

const SETTINGS_KEY = "spotdl-settings-v2";
let activeJobId = null;
let pollTimer   = null;
const autoZipped = new Set();

/* ── Helpers ── */
function prettyBytes(b) {
  if (b < 1024)        return b + " B";
  if (b < 1048576)     return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
}

function setBadge(status) {
  const map = {
    idle:     ["badge-idle",    "Idle"],
    queued:   ["badge-queued",  "Queued"],
    running:  ["badge-running", "Downloading"],
    complete: ["badge-complete","Complete"],
    failed:   ["badge-failed",  "Failed"],
  };
  const [cls, label] = map[status] || map.idle;
  statusBadge.className = "badge " + cls;
  statusBadge.innerHTML = `<span class="badge-dot"></span>${label}`;
}

function colorLog(line) {
  const el = document.createElement("span");
  if (/Downloaded/i.test(line))      el.className = "log-dl";
  else if (/error|failed/i.test(line)) el.className = "log-err";
  else if (/Skipping/i.test(line))   el.className = "log-skip";
  el.textContent = line + "\n";
  return el;
}

function appendLog(lines) {
  logPre.innerHTML = "";
  for (const line of lines) logPre.appendChild(colorLog(line));
  logPre.parentElement.scrollTop = logPre.parentElement.scrollHeight;
}

/* ── Settings persistence ── */
function loadSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
    if (s.format)         formatSel.value   = s.format;
    if (s.quality)        qualitySel.value  = s.quality;
    if (s.outputMode)     outputMode.value  = s.outputMode;
    if (s.customTemplate) document.querySelector("#custom-template").value = s.customTemplate;
    if (typeof s.autoZip === "boolean") autoZip.checked = s.autoZip;
  } catch { localStorage.removeItem(SETTINGS_KEY); }
  syncCustomRow();
}

function saveSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({
    format:         formatSel.value,
    quality:        qualitySel.value,
    outputMode:     outputMode.value,
    customTemplate: document.querySelector("#custom-template").value,
    autoZip:        autoZip.checked,
  }));
}

function syncCustomRow() {
  customRow.hidden = outputMode.value !== "custom";
}

/* ── Archive banner ── */
function showArchive(job) {
  if (!job.archive?.ready) return;
  const n = job.archive.file_count;
  archiveCount.textContent = n === 1 ? "1 new track ready" : `${n} new tracks ready`;
  archiveBtn.onclick = () => {
    const a = document.createElement("a");
    a.href = job.archive.url;
    a.download = job.archive.name || "spotdl-download.zip";
    a.click();
  };
  archiveBanner.hidden = false;
  if (autoZip.checked && !autoZipped.has(job.id)) {
    autoZipped.add(job.id);
    archiveBtn.click();
  }
}

/* ── Files list ── */
async function refreshFiles() {
  const res  = await fetch("/api/files");
  const data = await res.json();
  filesEl.innerHTML = "";
  if (!data.files.length) {
    filesEl.innerHTML = '<p class="files-empty">No files yet.</p>';
    return;
  }
  for (const f of data.files) {
    const a = document.createElement("a");
    a.className = "file-item";
    a.href = f.url;
    a.innerHTML = `
      <span class="file-name" title="${f.name}">${f.name}</span>
      <span class="file-meta">${prettyBytes(f.size)}</span>
    `;
    filesEl.appendChild(a);
  }
}

/* ── Job polling ── */
async function pollJob() {
  if (!activeJobId) return;
  const res = await fetch("/api/jobs/" + activeJobId);
  const job = await res.json();

  setBadge(job.status);
  const header = [`Status: ${job.status}`, `Query: ${job.query}`, `Output: ${job.output_mode}`, ""];
  appendLog(header.concat(job.log || []));

  if (job.archive?.ready) showArchive(job);

  if (job.status === "complete" || job.status === "failed") {
    clearInterval(pollTimer);
    pollTimer = null;
    submitBtn.disabled = false;
    submitBtn.textContent = "Download";
    await refreshFiles();
  }
}

/* ── Form submit ── */
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  saveSettings();
  archiveBanner.hidden = true;
  logPre.innerHTML = "";
  submitBtn.disabled = true;
  submitBtn.textContent = "Starting…";
  setBadge("queued");

  const res = await fetch("/api/download", { method: "POST", body: new FormData(form) });
  if (!res.ok) {
    const err = await res.json();
    appendLog(["Error: " + (err.detail || "Could not start download.")]);
    setBadge("failed");
    submitBtn.disabled = false;
    submitBtn.textContent = "Download";
    return;
  }
  const data = await res.json();
  activeJobId = data.job_id;
  submitBtn.textContent = "Downloading…";
  await pollJob();
  clearInterval(pollTimer);
  pollTimer = setInterval(pollJob, 1500);
});

/* ── Event listeners ── */
outputMode.addEventListener("change", () => { syncCustomRow(); saveSettings(); });
for (const el of [formatSel, qualitySel, autoZip]) {
  el.addEventListener("change", saveSettings);
}
document.querySelector("#custom-template").addEventListener("input", saveSettings);
refreshBtn.addEventListener("click", refreshFiles);

/* ── Init ── */
loadSettings();
setBadge("idle");
refreshFiles();
