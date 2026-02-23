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
const videoList = document.getElementById("videoList");
const loadingEl = document.getElementById("loading");
const errorEl = document.getElementById("error");
const successEl = document.getElementById("success");
const logsEl = document.getElementById("logs");
const clearLogsBtn = document.getElementById("clearLogsBtn");

function setLoading(isLoading) {
  loadingEl.classList.toggle("hidden", !isLoading);
  loadVideosBtn.disabled = isLoading;
  exportPdfBtn.disabled = isLoading || !videoList.value;
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

function addLog(step, payload = "") {
  const now = new Date().toLocaleTimeString();
  const message = `[${now}] ${step}`;
  const payloadText = formatLogPayload(payload);
  const line = payloadText ? `${message}\n${payloadText}` : message;

  logsEl.textContent += `${line}\n\n`;
  logsEl.scrollTop = logsEl.scrollHeight;
  console.log("[UI LOG]", step, payload);
}

async function fetchWithLogging(url, options = {}) {
  addLog("➡️ API request", {
    url,
    method: options.method || "GET",
    headers: options.headers || {},
  });

  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";

  let bodyPreview = "<non-json or binary body>";
  if (contentType.includes("application/json")) {
    const jsonPayload = await response.clone().json().catch(() => ({}));
    bodyPreview = jsonPayload;
  } else {
    const textPayload = await response.clone().text().catch(() => "");
    bodyPreview = textPayload.slice(0, 500);
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
    const url = `${API_BASE}/videos?api_key=${encodeURIComponent(apiKey)}`;
    const response = await fetchWithLogging(url);

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Failed to load videos.");
    }

    const data = await response.json();
    addLog("Processing /videos payload", {
      videoCount: (data.videos || []).length,
    });

    videoList.innerHTML = "";

    for (const video of data.videos || []) {
      const option = document.createElement("option");
      option.value = video.id;
      option.textContent = `${video.title} (${video.status || "unknown"})`;
      videoList.appendChild(option);
    }

    exportPdfBtn.disabled = !videoList.value;
    if (!videoList.options.length) {
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

async function exportPdf() {
  const apiKey = apiKeyInput.value.trim();
  const videoId = videoList.value;

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

  addLog("Starting Export PDF flow", {
    videoId,
    apiKey: maskApiKey(apiKey),
  });

  try {
    const formData = new FormData();
    formData.append("api_key", apiKey);
    formData.append("video_id", videoId);

    const response = await fetchWithLogging(`${API_BASE}/export-pdf`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Failed to export PDF.");
    }

    const blob = await response.blob();
    addLog("Received PDF payload", {
      sizeBytes: blob.size,
      mimeType: blob.type || "application/octet-stream",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${videoId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    addLog("Triggered PDF download", {
      filename: `${videoId}.pdf`,
    });
    setSuccess("PDF exported successfully.");
  } catch (error) {
    addLog("Export PDF failed", {
      error: error.message || "Unknown error",
    });
    setError(error.message || "Unexpected error while exporting PDF.");
  } finally {
    setLoading(false);
  }
}

videoList.addEventListener("change", () => {
  exportPdfBtn.disabled = !videoList.value;
  addLog("Video selection changed", { selectedVideoId: videoList.value || null });
});

clearLogsBtn.addEventListener("click", () => {
  logsEl.textContent = "";
  addLog("Logs cleared by user");
});

loadVideosBtn.addEventListener("click", loadVideos);
exportPdfBtn.addEventListener("click", exportPdf);
addLog("UI initialized", { apiBase: API_BASE });
