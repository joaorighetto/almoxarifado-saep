(function () {
  function getIssueFormElement() {
    return document.getElementById("issue-create-form");
  }

  function getRequestStatusElement() {
    return document.getElementById("form-request-status");
  }

  function getClientValidationAlertElement() {
    return document.getElementById("client-validation-alert");
  }

  function setClientValidationAlert(message) {
    const alertBox = getClientValidationAlertElement();
    if (!alertBox) return;
    if (!message) {
      alertBox.hidden = true;
      alertBox.textContent = "";
      return;
    }
    alertBox.hidden = false;
    alertBox.textContent = message;
  }

  function setRequestStatus(message, isLoading) {
    const status = getRequestStatusElement();
    if (!status) return;
    if (!message) {
      status.hidden = true;
      status.textContent = "";
      status.classList.remove("is-loading");
      return;
    }
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle("is-loading", isLoading === true);
  }

  function markFieldInvalid(field, message) {
    if (!field) return;
    field.classList.add("field-invalid");
    field.setAttribute("aria-invalid", "true");

    const existing = field.parentElement?.querySelector(".field-feedback");
    if (existing) existing.remove();
    if (!message) return;

    const feedback = document.createElement("div");
    feedback.className = "field-feedback";
    feedback.textContent = message;
    field.parentElement?.appendChild(feedback);
  }

  function clearFieldInvalidState(rootNode) {
    const scope = rootNode || document;
    scope.querySelectorAll(".field-invalid").forEach(function (field) {
      field.classList.remove("field-invalid");
      field.removeAttribute("aria-invalid");
    });
    scope.querySelectorAll(".field-feedback").forEach(function (node) {
      node.remove();
    });
  }

  function validateIssueForm() {
    const form = getIssueFormElement();
    if (!form) return true;

    clearFieldInvalidState(form);
    setClientValidationAlert("");
    let valid = true;
    const missingLabels = [];

    const requester = form.querySelector('[name="requested_by_name"]');
    if (requester && !requester.value.trim()) {
      valid = false;
      missingLabels.push("Solicitante");
      markFieldInvalid(requester, "Informe o solicitante.");
    }

    const destination = form.querySelector('[name="destination"]');
    if (destination && !destination.value.trim()) {
      valid = false;
      missingLabels.push("Destino");
      markFieldInvalid(destination, "Informe o destino.");
    }

    const itemForms = form.querySelectorAll(".issue-item-form");
    let validItemCount = 0;
    itemForms.forEach(function (itemForm) {
      const deleteField = itemForm.querySelector('input[type="checkbox"][name$="-DELETE"]');
      if (deleteField?.checked) return;

      const materialId = itemForm.querySelector(".material-id-field");
      const materialDisplay = itemForm.querySelector(".material-display-field");
      const quantity = itemForm.querySelector('input[name$="-quantity"]');

      const hasAnyInput =
        (materialDisplay?.value || "").trim() !== "" ||
        (quantity?.value || "").trim() !== "";
      if (!hasAnyInput) return;

      if (!materialId || !materialId.value) {
        valid = false;
        markFieldInvalid(materialDisplay, "Selecione um material válido da lista.");
      }

      const qty = Number(quantity?.value);
      if (!quantity?.value || Number.isNaN(qty) || qty <= 0) {
        valid = false;
        markFieldInvalid(quantity, "Informe quantidade maior que zero.");
      } else if (materialId?.value) {
        validItemCount += 1;
      }
    });

    if (validItemCount === 0) {
      valid = false;
      missingLabels.push("Itens");
      const firstMaterialField = form.querySelector(".material-display-field");
      if (firstMaterialField) {
        markFieldInvalid(firstMaterialField, "Adicione ao menos um item válido.");
      }
    }

    if (!valid) {
      const uniqueMissing = [...new Set(missingLabels)];
      const missingText = uniqueMissing.length
        ? `Campos obrigatórios: ${uniqueMissing.join(", ")}.`
        : "Preencha os campos obrigatórios para continuar.";
      setClientValidationAlert(missingText);
      setRequestStatus(
        "Existem campos obrigatórios pendentes. Revise os itens destacados.",
        false
      );
      const firstInvalid = form.querySelector(".field-invalid");
      if (firstInvalid && typeof firstInvalid.focus === "function") {
        firstInvalid.focus();
      }
    } else {
      setClientValidationAlert("");
      setRequestStatus("", false);
    }
    return valid;
  }

  function showSearchLoading(displayField) {
    const box = displayField._suggestionsBox || createSuggestionsBox(displayField);
    displayField._suggestionsBox = box;
    box.innerHTML = '<div class="material-suggestions-loading">Buscando materiais...</div>';
    box.hidden = false;
  }

  function getMaterialSearchUrl() {
    const form = document.querySelector("form[data-material-search-url]");
    return form ? form.dataset.materialSearchUrl : "";
  }

  function getFormsetElements() {
    const container = document.getElementById("issue-items-formset");
    if (!container) return null;

    const prefix = container.dataset.formsetPrefix || "items";
    const totalFormsInput = container.querySelector(`#id_${prefix}-TOTAL_FORMS`);
    const itemsList = container.querySelector("#issue-items-list");
    const emptyTemplate = container.querySelector("#issue-item-empty-form-template");

    if (!totalFormsInput || !itemsList || !emptyTemplate) return null;

    return { container, prefix, totalFormsInput, itemsList, emptyTemplate };
  }

  function buildOptionLabel(material) {
    return `${material.sku} - ${material.name}`;
  }

  function getMaterialUnitBadge(displayField) {
    return displayField.closest(".issue-item-form")?.querySelector(".material-unit-badge");
  }

  function setMaterialUnit(displayField, unitValue) {
    const badge = getMaterialUnitBadge(displayField);
    if (!badge) return;
    const unit = (unitValue || "").trim();
    badge.textContent = unit;
    if (unit) {
      badge.dataset.unit = unit;
      badge.classList.remove("is-empty");
    } else {
      delete badge.dataset.unit;
      badge.classList.add("is-empty");
    }
  }

  function applySelectedMaterial(displayField, hiddenField, material) {
    if (!material || !material.id) return;
    const label = material.label || buildOptionLabel(material);
    displayField.value = label;
    hiddenField.value = String(material.id);
    displayField.dataset.selectedMaterialId = String(material.id);
    displayField.dataset.selectedLabel = label;
    displayField.dataset.selectedUnit = material.unit || "";
    setMaterialUnit(displayField, material.unit || "");
    window.clearTimeout(displayField._searchDebounce);
  }

  function createSuggestionsBox(displayField) {
    const box = document.createElement("div");
    box.className = "material-suggestions";
    box.hidden = true;
    displayField.insertAdjacentElement("afterend", box);
    return box;
  }

  function hideSuggestions(displayField) {
    if (!displayField._suggestionsBox) return;
    displayField._suggestionsBox.hidden = true;
    displayField._suggestionsBox.innerHTML = "";
  }

  function renderSuggestions(displayField, materials, options) {
    const { append, hasMore, materialSearchUrl, query } = options;
    const box = displayField._suggestionsBox || createSuggestionsBox(displayField);
    displayField._suggestionsBox = box;
    if (!append) {
      displayField._materialsByLabel = new Map();
      box.innerHTML = "";
    }

    let list = box.querySelector(".material-suggestions-list");
    if (!list) {
      list = document.createElement("ul");
      list.className = "material-suggestions-list";
      box.appendChild(list);
    }

    if (!append && !materials.length) {
      box.hidden = true;
      return;
    }

    materials.forEach(function (material) {
      const label = material.label || buildOptionLabel(material);
      displayField._materialsByLabel.set(label, material);

      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "material-suggestion-item";
      button.textContent = label;
      button.addEventListener("mousedown", function (event) {
        event.preventDefault();
        const hiddenField = displayField
          .closest(".issue-item-form")
          ?.querySelector(".material-id-field");
        if (!hiddenField) return;
        applySelectedMaterial(displayField, hiddenField, material);
        hideSuggestions(displayField);
        ensureOneEmptyItemForm(materialSearchUrl);
      });

      li.appendChild(button);
      list.appendChild(li);
    });

    const oldMore = box.querySelector(".material-suggestions-more");
    if (oldMore) oldMore.remove();

    if (hasMore) {
      const moreWrap = document.createElement("div");
      moreWrap.className = "material-suggestions-more";
      const moreBtn = document.createElement("button");
      moreBtn.type = "button";
      moreBtn.className = "material-suggestion-more-btn";
      moreBtn.textContent = "Mostrar mais";
      moreBtn.addEventListener("mousedown", function (event) {
        event.preventDefault();
        fetchMaterialOptions(displayField, materialSearchUrl, {
          append: true,
          query,
          offset: displayField._searchOffset || 0,
        });
      });
      moreWrap.appendChild(moreBtn);
      box.appendChild(moreWrap);
    }

    box.hidden = false;
  }

  function fetchMaterialOptions(displayField, materialSearchUrl, options) {
    const fetchOptions = options || {};
    const append = fetchOptions.append === true;
    const query = (fetchOptions.query ?? displayField.value).trim();
    const offset = Number.isInteger(fetchOptions.offset)
      ? fetchOptions.offset
      : append
        ? displayField._searchOffset || 0
        : 0;

    window.clearTimeout(displayField._searchDebounce);
    displayField._searchDebounce = window.setTimeout(async function () {
      const selectedLabel = (displayField.dataset.selectedLabel || "").trim();
      if (!append && displayField.dataset.selectedMaterialId && query === selectedLabel) {
        hideSuggestions(displayField);
        return;
      }

      if (query.length < 2) {
        displayField._materialsByLabel = new Map();
        displayField._searchOffset = 0;
        displayField._lastQuery = "";
        hideSuggestions(displayField);
        return;
      }

      if (!materialSearchUrl) return;
      showSearchLoading(displayField);

      const url = new URL(materialSearchUrl, window.location.origin);
      url.searchParams.set("q", query);
      url.searchParams.set("offset", String(offset));
      url.searchParams.set("limit", "20");

      const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!response.ok) {
        hideSuggestions(displayField);
        return;
      }

      const payload = await response.json();
      const materials = payload.results || [];
      const hasMore = Boolean(payload.has_more);

      // Ignore stale responses from old query values.
      if (!append && displayField.value.trim() !== query) return;
      if (
        !append &&
        displayField.dataset.selectedMaterialId &&
        displayField.value.trim() === (displayField.dataset.selectedLabel || "").trim()
      ) {
        hideSuggestions(displayField);
        return;
      }

      displayField._searchOffset = offset + materials.length;
      displayField._lastQuery = query;
      renderSuggestions(displayField, materials, {
        append,
        hasMore,
        materialSearchUrl,
        query,
      });
    }, append ? 0 : 450);
  }

  function setupMaterialAutocomplete(rootNode, materialSearchUrl) {
    const scope = rootNode || document;
    scope.querySelectorAll(".material-display-field").forEach(function (displayField) {
      if (displayField.dataset.autocompleteReady === "true") return;

      const hiddenField = displayField.closest(".issue-item-form")?.querySelector(".material-id-field");
      if (!hiddenField) return;

      displayField.removeAttribute("list");
      displayField._materialsByLabel = new Map();
      displayField._searchOffset = 0;
      displayField._lastQuery = "";
      displayField.dataset.autocompleteReady = "true";
      displayField._suggestionsBox = createSuggestionsBox(displayField);

      displayField.addEventListener("input", function () {
        const typedValue = displayField.value.trim();
        const selectedLabel = (displayField.dataset.selectedLabel || "").trim();
        if (hiddenField.value && typedValue === selectedLabel) {
          return;
        }
        hiddenField.value = "";
        delete displayField.dataset.selectedMaterialId;
        delete displayField.dataset.selectedLabel;
        delete displayField.dataset.selectedUnit;
        setMaterialUnit(displayField, "");
        fetchMaterialOptions(displayField, materialSearchUrl, { append: false });
      });

      displayField.addEventListener("change", function () {
        const selectedMaterial = displayField._materialsByLabel.get(displayField.value);
        if (selectedMaterial?.id) {
          applySelectedMaterial(displayField, hiddenField, selectedMaterial);
          hideSuggestions(displayField);
          ensureOneEmptyItemForm(materialSearchUrl);
        } else {
          hiddenField.value = "";
          delete displayField.dataset.selectedMaterialId;
          delete displayField.dataset.selectedLabel;
          delete displayField.dataset.selectedUnit;
          setMaterialUnit(displayField, "");
        }
      });

      displayField.addEventListener("focus", function () {
        if (hiddenField.value && displayField.value.trim() === (displayField.dataset.selectedLabel || "").trim()) {
          hideSuggestions(displayField);
          return;
        }
        if (displayField.value.trim().length >= 2) {
          fetchMaterialOptions(displayField, materialSearchUrl, { append: false });
        }
      });

      displayField.addEventListener("blur", function () {
        window.setTimeout(function () {
          hideSuggestions(displayField);
        }, 120);
      });

      if (displayField.value.trim()) {
        const selectedId = hiddenField.value?.trim();
        if (selectedId) {
          displayField.dataset.selectedMaterialId = selectedId;
          displayField.dataset.selectedLabel = displayField.value.trim();
          const currentUnit = getMaterialUnitBadge(displayField)?.dataset.unit || "";
          displayField.dataset.selectedUnit = currentUnit;
          setMaterialUnit(displayField, currentUnit);
        } else {
          fetchMaterialOptions(displayField, materialSearchUrl, { append: false });
        }
      }
    });
  }

  function createNewItemForm(elements, materialSearchUrl) {
    const nextFormIndex = Number(elements.totalFormsInput.value);
    const templateHtml = elements.emptyTemplate.innerHTML.replaceAll("__prefix__", String(nextFormIndex));
    elements.itemsList.insertAdjacentHTML("beforeend", templateHtml);
    elements.totalFormsInput.value = String(nextFormIndex + 1);

    const insertedForm = elements.itemsList.lastElementChild;
    setupMaterialAutocomplete(insertedForm, materialSearchUrl);
  }

  function hasTrailingEmptyForm(elements) {
    const forms = elements.itemsList.querySelectorAll(".issue-item-form");
    if (!forms.length) return false;

    const lastForm = forms[forms.length - 1];
    const materialField = lastForm.querySelector(".material-id-field");

    return materialField && materialField.value === "";
  }

  function ensureOneEmptyItemForm(materialSearchUrl) {
    const elements = getFormsetElements();
    if (!elements) return;

    if (!hasTrailingEmptyForm(elements)) {
      createNewItemForm(elements, materialSearchUrl);
    }
  }

  function initIssueForm() {
    const materialSearchUrl = getMaterialSearchUrl();
    const form = getIssueFormElement();

    if (form && form.dataset.validationHooked !== "true") {
      form.dataset.validationHooked = "true";
      form.addEventListener("submit", function (event) {
        if (!validateIssueForm()) {
          event.preventDefault();
          return;
        }
        form.classList.add("is-submitting");
        setRequestStatus("Salvando saída, aguarde...", true);
      });
    }

    setupMaterialAutocomplete(document, materialSearchUrl);
    ensureOneEmptyItemForm(materialSearchUrl);

    document.addEventListener("click", function (event) {
      document.querySelectorAll(".material-display-field").forEach(function (displayField) {
        const box = displayField._suggestionsBox;
        if (!box || box.hidden) return;
        if (displayField.contains(event.target) || box.contains(event.target)) return;
        hideSuggestions(displayField);
      });
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
      if (event.target.id === "issue-form-inner") {
        clearFieldInvalidState(event.target);
        setClientValidationAlert("");
        setupMaterialAutocomplete(event.target, materialSearchUrl);
        ensureOneEmptyItemForm(materialSearchUrl);
        const formTarget = getIssueFormElement();
        if (formTarget) formTarget.classList.remove("is-submitting");
        if (event.target.querySelector(".success-box")) {
          setRequestStatus("Saída registrada com sucesso.", false);
        } else if (event.target.querySelector(".errorlist")) {
          setRequestStatus("Não foi possível salvar. Revise os campos destacados.", false);
        } else {
          setRequestStatus("", false);
        }
      }
    });

    document.body.addEventListener("htmx:beforeRequest", function (event) {
      const formTarget = getIssueFormElement();
      if (!formTarget || event.target !== formTarget) return;
      formTarget.classList.add("is-submitting");
      setRequestStatus("Salvando saída, aguarde...", true);
    });

    document.body.addEventListener("htmx:afterRequest", function (event) {
      const formTarget = getIssueFormElement();
      if (!formTarget || event.target !== formTarget) return;
      formTarget.classList.remove("is-submitting");
      if (event.detail.failed) {
        setRequestStatus("Não foi possível salvar. Revise os campos destacados.", false);
        return;
      }
      setRequestStatus("Processando resposta...", true);
    });

    document.body.addEventListener("htmx:responseError", function (event) {
      const formTarget = getIssueFormElement();
      if (!formTarget || event.target !== formTarget) return;
      formTarget.classList.remove("is-submitting");
      setRequestStatus("Erro ao processar a requisição. Tente novamente.", false);
    });
  }

  document.addEventListener("DOMContentLoaded", initIssueForm);
})();
