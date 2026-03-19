(function () {
  function getFormElement() {
    return document.getElementById("material-request-form");
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

  function getMaterialSearchUrl() {
    const form = getFormElement();
    return form?.dataset.materialSearchUrl || "";
  }

  function getApiUrl() {
    const form = getFormElement();
    return form?.dataset.apiUrl || "/api/solicitacoes-materiais/";
  }

  function getFormMode() {
    const form = getFormElement();
    return form?.dataset.formMode || "create";
  }

  function getRequestId() {
    const form = getFormElement();
    return form?.dataset.requestId || "";
  }

  function getInitialRequestData() {
    const node = document.getElementById("material-request-initial-data");
    if (!node?.textContent) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (_error) {
      return null;
    }
  }

  function getListUrl() {
    const form = getFormElement();
    return form?.dataset.listUrl || "/solicitacoes/minhas/";
  }

  function getCreateUrl() {
    const form = getFormElement();
    return form?.dataset.createUrl || "/solicitacoes/nova/";
  }

  function getUserDepartment() {
    const form = getFormElement();
    return form?.dataset.userDepartment || "";
  }

  function getFormsetElements() {
    const container = document.getElementById("material-request-items-formset");
    if (!container) return null;

    const prefix = container.dataset.formsetPrefix || "items";
    const totalFormsInput = container.querySelector(`#id_${prefix}-TOTAL_FORMS`);
    const itemsList = container.querySelector("#material-request-items-list");
    const emptyTemplate = container.querySelector("#material-request-item-empty-form-template");

    if (!totalFormsInput || !itemsList || !emptyTemplate) return null;
    return { totalFormsInput, itemsList, emptyTemplate };
  }

  function buildOptionLabel(material) {
    return `${material.sku} - ${material.name}`;
  }

  function getMaterialUnitBadge(displayField) {
    return displayField.closest(".issue-item-form")?.querySelector(".material-unit-badge");
  }

  function getMaterialStockHint(displayField) {
    return displayField.closest(".issue-item-form")?.querySelector(".material-stock-hint");
  }

  function setMaterialUnit(displayField, unitValue) {
    const badge = getMaterialUnitBadge(displayField);
    if (!badge) return;
    const unit = (unitValue || "").trim();
    badge.textContent = unit;
    if (unit) {
      badge.classList.remove("is-empty");
    } else {
      badge.classList.add("is-empty");
    }
  }

  function setMaterialStockHint(displayField, quantityValue, unitValue) {
    const hint = getMaterialStockHint(displayField);
    if (!hint) return;
    const quantity = String(quantityValue ?? "").trim();
    const unit = (unitValue || "").trim();
    if (!quantity) {
      hint.hidden = true;
      hint.textContent = "";
      return;
    }
    hint.hidden = false;
    hint.textContent = `Saldo atual: ${quantity}${unit ? ` ${unit}` : ""}`;
  }

  function applySelectedMaterial(displayField, hiddenField, material) {
    if (!material || !material.id) return;
    const label = buildOptionLabel(material);
    displayField.value = label;
    hiddenField.value = String(material.id);
    setMaterialUnit(displayField, material.unit || "");
    setMaterialStockHint(displayField, material.available_quantity || "", material.unit || "");
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

  function scheduleMaterialFetch(displayField, materialSearchUrl, options) {
    window.clearTimeout(displayField._searchDebounce);
    displayField._searchDebounce = window.setTimeout(function () {
      fetchMaterialOptions(displayField, materialSearchUrl, options);
    }, 300);
  }

  async function fetchMaterialOptions(displayField, materialSearchUrl, options) {
    const append = options?.append === true;
    const query = (options?.query ?? displayField.value).trim();
    const offset = Number.isInteger(options?.offset) ? options.offset : append ? displayField._searchOffset || 0 : 0;

    if (query.length < 2 || !materialSearchUrl) {
      hideSuggestions(displayField);
      return;
    }

    const url = new URL(materialSearchUrl, window.location.origin);
    url.searchParams.set("q", query);
    url.searchParams.set("offset", String(offset));
    url.searchParams.set("limit", "20");

    if (displayField._searchController) {
      displayField._searchController.abort();
    }
    const controller = new AbortController();
    displayField._searchController = controller;

    let response;
    try {
      response = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        signal: controller.signal,
      });
    } catch (_error) {
      if (displayField._searchController === controller) displayField._searchController = null;
      return;
    }
    if (displayField._searchController === controller) displayField._searchController = null;

    if (!response.ok) {
      hideSuggestions(displayField);
      return;
    }

    const payload = await response.json();
    const materials = payload.results || [];
    const hasMore = Boolean(payload.has_more);

    const box = displayField._suggestionsBox || createSuggestionsBox(displayField);
    displayField._suggestionsBox = box;
    if (!append) {
      displayField._materialsByLabel = new Map();
      box.innerHTML = "";
    }
    if (!append && !materials.length) {
      hideSuggestions(displayField);
      return;
    }

    let list = box.querySelector(".material-suggestions-list");
    if (!list) {
      list = document.createElement("ul");
      list.className = "material-suggestions-list";
      box.appendChild(list);
    }

    materials.forEach(function (material) {
      const label = buildOptionLabel(material);
      displayField._materialsByLabel.set(label, material);

      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "material-suggestion-item";
      button.textContent = label;
      button.addEventListener("mousedown", function (event) {
        event.preventDefault();
        const hiddenField = displayField.closest(".issue-item-form")?.querySelector(".material-id-field");
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
          offset: (displayField._searchOffset || 0) + materials.length,
        });
      });
      moreWrap.appendChild(moreBtn);
      box.appendChild(moreWrap);
    }

    displayField._searchOffset = offset + materials.length;
    box.hidden = false;
  }

  function setupMaterialAutocomplete(rootNode, materialSearchUrl) {
    const scope = rootNode || document;
    scope.querySelectorAll(".material-display-field").forEach(function (displayField) {
      if (displayField.dataset.autocompleteReady === "true") return;

      const hiddenField = displayField.closest(".issue-item-form")?.querySelector(".material-id-field");
      if (!hiddenField) return;

      displayField.dataset.autocompleteReady = "true";
      displayField._materialsByLabel = new Map();
      displayField._searchOffset = 0;
      displayField._suggestionsBox = createSuggestionsBox(displayField);

      displayField.addEventListener("input", function () {
        hiddenField.value = "";
        setMaterialUnit(displayField, "");
        setMaterialStockHint(displayField, "", "");
        scheduleMaterialFetch(displayField, materialSearchUrl, { append: false });
      });

      displayField.addEventListener("change", function () {
        const selectedMaterial = displayField._materialsByLabel.get(displayField.value);
        if (selectedMaterial?.id) {
          applySelectedMaterial(displayField, hiddenField, selectedMaterial);
          hideSuggestions(displayField);
          ensureOneEmptyItemForm(materialSearchUrl);
        }
      });

      displayField.addEventListener("blur", function () {
        window.setTimeout(function () {
          hideSuggestions(displayField);
        }, 120);
      });
    });
  }

  function createNewItemForm(elements, materialSearchUrl) {
    const nextFormIndex = Number(elements.totalFormsInput.value);
    const templateHtml = elements.emptyTemplate.innerHTML.replaceAll("__prefix__", String(nextFormIndex));
    elements.itemsList.insertAdjacentHTML("beforeend", templateHtml);
    elements.totalFormsInput.value = String(nextFormIndex + 1);
    setupMaterialAutocomplete(elements.itemsList.lastElementChild, materialSearchUrl);
  }

  function resetItemsList(elements) {
    elements.itemsList.innerHTML = "";
    elements.totalFormsInput.value = "0";
  }

  function addExistingItemForm(elements, materialSearchUrl, item) {
    createNewItemForm(elements, materialSearchUrl);
    const itemForm = elements.itemsList.lastElementChild;
    const hiddenField = itemForm.querySelector(".material-id-field");
    const displayField = itemForm.querySelector(".material-display-field");
    const quantityField = itemForm.querySelector('input[name$="-requested_quantity"]');
    const notesField = itemForm.querySelector('input[name$="-notes"], textarea[name$="-notes"]');
    const material = {
      id: item.material,
      sku: item.material_sku,
      name: item.material_name,
      unit: item.unit,
      available_quantity: item.available_quantity || "",
    };

    if (displayField) {
      displayField._materialsByLabel = displayField._materialsByLabel || new Map();
      displayField._materialsByLabel.set(buildOptionLabel(material), material);
      applySelectedMaterial(displayField, hiddenField, material);
    }
    if (quantityField) quantityField.value = item.requested_quantity || "";
    if (notesField) notesField.value = item.notes || "";
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
    if (!hasTrailingEmptyForm(elements)) createNewItemForm(elements, materialSearchUrl);
  }

  function validateForm() {
    const form = getFormElement();
    if (!form) return true;
    clearFieldInvalidState(form);
    setClientValidationAlert("");
    let valid = true;

    const ownWarehouseRequestField = form.querySelector('[name="is_own_warehouse_request"]');
    const requesterNameField = form.querySelector('[name="requester_name"]');
    const requesterDepartmentField = form.querySelector('[name="requester_department"]');
    const isOwnWarehouseRequest = Boolean(ownWarehouseRequestField?.checked);
    const hasRequesterName = Boolean(requesterNameField?.value.trim());
    const hasRequesterDepartment = Boolean(requesterDepartmentField?.value.trim());
    if (
      requesterNameField &&
      requesterDepartmentField &&
      !isOwnWarehouseRequest &&
      hasRequesterName !== hasRequesterDepartment
    ) {
      valid = false;
      if (!hasRequesterName) {
        markFieldInvalid(requesterNameField, "Informe o nome do solicitante.");
      }
      if (!hasRequesterDepartment) {
        markFieldInvalid(requesterDepartmentField, "Informe o departamento da solicitação.");
      }
    }

    const itemForms = form.querySelectorAll(".issue-item-form");
    const materialIds = new Set();
    let validItemCount = 0;
    itemForms.forEach(function (itemForm) {
      const materialIdField = itemForm.querySelector(".material-id-field");
      const materialDisplay = itemForm.querySelector(".material-display-field");
      const quantityField = itemForm.querySelector('input[name$="-requested_quantity"]');

      const hasAnyInput = (materialDisplay?.value || "").trim() !== "" || (quantityField?.value || "").trim() !== "";
      if (!hasAnyInput) return;

      const materialId = (materialIdField?.value || "").trim();
      if (!materialId) {
        valid = false;
        markFieldInvalid(materialDisplay, "Selecione um material válido da lista.");
      } else if (materialIds.has(materialId)) {
        valid = false;
        markFieldInvalid(materialDisplay, "Material duplicado na solicitação.");
      } else {
        materialIds.add(materialId);
      }

      const quantity = Number(quantityField?.value);
      if (!quantityField?.value || Number.isNaN(quantity) || quantity <= 0) {
        valid = false;
        markFieldInvalid(quantityField, "Informe quantidade maior que zero.");
      } else if (materialId) {
        validItemCount += 1;
      }
    });

    if (validItemCount === 0) {
      valid = false;
      markFieldInvalid(form.querySelector(".material-display-field"), "Adicione ao menos um item válido.");
    }

    if (!valid) {
      setClientValidationAlert("Revise os campos destacados.");
      setRequestStatus("Existem inconsistências na solicitação.", false);
      const firstInvalid = form.querySelector(".field-invalid");
      if (firstInvalid?.focus) firstInvalid.focus();
    }
    return valid;
  }

  function collectItems(form) {
    const items = [];
    form.querySelectorAll(".issue-item-form").forEach(function (itemForm) {
      const materialField = itemForm.querySelector(".material-id-field");
      const quantityField = itemForm.querySelector('input[name$="-requested_quantity"]');
      const notesField = itemForm.querySelector('input[name$="-notes"], textarea[name$="-notes"]');

      const materialId = (materialField?.value || "").trim();
      const requestedQuantity = (quantityField?.value || "").trim();
      const notes = (notesField?.value || "").trim();

      if (!materialId || !requestedQuantity || Number(requestedQuantity) <= 0) return;
      items.push({ material: Number(materialId), requested_quantity: requestedQuantity, notes });
    });
    return items;
  }

  function getCsrfToken(form) {
    const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return csrfInput ? csrfInput.value : "";
  }

  function populateExistingRequest(payload, materialSearchUrl) {
    const form = getFormElement();
    const elements = getFormsetElements();
    if (!form || !elements || !payload) return;

    const notesField = form.querySelector('[name="notes"]');
    const requesterNameField = form.querySelector('[name="requester_name"]');
    const requesterDepartmentField = form.querySelector('[name="requester_department"]');
    const ownWarehouseRequestField = form.querySelector('[name="is_own_warehouse_request"]');

    if (notesField) notesField.value = payload.notes || "";
    if (requesterNameField) requesterNameField.value = payload.requester_name || "";
    if (requesterDepartmentField) requesterDepartmentField.value = payload.requester_department || "";
    if (ownWarehouseRequestField && requesterDepartmentField) {
      ownWarehouseRequestField.checked = requesterDepartmentField.value.trim() === getUserDepartment();
    }

    resetItemsList(elements);
    (payload.items || []).forEach(function (item) {
      addExistingItemForm(elements, materialSearchUrl, item);
    });
    ensureOneEmptyItemForm(materialSearchUrl);
    form.dispatchEvent(new CustomEvent("material-request:loaded"));
  }

  async function loadExistingRequest(materialSearchUrl) {
    const requestId = getRequestId();
    if (!requestId) return;

    const initialData = getInitialRequestData();
    if (initialData) {
      populateExistingRequest(initialData, materialSearchUrl);
      return;
    }

    setRequestStatus("Carregando rascunho...", true);
    try {
      const response = await fetch(`${getApiUrl()}${requestId}/`, {
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      if (!response.ok) {
        setRequestStatus("Não foi possível carregar o rascunho.", false);
        return;
      }

      const payload = await response.json();
      populateExistingRequest(payload, materialSearchUrl);
      setRequestStatus("", false);
    } catch (_error) {
      setRequestStatus("Não foi possível carregar o rascunho.", false);
    }
  }

  function renderSuccess(materialRequestId, wasSubmitted, finalStatus) {
    const form = getFormElement();
    if (!form) return;
    const listUrl = getListUrl();
    const summary = wasSubmitted
      ? finalStatus === "approved"
        ? `Solicitação ${materialRequestId} enviada e aprovada automaticamente.`
        : `Solicitação ${materialRequestId} enviada para aprovação.`
      : `Solicitação ${materialRequestId} salva como rascunho.`;
    form.innerHTML = `
      <div class="success-box">
        <strong>${summary}</strong>
        <div class="success-links">
          <a href="${listUrl}">Ver minhas solicitações</a>
          <span>-</span>
          <a href="${getCreateUrl()}">Criar nova solicitação</a>
        </div>
      </div>
    `;
    setRequestStatus("Solicitação processada com sucesso.", false);
  }

  async function submitMaterialRequest(event) {
    const form = getFormElement();
    if (!form) return;
    event.preventDefault();
    if (!validateForm()) return;

    const payload = {
      notes: (form.querySelector('[name="notes"]')?.value || "").trim(),
      items: collectItems(form),
    };
    const requesterName = (form.querySelector('[name="requester_name"]')?.value || "").trim();
    const requesterDepartment = (
      form.querySelector('[name="requester_department"]')?.value || ""
    ).trim();
    const isOwnWarehouseRequest = Boolean(
      form.querySelector('[name="is_own_warehouse_request"]')?.checked
    );
    if (!isOwnWarehouseRequest && requesterName) payload.requester_name = requesterName;
    if (!isOwnWarehouseRequest && requesterDepartment) payload.requester_department = requesterDepartment;
    const shouldSubmitNow = Boolean(form.querySelector('[name="submit_now"]')?.checked);
    const requestId = getRequestId();
    const isEditMode = getFormMode() === "edit" && Boolean(requestId);

    form.classList.add("is-submitting");
    setRequestStatus("Salvando solicitação, aguarde...", true);
    setClientValidationAlert("");
    clearFieldInvalidState(form);

    try {
      const response = await fetch(isEditMode ? `${getApiUrl()}${requestId}/` : getApiUrl(), {
        method: isEditMode ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": getCsrfToken(form),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errors = await response.json().catch(function () {
          return {};
        });
        setClientValidationAlert(
          Array.isArray(errors?.non_field_errors)
            ? errors.non_field_errors.join(" ")
            : "Não foi possível salvar a solicitação."
        );
        setRequestStatus("Não foi possível salvar. Revise os dados.", false);
        return;
      }

      const created = await response.json();
      let finalStatus = created.status;
      if (shouldSubmitNow) {
        setRequestStatus("Enviando para aprovação...", true);
        const submitResponse = await fetch(`${getApiUrl()}${created.id}/submit/`, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "X-CSRFToken": getCsrfToken(form),
            "X-Requested-With": "XMLHttpRequest",
          },
        });
        if (!submitResponse.ok) {
          const errors = await submitResponse.json().catch(function () {
            return {};
          });
          setClientValidationAlert(
            Array.isArray(errors?.items)
              ? errors.items.join(" ")
              : "Solicitação salva, mas não foi possível enviar para aprovação."
          );
          setRequestStatus("Solicitação salva em rascunho.", false);
          return;
        }
        const submitted = await submitResponse.json();
        finalStatus = submitted.status || finalStatus;
      }

      renderSuccess(created.id, shouldSubmitNow, finalStatus);
    } catch (_error) {
      setRequestStatus("Erro ao processar a requisição. Tente novamente.", false);
    } finally {
      form.classList.remove("is-submitting");
    }
  }

  function initMaterialRequestForm() {
    const form = getFormElement();
    if (!form) return;
    const materialSearchUrl = getMaterialSearchUrl();
    const ownWarehouseRequestField = form.querySelector('[name="is_own_warehouse_request"]');
    const requesterNameField = form.querySelector('[name="requester_name"]');
    const requesterDepartmentField = form.querySelector('[name="requester_department"]');
    const warehouseHelp = document.getElementById("warehouse-request-help");

    function setWarehouseTargetFieldsHidden(isHidden) {
      requesterNameField.closest(".form-field")?.toggleAttribute("hidden", isHidden);
      requesterDepartmentField.closest(".form-field")?.toggleAttribute("hidden", isHidden);
    }

    function syncWarehouseRequestMode() {
      if (!ownWarehouseRequestField || !requesterNameField || !requesterDepartmentField) return;
      const isOwnRequest = ownWarehouseRequestField.checked;
      requesterNameField.disabled = isOwnRequest;
      requesterDepartmentField.disabled = isOwnRequest;
      setWarehouseTargetFieldsHidden(isOwnRequest);
      if (isOwnRequest) {
        requesterNameField.value = "";
        requesterDepartmentField.value = "";
      }
      if (warehouseHelp) {
        warehouseHelp.textContent = isOwnRequest
          ? "Marcada, a solicitação será criada para o próprio almoxarifado e aprovada automaticamente ao enviar."
          : "Desmarque apenas para abrir solicitação em nome de outra seção. Nesse caso, informe solicitante e departamento.";
      }
    }

    form.addEventListener("submit", submitMaterialRequest);
    setupMaterialAutocomplete(document, materialSearchUrl);
    if (getFormMode() === "edit" && getRequestId()) {
      loadExistingRequest(materialSearchUrl);
    } else {
      ensureOneEmptyItemForm(materialSearchUrl);
    }
    if (ownWarehouseRequestField) {
      ownWarehouseRequestField.addEventListener("change", syncWarehouseRequestMode);
      form.addEventListener("material-request:loaded", syncWarehouseRequestMode);
      syncWarehouseRequestMode();
    }

    document.addEventListener("click", function (event) {
      document.querySelectorAll(".material-display-field").forEach(function (displayField) {
        const box = displayField._suggestionsBox;
        if (!box || box.hidden) return;
        if (displayField.contains(event.target) || box.contains(event.target)) return;
        hideSuggestions(displayField);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initMaterialRequestForm);
})();
