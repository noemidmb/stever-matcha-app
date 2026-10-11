const root = document.getElementById("status-root");
const code = root.dataset.code;
const labelEl = document.getElementById("status-label");
const card = document.querySelector(".status-card");
const ORDER = ["pending", "whisking", "ready"];

function render(status, label) {
  labelEl.textContent = label;
  document.title = label + " | Stever Matcha";
  card.classList.toggle("ready", status === "ready");

  // picked_up counts as past every step
  const current = status === "picked_up" ? ORDER.length : ORDER.indexOf(status);
  document.querySelectorAll(".step").forEach((step, i) => {
    step.classList.toggle("done", i < current);
    step.classList.toggle("current", i === current);
  });
}

async function poll() {
  try {
    const res = await fetch("/api/orders/" + code);
    if (!res.ok) return;
    const data = await res.json();
    render(data.status, data.label);
  } catch (e) {
    // offline for a moment, so just try again on the next tick
  }
}

render(root.dataset.status, labelEl.textContent);
setInterval(poll, 3000);   // ask the server every 3 seconds