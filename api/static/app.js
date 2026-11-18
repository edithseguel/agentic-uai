const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const dialog = document.querySelector("#settings-dialog");
const settingsForm = document.querySelector("#settings-form");
const apiKeyInput = document.querySelector("#api-key-input");
const apiStatus = document.querySelector("#api-status");
const settingsError = document.querySelector("#settings-error");

const routeNames = {
  preventa: "Preventa",
  postventa: "Postventa",
  generica: "General",
};

function getUserId() {
  let userId = localStorage.getItem("tecnosur-chat-user");
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem("tecnosur-chat-user", userId);
  }
  return userId;
}

function setApiStatus(connected) {
  apiStatus.textContent = connected ? "Servidor disponible" : "Servidor desconectado";
  apiStatus.classList.toggle("ready", connected);
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

function addMessage(text, role, time = new Date()) {
  const row = document.createElement("article");
  row.className = `message-row ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const body = document.createElement("p");
  body.className = "bubble-text";
  body.textContent = text;
  bubble.append(body);
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = time.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
  bubble.append(meta);
  row.append(bubble);
  messages.append(row);
  scrollToBottom();
  return { row, bubble, meta };
}

function addTrace(bubble, data) {
  const tag = document.createElement("span");
  tag.className = "route-tag";
  tag.textContent = routeNames[data.ruta] || data.ruta;
  bubble.querySelector(".message-meta").prepend(tag);

  const details = document.createElement("details");
  details.className = "trace-details";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = `Recorrido del agente · ${data.pasos.length} pasos`;
  details.append(summary);

  const reason = document.createElement("p");
  reason.className = "trace-reason";
  reason.textContent = data.motivo;
  details.append(reason);

  const list = document.createElement("ol");
  list.className = "trace-list";
  for (const step of data.pasos) {
    const item = document.createElement("li");
    item.className = `trace-step${step.nodo === "herramienta" ? " tool" : ""}`;
    const title = document.createElement("strong");
    title.textContent = step.nodo === "herramienta"
      ? `Herramienta · ${step.detalle}`
      : step.detalle;
    const nodeName = document.createElement("span");
    nodeName.textContent = step.nodo;
    item.append(title, nodeName);
    list.append(item);
  }
  details.append(list);
  bubble.append(details);
  scrollToBottom();
}

function showSettings() {
  settingsError.textContent = "";
  settingsError.classList.remove("success");
  apiKeyInput.value = "";
  if (!dialog.open) dialog.showModal();
  apiKeyInput.focus();
}

async function checkApi() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("API unavailable");
    setApiStatus(true);
  } catch {
    setApiStatus(false);
  }
}

document.querySelector("#settings-button").addEventListener("click", showSettings);
document.querySelector("#cancel-settings").addEventListener("click", () => dialog.close());
document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.textContent;
    form.requestSubmit();
  });
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const key = apiKeyInput.value.trim();
  if (!key) {
    settingsError.textContent = "Ingresa una clave API válida.";
    return;
  }

  const saveButton = settingsForm.querySelector(".primary-button");
  saveButton.disabled = true;
  settingsError.classList.remove("success");
  settingsError.textContent = "Verificando clave…";
  try {
    const response = await fetch("/auth/check", {
      headers: { "X-API-Key": key },
    });
    if (response.status === 401) {
      sessionStorage.removeItem("tecnosur-chat-api-key");
      settingsError.textContent = "La clave no coincide con la configurada en el servidor.";
      setApiStatus(false);
      return;
    }
    if (!response.ok) throw new Error("No fue posible validar la clave.");

    sessionStorage.setItem("tecnosur-chat-api-key", key);
    settingsError.textContent = "Clave validada correctamente.";
    settingsError.classList.add("success");
    setApiStatus(true);
    window.setTimeout(() => {
      dialog.close();
      input.focus();
    }, 1800);
  } catch (error) {
    settingsError.textContent = error.message || "No se pudo validar la clave.";
    setApiStatus(false);
  } finally {
    saveButton.disabled = false;
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const texto = input.value.trim();
  if (!texto || sendButton.disabled) return;
  const apiKey = sessionStorage.getItem("tecnosur-chat-api-key");
  if (!apiKey) {
    showSettings();
    settingsError.textContent = "Configura tu clave API antes de enviar mensajes.";
    return;
  }

  addMessage(texto, "user");
  input.value = "";
  sendButton.disabled = true;
  input.disabled = true;
  const loading = document.createElement("article");
  loading.className = "message-row assistant";
  const loadingBubble = document.createElement("div");
  loadingBubble.className = "bubble typing";
  loadingBubble.setAttribute("aria-label", "El asistente está escribiendo");
  for (let i = 0; i < 3; i += 1) loadingBubble.append(document.createElement("i"));
  loading.append(loadingBubble);
  messages.append(loading);
  scrollToBottom();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
      body: JSON.stringify({ user_id: getUserId(), texto }),
    });
    const data = await response.json();
    loading.remove();
    if (response.status === 401) {
      sessionStorage.removeItem("tecnosur-chat-api-key");
      setApiStatus(false);
      showSettings();
      settingsError.textContent = "La clave API no es válida. Revisa e inténtalo otra vez.";
      throw new Error("No se pudo autorizar la solicitud.");
    }
    if (!response.ok) throw new Error(data.detail || "No fue posible obtener una respuesta.");
    const reply = addMessage(data.respuesta, "assistant");
    addTrace(reply.bubble, data);
  } catch (error) {
    loading.remove();
    if (error instanceof TypeError) {
      addMessage("No se pudo conectar con el servidor. Comprueba que la API esté en ejecución e inténtalo de nuevo.", "assistant");
    } else if (error.message !== "No se pudo autorizar la solicitud.") {
      const errorMessage = addMessage(error.message || "Ocurrió un error inesperado.", "assistant");
      errorMessage.bubble.classList.add("error-text");
    }
  } finally {
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
  }
});

checkApi();
if (!sessionStorage.getItem("tecnosur-chat-api-key")) {
  window.setTimeout(showSettings, 250);
}
