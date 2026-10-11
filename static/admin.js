const queueEl = document.getElementById("queue");
const summaryEl = document.getElementById("queue-summary");

const money = (cents) => "$" + (cents / 100).toFixed(2);
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// which status each button moves an order to, and what the button says
const NEXT = {
    pending: ["whisking", "Start whisking"],
    whisking: ["ready", "Mark ready"],
    ready: ["picked_up", "Picked up"],
  };
  
  async function setStatus(id, status) {
    await fetch("/admin/api/orders/" + id + "/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    refresh();   // redraw the queue right away
  }

function render(orders) {
  // Customer names are typed by users, so we only ever use textContent
  // (never innerHTML). That stops anyone injecting code into this page.
  queueEl.replaceChildren();
  summaryEl.textContent = orders.length
    ? orders.length + " open order" + (orders.length === 1 ? "" : "s") + ". Updates automatically."
    : "No open orders right now. New ones will show up here by themselves.";

  orders.forEach((o) => {
    const card = el("div", "card order-card");

    const head = el("div", "order-head");
    head.append(
      el("h2", null, o.customer_name + "  ·  " + money(o.total_cents)),
      el("span", "badge " + o.status, o.label)
    );

    const list = el("ul");
    o.items.forEach((i) => {
      list.appendChild(el("li", null,
        i.quantity + " × " + i.item_name + " (" + i.temp + ", " + i.milk + ", " + i.sweetness + ")"));
    });

    card.append(head, el("p", "muted", o.popup_location), list);
    const [next, text] = NEXT[o.status];
    const btn = el("button", "btn", text);
    btn.onclick = () => { btn.disabled = true; setStatus(o.id, next); };
    card.appendChild(btn);
    queueEl.appendChild(card);
  });
}

async function refresh() {
  try {
    const res = await fetch("/admin/api/orders");
    if (res.status === 401) { window.location.href = "/admin/login"; return; }
    render((await res.json()).orders);
  } catch (e) {
    summaryEl.textContent = "Connection lost, retrying...";
  }
}

refresh();
setInterval(refresh, 3000);