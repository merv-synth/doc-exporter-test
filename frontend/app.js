const LOCAL_API_BASE = "http://localhost:8000";
const HOSTNAME_API_BASE_MAP = {
  localhost: LOCAL_API_BASE,
  "127.0.0.1": LOCAL_API_BASE,
};

const API_BASE =
  window.__API_BASE__ || HOSTNAME_API_BASE_MAP[window.location.hostname] || LOCAL_API_BASE;

const apiKeyInput = document.getElementById("apiKey");
const loadVideosBtn = document.getElementById("loadVideosBtn");
const exportPdfBtn = document.getElementById("exportPdfBtn");
const exportWordBtn = document.getElementById("exportWordBtn");
const videoList = document.getElementById("videoList");
const videoGallery = document.getElementById("videoGallery");
const loadingEl = document.getElementById("loading");
const errorEl = document.getElementById("error");
const successEl = document.getElementById("success");
const logsEl = document.getElementById("logs");
const clearLogsBtn = document.getElementById("clearLogsBtn");
const logsCountEl = document.getElementById("logsCount");

let logEntriesCount = 0;

function setLoading(isLoading) {
  loadingEl.classList.toggle("hidden", !isLoading);
  loadVideosBtn.disabled = isLoading;
  exportPdfBtn.disabled = isLoading || !videoList.value;
  exportWordBtn.disabled = isLoading || !videoList.value;
}

function setError(message) {
  errorEl.textContent = message;
  errorEl.classList.toggle("hidden", !message);
}

function setSuccess(message) {
  successEl.textContent = message;
  successEl.classList.toggle("hidden", !message);
}

function maskApiKey(apiKey) {
  if (!apiKey) {
    return "(empty)";
  }
  if (apiKey.length <= 8) {
    return "*".repeat(apiKey.length);
  }
  return `${apiKey.slice(0, 4)}...${apiKey.slice(-4)}`;
}

function formatLogPayload(payload) {
  if (payload === undefined || payload === null || payload === "") {
    return "";
  }
  if (typeof payload === "string") {
    return payload;
  }

  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

function updateLogsCount() {
  if (!logsCountEl) {
    return;
  }

  const label = logEntriesCount === 1 ? "entry" : "entries";
  logsCountEl.textContent = `${logEntriesCount} ${label}`;
}

function addLog(step, payload = "") {
  const now = new Date().toLocaleTimeString();
  const message = `[${now}] ${step}`;
  const payloadText = formatLogPayload(payload);
  const line = payloadText ? `${message}\n${payloadText}` : message;

  logsEl.textContent += `${line}\n\n`;
  logEntriesCount += 1;
  updateLogsCount();
  logsEl.scrollTop = logsEl.scrollHeight;
  console.log("[UI LOG]", step, payload);
}

async function fetchWithLogging(url, options = {}) {
  let requestBody = options.body;
  if (typeof requestBody === "string") {
    try {
      requestBody = JSON.parse(requestBody);
    } catch {
      // leave raw string as-is
    }
  } else if (requestBody instanceof FormData) {
    requestBody = Object.fromEntries(requestBody.entries());
  }

  addLog("➡️ API request", {
    url,
    method: options.method || "GET",
    headers: options.headers || {},
    body: requestBody || null,
  });

  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";

  let bodyPreview = "<non-json or binary body>";
  if (contentType.includes("application/json")) {
    const jsonPayload = await response.clone().json().catch(() => ({}));
    bodyPreview = jsonPayload;
  } else {
    const textPayload = await response.clone().text().catch(() => "");
    bodyPreview = textPayload;
  }

  addLog("⬅️ API response", {
    url,
    status: response.status,
    ok: response.ok,
    contentType,
    bodyPreview,
  });

  return response;
}

function clearVideoGallery() {
  videoGallery.innerHTML = "";
  videoList.value = "";
}

function renderVideoCards(videos) {
  clearVideoGallery();

  for (const video of videos) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "video-card";
    card.dataset.videoId = video.id;

    const thumb = document.createElement("img");
    thumb.className = "video-card__thumbnail";
    thumb.loading = "lazy";
    thumb.src = video.thumbnail?.image || "";
    thumb.alt = `${video.title} thumbnail`;
    thumb.referrerPolicy = "no-referrer";

    if (!video.thumbnail?.image) {
      thumb.classList.add("video-card__thumbnail--hidden");
    }

    const details = document.createElement("div");
    details.className = "video-card__details";

    const title = document.createElement("p");
    title.className = "video-card__title";
    title.textContent = video.title || video.id;

    const status = document.createElement("p");
    status.className = "video-card__status";
    status.textContent = `Status: ${video.status || "unknown"}`;

    details.appendChild(title);
    details.appendChild(status);
    card.appendChild(thumb);
    card.appendChild(details);

    card.addEventListener("click", () => {
      videoList.value = video.id;
      document.querySelectorAll(".video-card.is-selected").forEach((el) => {
        el.classList.remove("is-selected");
      });
      card.classList.add("is-selected");
      exportPdfBtn.disabled = false;
      addLog("Video selection changed", { selectedVideoId: video.id });
    });

    videoGallery.appendChild(card);
  }

  if (videos.length > 0) {
    const firstCard = videoGallery.querySelector(".video-card");
    if (firstCard) {
      firstCard.click();
    }
  }
}

async function loadVideos() {
  const apiKey = apiKeyInput.value.trim();
  if (!apiKey) {
    setError("Please enter your Synthesia API key.");
    addLog("Validation failed: API key missing");
    return;
  }

  setError("");
  setSuccess("");
  setLoading(true);

  addLog("Starting Load Videos flow", {
    apiBase: API_BASE,
    apiKey: maskApiKey(apiKey),
  });

  try {
    const url = `${API_BASE}/videos`;
    const response = await fetchWithLogging(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ api_key: apiKey }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Failed to load videos.");
    }

    const data = await response.json();
    addLog("Processing /videos payload", {
      videoCount: (data.videos || []).length,
    });

    const videos = data.videos || [];
    renderVideoCards(videos);

    exportPdfBtn.disabled = !videoList.value;
    exportWordBtn.disabled = !videoList.value;
    if (!videos.length) {
      setError("No videos were returned for this account.");
      addLog("No videos available for account");
    } else {
      addLog("Videos loaded into UI", {
        selectedVideoId: videoList.value,
      });
    }
  } catch (error) {
    addLog("Load Videos failed", {
      error: error.message || "Unknown error",
    });
    setError(error.message || "Unexpected error while loading videos.");
  } finally {
    setLoading(false);
  }
}

async function exportDocument(format) {
  const apiKey = apiKeyInput.value.trim();
  const videoId = videoList.value;
  const normalizedFormat = format === "word" ? "word" : "pdf";
  const endpoint = normalizedFormat === "word" ? "export-word" : "export-pdf";
  const extension = normalizedFormat === "word" ? "docx" : "pdf";
  const successLabel = normalizedFormat === "word" ? "Word document" : "PDF";

  if (!apiKey || !videoId) {
    setError("Please provide an API key and select a video.");
    addLog("Validation failed: missing API key or video", {
      hasApiKey: Boolean(apiKey),
      hasVideoId: Boolean(videoId),
    });
    return;
  }

  setError("");
  setSuccess("");
  setLoading(true);

  addLog(`Starting Export ${successLabel} flow`, {
    videoId,
    apiKey: maskApiKey(apiKey),
  });

  try {
    const formData = new FormData();
    formData.append("api_key", apiKey);
    formData.append("video_id", videoId);

    const response = await fetchWithLogging(`${API_BASE}/${endpoint}`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `Failed to export ${successLabel}.`);
    }

    const blob = await response.blob();
    addLog(`Received ${successLabel} payload`, {
      sizeBytes: blob.size,
      mimeType: blob.type || "application/octet-stream",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${videoId}.${extension}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    addLog(`Triggered ${successLabel} download`, {
      filename: `${videoId}.${extension}`,
    });
    setSuccess(`${successLabel} exported successfully.`);
  } catch (error) {
    addLog(`Export ${successLabel} failed`, {
      error: error.message || "Unknown error",
    });
    setError(error.message || `Unexpected error while exporting ${successLabel}.`);
  } finally {
    setLoading(false);
  }
}

async function exportPdf() {
  return exportDocument("pdf");
}

async function exportWord() {
  return exportDocument("word");
}

clearLogsBtn.addEventListener("click", () => {
  logsEl.textContent = "";
  logEntriesCount = 0;
  updateLogsCount();
  addLog("Logs cleared by user");
});

loadVideosBtn.addEventListener("click", loadVideos);
exportPdfBtn.addEventListener("click", exportPdf);
exportWordBtn.addEventListener("click", exportWord);
addLog("UI initialized", { apiBase: API_BASE });

updateLogsCount();
