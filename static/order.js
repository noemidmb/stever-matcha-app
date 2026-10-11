const money = (cents) => "$" + (cents / 100).toFixed(2);

// helper: make an element with a class and text
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

let cart = [];  // each entry: {key, name, milk, sweetness, temp, unit_cents, quantity}
const linesEl = document.getElementById("cart-lines");
const totalEl = document.getElementById("cart-total");
const placeBtn = document.getElementById("place-order");
const errorEl = document.getElementById("order-error");
const nameInput = document.getElementById("customer-name");
const asideEl = document.querySelector(".cart");

// ----- each drink card: live price + "Add to cart" -----
document.querySelectorAll(".drink").forEach((card) => {
  const basePrice = Number(card.dataset.price);
  const priceEl = card.querySelector(".live-price");
  const pick = (field) => card.querySelector("[name=" + field + "]").value;
  const unitPrice = () => basePrice + window.MILK_PRICES[pick("milk")];

  function refresh() {
    priceEl.textContent = money(unitPrice());
  }
  card.querySelectorAll("select").forEach((s) => s.addEventListener("change", refresh));
  refresh();

  card.querySelector(".add").addEventListener("click", () => {
    const line = {
        menu_item_id: Number(card.dataset.id),
        name: card.dataset.name,
        milk: pick("milk"),
        sweetness: pick("sweetness"),
        temp: pick("temp"),
        unit_cents: unitPrice(),
        quantity: 1,
    };
    // same drink + same choices = bump the quantity instead of a new line
    line.key = [line.name, line.milk, line.sweetness, line.temp].join("|");
    const existing = cart.find((l) => l.key === line.key);
    if (existing) {
      existing.quantity += 1;
    } else {
      cart.push(line);
    }
    renderCart();
  });
});

// ----- cart display -----
function changeQty(line, delta) {
  line.quantity += delta;
  if (line.quantity <= 0) {
    cart = cart.filter((l) => l !== line);
  }
  renderCart();
}

function renderCart() {
  linesEl.replaceChildren();  // clear the cart display, then redraw it

  if (cart.length === 0) {
    linesEl.appendChild(el("p", "muted", "Your cart is empty. Add a drink!"));
  }

  cart.forEach((line) => {
    const row = el("div", "cart-line");

    const info = el("div", "cart-info");
    info.append(
      el("strong", null, line.name),
      el("div", "muted", line.temp + " · " + line.milk + " · " + line.sweetness)
    );

    const qty = el("div", "qty");
    const minus = el("button", "qty-btn", "−");
    const plus = el("button", "qty-btn", "+");
    minus.type = "button";
    plus.type = "button";
    minus.onclick = () => changeQty(line, -1);
    plus.onclick = () => changeQty(line, 1);
    qty.append(minus, el("span", null, String(line.quantity)), plus,
               el("span", "muted", money(line.unit_cents * line.quantity)));

    row.append(info, qty);
    linesEl.appendChild(row);
  });

  const total = cart.reduce((sum, l) => sum + l.unit_cents * l.quantity, 0);
  totalEl.textContent = money(total);
  placeBtn.disabled = cart.length === 0;
}
// ----- place the order -----
placeBtn.addEventListener("click", async () => {
    errorEl.textContent = "";
    placeBtn.disabled = true;
    placeBtn.textContent = "Placing...";
    try {
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          popup_id: window.POPUP_ID,
          customer_name: nameInput.value,
          items: cart.map((l) => ({
            menu_item_id: l.menu_item_id,
            milk: l.milk,
            sweetness: l.sweetness,
            temp: l.temp,
            quantity: l.quantity,
          })),
        }),
      });
      const data = await res.json();
      if (res.ok) {
        asideEl.replaceChildren(
          el("h2", null, "Order placed! 🍵"),
          el("p", null, "Thanks, " + nameInput.value.trim() + "! Pay at the pop-up when you pick up."),
          el("p", "muted", "Your order code: " + data.code)
        );
        return;
      }
      errorEl.textContent = data.error || "Something went wrong.";
    } catch (e) {
      errorEl.textContent = "Couldn't reach the server. Try again.";
    }
    placeBtn.textContent = "Place order";
    placeBtn.disabled = cart.length === 0;
  });
renderCart();