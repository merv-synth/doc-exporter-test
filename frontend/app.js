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

async function loadVideos() {
  const apiKey = apiKeyInput.value.trim();
  if (!apiKey) {
    setError("Please enter your Synthesia API key.");
    return;
  }

  setError("");
  setSuccess("");
  setLoading(true);

  try {
    const response = await fetch(`${API_BASE}/videos?api_key=${encodeURIComponent(apiKey)}`);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Failed to load videos.");
    }

    const data = await response.json();
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
    }
  } catch (error) {
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
    return;
  }

  setError("");
  setSuccess("");
  setLoading(true);

  try {
    const formData = new FormData();
    formData.append("api_key", apiKey);
    formData.append("video_id", videoId);

    const response = await fetch(`${API_BASE}/export-pdf`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Failed to export PDF.");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${videoId}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    setSuccess("PDF exported successfully.");
  } catch (error) {
    setError(error.message || "Unexpected error while exporting PDF.");
  } finally {
    setLoading(false);
  }
}

videoList.addEventListener("change", () => {
  exportPdfBtn.disabled = !videoList.value;
});

loadVideosBtn.addEventListener("click", loadVideos);
exportPdfBtn.addEventListener("click", exportPdf);
