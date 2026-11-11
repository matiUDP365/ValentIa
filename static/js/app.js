document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('input[name="role"]').forEach((input) => {
    input.addEventListener("change", () => {
      document.querySelectorAll(".role-option").forEach((option) => option.classList.remove("selected"));
      input.closest(".role-option").classList.add("selected");
    });
  });

  const reveal = document.querySelector(".reveal-password");
  if (reveal) {
    reveal.addEventListener("click", () => {
      const password = document.querySelector("#password");
      const showing = password.type === "text";
      password.type = showing ? "password" : "text";
      reveal.textContent = showing ? "Mostrar" : "Ocultar";
      reveal.setAttribute("aria-label", showing ? "Mostrar contraseña" : "Ocultar contraseña");
    });
  }

  const menu = document.querySelector(".mobile-menu");
  const sidebar = document.querySelector(".sidebar");
  if (menu && sidebar) menu.addEventListener("click", () => sidebar.classList.toggle("sidebar-open"));

  const monitoringPanel = document.querySelector("[data-monitoring-url]");
  if (monitoringPanel) {
    const refreshMonitoring = async () => {
      try {
        const response = await fetch(monitoringPanel.dataset.monitoringUrl, { cache: "no-store" });
        if (!response.ok) return;
        const result = await response.json();
        document.querySelectorAll("[data-component-id]").forEach((card) => {
          const component = result.components.find((item) => item.id === card.dataset.componentId);
          if (!component) return;
          const badge = card.querySelector("[data-component-status]");
          if (badge) {
            badge.classList.remove("status-healthy", "status-pending", "status-error");
            badge.classList.add(`status-${component.health}`);
            const label = badge.querySelector("span");
            if (label) label.textContent = component.state;
          }
          const detail = card.querySelector("[data-component-detail]");
          if (detail) detail.textContent = component.detail;
        });
        const updatedAt = document.querySelector("#monitoringUpdatedAt");
        if (updatedAt) updatedAt.textContent = result.updated_at;
        const banner = document.querySelector("#monitoringDemoBanner");
        if (banner) {
          banner.hidden = result.source === "raspberry";
          const note = banner.querySelector("div span");
          if (note) note.textContent = result.integration_note;
        }
      } catch (_error) {
        // Si no hay conexión, se conservan los últimos datos mostrados.
      }
    };
    refreshMonitoring();
    window.setInterval(refreshMonitoring, 3000);
  }

  const readerPanel = document.querySelector("#readerPanel");
  if (readerPanel) {
    const feed = document.querySelector("#readerFeed");
    const placeholder = document.querySelector("#readerPlaceholder");
    const liveBadge = document.querySelector("#previewLive");
    const state = document.querySelector("#readerState");
    const startButton = document.querySelector("#readerStart");
    const stopButton = document.querySelector("#readerStop");
    const sign = document.querySelector("#detectedSign");
    const confidence = document.querySelector("#readerConfidence");
    const confidenceBar = document.querySelector("#confidenceBar");
    const phrase = document.querySelector("#readerPhrase");
    const error = document.querySelector("#readerError");
    const speak = document.querySelector("#readerSpeak");
    let streamOpen = false;

    const refreshReader = async () => {
      try {
        const response = await fetch(readerPanel.dataset.statusUrl, { cache: "no-store" });
        if (!response.ok) throw new Error("No se pudo consultar el estado del lector.");
        const result = await response.json();
        const active = result.running;
        state.classList.toggle("is-running", active);
        state.classList.toggle("is-error", result.state === "error");
        state.querySelector("span").textContent = result.state === "starting" ? "Iniciando" : active ? "Activo" : result.state === "error" ? "Revisar lector" : "Detenido";
        startButton.hidden = active;
        stopButton.hidden = !active;
        speak.disabled = !result.audio_ready;
        sign.textContent = result.sign || "—";
        confidence.textContent = result.sign ? `${result.confidence}%` : "—";
        confidenceBar.style.width = `${result.sign ? result.confidence : 0}%`;
        phrase.textContent = result.phrase || "Tu frase aparecerá aquí.";
        error.hidden = !result.error;
        error.textContent = result.error || "";
        placeholder.hidden = active;
        feed.hidden = !active;
        liveBadge.hidden = !active;

        const moduleStatus = {
          camera: [result.camera_ready ? "Capturando" : result.state === "error" ? "Error" : "Detenida", result.camera_ready ? "healthy" : result.state === "error" ? "error" : "pending"],
          edge: [result.running ? "Activo" : result.model_ready ? "Listo" : result.state === "error" ? "Error" : "Detenido", result.model_ready ? "healthy" : result.state === "error" ? "error" : "pending"],
          gestures: [result.running ? "Detectando" : result.model_ready ? "Modelo cargado" : result.state === "error" ? "Error" : "Detenido", result.model_ready ? "healthy" : result.state === "error" ? "error" : "pending"],
          audio: [result.audio_ready ? "Disponible" : "No disponible", result.audio_ready ? "healthy" : "pending"],
        };
        document.querySelectorAll("[data-component-id]").forEach((card) => {
          const update = moduleStatus[card.dataset.componentId];
          if (!update) return;
          const badge = card.querySelector("[data-component-status]");
          badge.classList.remove("status-healthy", "status-pending", "status-error");
          badge.classList.add(`status-${update[1]}`);
          badge.querySelector("span").textContent = update[0];
        });

        if (active && !streamOpen) {
          feed.src = `${readerPanel.dataset.videoUrl}?session=${Date.now()}`;
          streamOpen = true;
        } else if (!active && streamOpen) {
          feed.removeAttribute("src");
          streamOpen = false;
        }
      } catch (_error) {
        state.classList.add("is-error");
        state.querySelector("span").textContent = "Sin comunicación";
      }
    };

    refreshReader();
    window.setInterval(refreshReader, 900);
  }
});
