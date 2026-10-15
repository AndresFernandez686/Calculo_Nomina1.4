(function () {
  const input = document.getElementById("valor_por_hora");
  const button = document.getElementById("hora_predeterminada");
  const status = document.getElementById("hora_predeterminada_estado");
  const storageKey = "nomina.valorPorHoraPredeterminado";
  let enabled = false;

  function normalize(value) {
    const text = value.trim();
    if (!/^(?:[0-9]+|[0-9]{1,3}(\.[0-9]{3})+|[0-9]{1,3}(,[0-9]{3})+)$/.test(text)) return null;
    const amount = Number(text.replace(/[.,]/g, ""));
    return Number.isSafeInteger(amount) ? String(amount) : null;
  }

  function valid(value) {
    return normalize(value) !== null;
  }

  function render() {
    button.setAttribute("aria-pressed", String(enabled));
    button.classList.toggle("btn-primary", enabled);
    button.classList.toggle("btn-secondary", !enabled);
    status.textContent = enabled
      ? "Predeterminado activo. El valor se conserva al actualizar en este navegador."
      : "Activa Predeterminado para conservar este valor en este navegador.";
  }

  try {
    const saved = localStorage.getItem(storageKey);
    if (saved !== null && valid(saved)) {
      input.value = normalize(saved);
      enabled = true;
    }
    render();
  } catch (error) {
    status.textContent = "No se pudo acceder al almacenamiento del navegador.";
  }

  button.addEventListener("click", function () {
    if (!enabled && (!valid(input.value) || !input.reportValidity())) {
      status.textContent = "Introduce un valor por hora válido para guardarlo.";
      return;
    }
    try {
      if (enabled) localStorage.removeItem(storageKey);
      else localStorage.setItem(storageKey, normalize(input.value));
      enabled = !enabled;
      render();
    } catch (error) {
      status.textContent = "No se pudo guardar la preferencia en este navegador.";
    }
  });

  input.addEventListener("input", function () {
    if (!enabled) return;
    if (!valid(input.value) || !input.validity.valid) {
      status.textContent = "Introduce un valor válido. Se conserva el último valor guardado.";
      return;
    }
    try {
      localStorage.setItem(storageKey, normalize(input.value));
      render();
    } catch (error) {
      status.textContent = "No se pudo guardar el nuevo valor en este navegador.";
    }
  });

  input.addEventListener("blur", function () {
    const amount = normalize(input.value);
    if (amount !== null) input.value = amount;
  });

  input.form.addEventListener("submit", function (event) {
    const amount = normalize(input.value);
    if (amount === null) {
      event.preventDefault();
      status.textContent = "Introduce un valor entero válido, como 14634, 14.634 o 14,634.";
      input.focus();
      return;
    }
    input.value = amount;
  });
})();
