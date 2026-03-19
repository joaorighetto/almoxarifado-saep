(function () {
  function getFormElement() {
    return document.getElementById("material-request-form");
  }

  function getStatusElement() {
    return document.getElementById("form-request-status");
  }

  function getClientValidationAlertElement() {
    return document.getElementById("client-validation-alert");
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

  function buildPageContext() {
    const form = getFormElement();
    if (!form) return null;

    return {
      form,
      statusElement: getStatusElement(),
      clientValidationAlert: getClientValidationAlertElement(),
      materialSearchUrl: form.dataset.materialSearchUrl || "",
      apiUrl: form.dataset.apiUrl || "/api/solicitacoes-materiais/",
      listUrl: form.dataset.listUrl || "/solicitacoes/minhas/",
      createUrl: form.dataset.createUrl || "/solicitacoes/nova/",
      userDepartment: form.dataset.userDepartment || "",
      formMode: form.dataset.formMode || "create",
      requestId: form.dataset.requestId || "",
      initialRequestData: getInitialRequestData(),
      ownWarehouseRequestField: form.querySelector('[name="is_own_warehouse_request"]'),
      requesterNameField: form.querySelector('[name="requester_name"]'),
      requesterDepartmentField: form.querySelector('[name="requester_department"]'),
      notesField: form.querySelector('[name="notes"]'),
      submitNowField: form.querySelector('[name="submit_now"]'),
      warehouseHelp: document.getElementById("warehouse-request-help"),
    };
  }

  function getFormsetElements() {
    const container = document.getElementById("material-request-items-formset");
    if (!container) return null;

    const prefix = container.dataset.formsetPrefix || "items";
    const totalFormsInput = container.querySelector(`#id_${prefix}-TOTAL_FORMS`);
    const itemsList = container.querySelector("#material-request-items-list");
    const emptyTemplate = container.querySelector("#material-request-item-empty-form-template");

    if (!totalFormsInput || !itemsList || !emptyTemplate) return null;

    return { container, prefix, totalFormsInput, itemsList, emptyTemplate };
  }

  function buildOptionLabel(material) {
    return `${material.sku} - ${material.name}`;
  }

  function getCsrfToken(form) {
    const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return csrfInput ? csrfInput.value : "";
  }

  function createFeedbackController(context) {
    function setClientValidationAlert(message) {
      if (!context.clientValidationAlert) return;
      if (!message) {
        context.clientValidationAlert.hidden = true;
        context.clientValidationAlert.textContent = "";
        return;
      }
      context.clientValidationAlert.hidden = false;
      context.clientValidationAlert.textContent = message;
    }

    function setRequestStatus(message, isLoading) {
      if (!context.statusElement) return;
      if (!message) {
        context.statusElement.hidden = true;
        context.statusElement.textContent = "";
        context.statusElement.classList.remove("is-loading");
        return;
      }
      context.statusElement.hidden = false;
      context.statusElement.textContent = message;
      context.statusElement.classList.toggle("is-loading", isLoading === true);
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

    return {
      clearFieldInvalidState,
      markFieldInvalid,
      setClientValidationAlert,
      setRequestStatus,
    };
  }

  function createAutocompleteController(materialSearchUrl, itemsController) {
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
      badge.classList.toggle("is-empty", !unit);
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
      displayField.value = buildOptionLabel(material);
      hiddenField.value = String(material.id);
      setMaterialUnit(displayField, material.unit || "");
      setMaterialStockHint(
        displayField,
        material.available_quantity || "",
        material.unit || "",
      );
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

    function scheduleMaterialFetch(displayField, options) {
      window.clearTimeout(displayField._searchDebounce);
      displayField._searchDebounce = window.setTimeout(function () {
        fetchMaterialOptions(displayField, options);
      }, 300);
    }

    async function fetchMaterialOptions(displayField, options) {
      const append = options?.append === true;
      const query = (options?.query ?? displayField.value).trim();
      const offset = Number.isInteger(options?.offset)
        ? options.offset
        : append
          ? displayField._searchOffset || 0
          : 0;

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
        if (displayField._searchController === controller) {
          displayField._searchController = null;
        }
        return;
      }

      if (displayField._searchController === controller) {
        displayField._searchController = null;
      }

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
          const hiddenField = displayField
            .closest(".issue-item-form")
            ?.querySelector(".material-id-field");
          if (!hiddenField) return;
          applySelectedMaterial(displayField, hiddenField, material);
          hideSuggestions(displayField);
          itemsController.ensureOneEmptyItemForm();
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
          fetchMaterialOptions(displayField, {
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

    function setupMaterialAutocomplete(rootNode) {
      const scope = rootNode || document;
      scope.querySelectorAll(".material-display-field").forEach(function (displayField) {
        if (displayField.dataset.autocompleteReady === "true") return;

        const hiddenField = displayField
          .closest(".issue-item-form")
          ?.querySelector(".material-id-field");
        if (!hiddenField) return;

        displayField.dataset.autocompleteReady = "true";
        displayField._materialsByLabel = new Map();
        displayField._searchOffset = 0;
        displayField._suggestionsBox = createSuggestionsBox(displayField);

        displayField.addEventListener("input", function () {
          hiddenField.value = "";
          setMaterialUnit(displayField, "");
          setMaterialStockHint(displayField, "", "");
          scheduleMaterialFetch(displayField, { append: false });
        });

        displayField.addEventListener("change", function () {
          const selectedMaterial = displayField._materialsByLabel.get(displayField.value);
          if (!selectedMaterial?.id) return;
          applySelectedMaterial(displayField, hiddenField, selectedMaterial);
          hideSuggestions(displayField);
          itemsController.ensureOneEmptyItemForm();
        });

        displayField.addEventListener("blur", function () {
          window.setTimeout(function () {
            hideSuggestions(displayField);
          }, 120);
        });
      });
    }

    function hideSuggestionsOnOutsideClick(event) {
      document.querySelectorAll(".material-display-field").forEach(function (displayField) {
        const box = displayField._suggestionsBox;
        if (!box || box.hidden) return;
        if (displayField.contains(event.target) || box.contains(event.target)) return;
        hideSuggestions(displayField);
      });
    }

    return {
      applySelectedMaterial,
      hideSuggestionsOnOutsideClick,
      setupMaterialAutocomplete,
    };
  }

  function createItemsController(formsetElements) {
    let autocompleteController = null;

    function setAutocompleteController(controller) {
      autocompleteController = controller;
    }

    function createNewItemForm() {
      const nextFormIndex = Number(formsetElements.totalFormsInput.value);
      const templateHtml = formsetElements.emptyTemplate.innerHTML.replaceAll(
        "__prefix__",
        String(nextFormIndex),
      );
      formsetElements.itemsList.insertAdjacentHTML("beforeend", templateHtml);
      formsetElements.totalFormsInput.value = String(nextFormIndex + 1);
      autocompleteController?.setupMaterialAutocomplete(
        formsetElements.itemsList.lastElementChild,
      );
    }

    function resetItemsList() {
      formsetElements.itemsList.innerHTML = "";
      formsetElements.totalFormsInput.value = "0";
    }

    function addExistingItemForm(item) {
      createNewItemForm();

      const itemForm = formsetElements.itemsList.lastElementChild;
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
        autocompleteController?.applySelectedMaterial(displayField, hiddenField, material);
      }
      if (quantityField) quantityField.value = item.requested_quantity || "";
      if (notesField) notesField.value = item.notes || "";
    }

    function hasTrailingEmptyForm() {
      const forms = formsetElements.itemsList.querySelectorAll(".issue-item-form");
      if (!forms.length) return false;
      const lastForm = forms[forms.length - 1];
      const materialField = lastForm.querySelector(".material-id-field");
      return materialField && materialField.value === "";
    }

    function ensureOneEmptyItemForm() {
      if (!hasTrailingEmptyForm()) createNewItemForm();
    }

    function collectItems() {
      const items = [];
      formsetElements.itemsList.querySelectorAll(".issue-item-form").forEach(function (itemForm) {
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

    function getItemForms() {
      return formsetElements.itemsList.querySelectorAll(".issue-item-form");
    }

    return {
      addExistingItemForm,
      collectItems,
      createNewItemForm,
      ensureOneEmptyItemForm,
      getItemForms,
      resetItemsList,
      setAutocompleteController,
    };
  }

  function createWarehouseRequestController(context) {
    function setWarehouseTargetFieldsHidden(isHidden) {
      context.requesterNameField?.closest(".form-field")?.toggleAttribute("hidden", isHidden);
      context.requesterDepartmentField
        ?.closest(".form-field")
        ?.toggleAttribute("hidden", isHidden);
    }

    function sync() {
      if (
        !context.ownWarehouseRequestField ||
        !context.requesterNameField ||
        !context.requesterDepartmentField
      ) {
        return;
      }

      const isOwnRequest = context.ownWarehouseRequestField.checked;
      context.requesterNameField.disabled = isOwnRequest;
      context.requesterDepartmentField.disabled = isOwnRequest;
      setWarehouseTargetFieldsHidden(isOwnRequest);

      if (isOwnRequest) {
        context.requesterNameField.value = "";
        context.requesterDepartmentField.value = "";
      }

      if (context.warehouseHelp) {
        context.warehouseHelp.textContent = isOwnRequest
          ? "Marcada, a solicitação será criada para o próprio almoxarifado e aprovada automaticamente ao enviar."
          : "Desmarque apenas para abrir solicitação em nome de outra seção. Nesse caso, informe solicitante e departamento.";
      }
    }

    function applyPayload(payload) {
      if (context.requesterNameField) {
        context.requesterNameField.value = payload.requester_name || "";
      }
      if (context.requesterDepartmentField) {
        context.requesterDepartmentField.value = payload.requester_department || "";
      }
      if (context.ownWarehouseRequestField && context.requesterDepartmentField) {
        context.ownWarehouseRequestField.checked =
          context.requesterDepartmentField.value.trim() === context.userDepartment;
      }
      sync();
    }

    function isOwnWarehouseRequest() {
      return Boolean(context.ownWarehouseRequestField?.checked);
    }

    function init() {
      if (!context.ownWarehouseRequestField) return;
      context.ownWarehouseRequestField.addEventListener("change", sync);
      sync();
    }

    return {
      applyPayload,
      init,
      isOwnWarehouseRequest,
      sync,
    };
  }

  function createFormValidator(context, itemsController, feedbackController) {
    function validateWarehouseFields() {
      const isOwnWarehouseRequest = Boolean(context.ownWarehouseRequestField?.checked);
      const hasRequesterName = Boolean(context.requesterNameField?.value.trim());
      const hasRequesterDepartment = Boolean(context.requesterDepartmentField?.value.trim());

      if (
        !context.requesterNameField ||
        !context.requesterDepartmentField ||
        isOwnWarehouseRequest ||
        hasRequesterName === hasRequesterDepartment
      ) {
        return true;
      }

      if (!hasRequesterName) {
        feedbackController.markFieldInvalid(
          context.requesterNameField,
          "Informe o nome do solicitante.",
        );
      }
      if (!hasRequesterDepartment) {
        feedbackController.markFieldInvalid(
          context.requesterDepartmentField,
          "Informe o departamento da solicitação.",
        );
      }
      return false;
    }

    function validateItems() {
      const materialIds = new Set();
      let valid = true;
      let validItemCount = 0;

      itemsController.getItemForms().forEach(function (itemForm) {
        const materialIdField = itemForm.querySelector(".material-id-field");
        const materialDisplay = itemForm.querySelector(".material-display-field");
        const quantityField = itemForm.querySelector('input[name$="-requested_quantity"]');

        const hasAnyInput =
          (materialDisplay?.value || "").trim() !== "" ||
          (quantityField?.value || "").trim() !== "";
        if (!hasAnyInput) return;

        const materialId = (materialIdField?.value || "").trim();
        if (!materialId) {
          valid = false;
          feedbackController.markFieldInvalid(
            materialDisplay,
            "Selecione um material válido da lista.",
          );
        } else if (materialIds.has(materialId)) {
          valid = false;
          feedbackController.markFieldInvalid(
            materialDisplay,
            "Material duplicado na solicitação.",
          );
        } else {
          materialIds.add(materialId);
        }

        const quantity = Number(quantityField?.value);
        if (!quantityField?.value || Number.isNaN(quantity) || quantity <= 0) {
          valid = false;
          feedbackController.markFieldInvalid(
            quantityField,
            "Informe quantidade maior que zero.",
          );
        } else if (materialId) {
          validItemCount += 1;
        }
      });

      if (validItemCount === 0) {
        valid = false;
        feedbackController.markFieldInvalid(
          context.form.querySelector(".material-display-field"),
          "Adicione ao menos um item válido.",
        );
      }

      return valid;
    }

    function validate() {
      feedbackController.clearFieldInvalidState(context.form);
      feedbackController.setClientValidationAlert("");

      const valid = validateWarehouseFields() && validateItems();
      if (valid) return true;

      feedbackController.setClientValidationAlert("Revise os campos destacados.");
      feedbackController.setRequestStatus("Existem inconsistências na solicitação.", false);
      const firstInvalid = context.form.querySelector(".field-invalid");
      if (firstInvalid?.focus) firstInvalid.focus();
      return false;
    }

    return { validate };
  }

  function populateExistingRequest(
    context,
    itemsController,
    warehouseController,
    payload,
  ) {
    if (!payload) return;

    if (context.notesField) context.notesField.value = payload.notes || "";
    warehouseController.applyPayload(payload);

    itemsController.resetItemsList();
    (payload.items || []).forEach(function (item) {
      itemsController.addExistingItemForm(item);
    });
    itemsController.ensureOneEmptyItemForm();
  }

  async function loadExistingRequest(
    context,
    itemsController,
    warehouseController,
    feedbackController,
  ) {
    if (!context.requestId) return;

    if (context.initialRequestData) {
      populateExistingRequest(
        context,
        itemsController,
        warehouseController,
        context.initialRequestData,
      );
      return;
    }

    feedbackController.setRequestStatus("Carregando rascunho...", true);
    try {
      const response = await fetch(`${context.apiUrl}${context.requestId}/`, {
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      if (!response.ok) {
        feedbackController.setRequestStatus("Não foi possível carregar o rascunho.", false);
        return;
      }

      const payload = await response.json();
      populateExistingRequest(context, itemsController, warehouseController, payload);
      feedbackController.setRequestStatus("", false);
    } catch (_error) {
      feedbackController.setRequestStatus("Não foi possível carregar o rascunho.", false);
    }
  }

  function buildRequestPayload(context, itemsController, warehouseController) {
    const payload = {
      notes: (context.notesField?.value || "").trim(),
      items: itemsController.collectItems(),
    };

    const requesterName = (context.requesterNameField?.value || "").trim();
    const requesterDepartment = (context.requesterDepartmentField?.value || "").trim();

    if (!warehouseController.isOwnWarehouseRequest() && requesterName) {
      payload.requester_name = requesterName;
    }
    if (!warehouseController.isOwnWarehouseRequest() && requesterDepartment) {
      payload.requester_department = requesterDepartment;
    }

    return payload;
  }

  function getErrorMessage(errors, fallbackMessage) {
    if (Array.isArray(errors?.items)) return errors.items.join(" ");
    if (Array.isArray(errors?.non_field_errors)) return errors.non_field_errors.join(" ");
    return fallbackMessage;
  }

  function renderSuccess(context, materialRequestId, wasSubmitted, finalStatus, feedbackController) {
    const summary = wasSubmitted
      ? finalStatus === "approved"
        ? `Solicitação ${materialRequestId} enviada e aprovada automaticamente.`
        : `Solicitação ${materialRequestId} enviada para aprovação.`
      : `Solicitação ${materialRequestId} salva como rascunho.`;

    context.form.innerHTML = `
      <div class="success-box">
        <strong>${summary}</strong>
        <div class="success-links">
          <a href="${context.listUrl}">Ver minhas solicitações</a>
          <span>-</span>
          <a href="${context.createUrl}">Criar nova solicitação</a>
        </div>
      </div>
    `;
    feedbackController.setRequestStatus("Solicitação processada com sucesso.", false);
  }

  function createSubmitController(
    context,
    itemsController,
    warehouseController,
    feedbackController,
    validator,
  ) {
    function buildRequestUrl() {
      const isEditMode = context.formMode === "edit" && Boolean(context.requestId);
      return {
        method: isEditMode ? "PATCH" : "POST",
        url: isEditMode ? `${context.apiUrl}${context.requestId}/` : context.apiUrl,
      };
    }

    async function saveRequest(payload) {
      const requestConfig = buildRequestUrl();
      const response = await fetch(requestConfig.url, {
        method: requestConfig.method,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": getCsrfToken(context.form),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) return { ok: true, data: await response.json() };

      const errors = await response.json().catch(function () {
        return {};
      });
      return { ok: false, errors };
    }

    async function submitForApproval(materialRequestId) {
      const response = await fetch(`${context.apiUrl}${materialRequestId}/submit/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-CSRFToken": getCsrfToken(context.form),
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      if (response.ok) return { ok: true, data: await response.json() };

      const errors = await response.json().catch(function () {
        return {};
      });
      return { ok: false, errors };
    }

    async function handleSubmit(event) {
      event.preventDefault();
      if (!validator.validate()) return;

      const payload = buildRequestPayload(context, itemsController, warehouseController);
      const shouldSubmitNow = Boolean(context.submitNowField?.checked);

      context.form.classList.add("is-submitting");
      feedbackController.setRequestStatus("Salvando solicitação, aguarde...", true);
      feedbackController.setClientValidationAlert("");
      feedbackController.clearFieldInvalidState(context.form);

      try {
        const saveResult = await saveRequest(payload);
        if (!saveResult.ok) {
          feedbackController.setClientValidationAlert(
            getErrorMessage(saveResult.errors, "Não foi possível salvar a solicitação."),
          );
          feedbackController.setRequestStatus("Não foi possível salvar. Revise os dados.", false);
          return;
        }

        const created = saveResult.data;
        let finalStatus = created.status;

        if (shouldSubmitNow) {
          feedbackController.setRequestStatus("Enviando para aprovação...", true);
          const submitResult = await submitForApproval(created.id);
          if (!submitResult.ok) {
            feedbackController.setClientValidationAlert(
              getErrorMessage(
                submitResult.errors,
                "Solicitação salva, mas não foi possível enviar para aprovação.",
              ),
            );
            feedbackController.setRequestStatus("Solicitação salva em rascunho.", false);
            return;
          }
          finalStatus = submitResult.data.status || finalStatus;
        }

        renderSuccess(
          context,
          created.id,
          shouldSubmitNow,
          finalStatus,
          feedbackController,
        );
      } catch (_error) {
        feedbackController.setRequestStatus("Erro ao processar a requisição. Tente novamente.", false);
      } finally {
        context.form.classList.remove("is-submitting");
      }
    }

    return { handleSubmit };
  }

  async function initMaterialRequestForm() {
    const context = buildPageContext();
    if (!context) return;

    const formsetElements = getFormsetElements();
    if (!formsetElements) return;

    const feedbackController = createFeedbackController(context);
    const itemsController = createItemsController(formsetElements);
    const autocompleteController = createAutocompleteController(
      context.materialSearchUrl,
      itemsController,
    );
    itemsController.setAutocompleteController(autocompleteController);

    const warehouseController = createWarehouseRequestController(context);
    const validator = createFormValidator(context, itemsController, feedbackController);
    const submitController = createSubmitController(
      context,
      itemsController,
      warehouseController,
      feedbackController,
      validator,
    );

    context.form.addEventListener("submit", submitController.handleSubmit);
    autocompleteController.setupMaterialAutocomplete(document);
    warehouseController.init();

    if (context.formMode === "edit" && context.requestId) {
      await loadExistingRequest(
        context,
        itemsController,
        warehouseController,
        feedbackController,
      );
    } else {
      itemsController.ensureOneEmptyItemForm();
    }

    document.addEventListener("click", autocompleteController.hideSuggestionsOnOutsideClick);
  }

  document.addEventListener("DOMContentLoaded", function () {
    void initMaterialRequestForm();
  });
})();
