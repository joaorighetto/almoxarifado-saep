(function () {
  function setWarehouseStatus(message, isLoading) {
    const node = document.getElementById("warehouse-status");
    if (!node) return;
    if (!message) {
      node.hidden = true;
      node.textContent = "";
      node.classList.remove("is-loading");
      return;
    }
    node.hidden = false;
    node.textContent = message;
    node.classList.toggle("is-loading", isLoading === true);
  }

  function getCsrfToken() {
    const csrfCookie = document.cookie
      .split(";")
      .map(function (part) {
        return part.trim();
      })
      .find(function (part) {
        return part.startsWith("csrftoken=");
      });
    return csrfCookie ? decodeURIComponent(csrfCookie.split("=", 2)[1]) : "";
  }

  function removeRequestRow(requestId) {
    const row = document.querySelector(`tr[data-request-id="${requestId}"]`);
    if (!row) return;
    row.remove();

    const tbody = document.querySelector("#warehouse-approved-table tbody");
    if (!tbody) return;
    if (!tbody.querySelector("tr")) {
      const emptyRow = document.createElement("tr");
      emptyRow.innerHTML = '<td colspan="6" class="muted-text">Nenhuma solicitação aprovada pendente.</td>';
      tbody.appendChild(emptyRow);
    }
  }

  async function fulfillRequest(requestId) {
    const response = await fetch(`/api/solicitacoes-materiais/${requestId}/fulfill/`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      const payload = await response.json().catch(function () {
        return {};
      });
      throw new Error(
        payload?.detail ||
          payload?.status?.[0] ||
          payload?.items?.[0] ||
          payload?.non_field_errors?.[0] ||
          "Não foi possível atender a solicitação."
      );
    }
    return response.json();
  }

  function initWarehouseActions() {
    document.querySelectorAll(".js-fulfill-request").forEach(function (button) {
      button.addEventListener("click", async function () {
        const requestId = button.dataset.requestId;
        if (!requestId) return;

        setWarehouseStatus(`Atendendo solicitação #${requestId}...`, true);
        try {
          const result = await fulfillRequest(requestId);
          removeRequestRow(requestId);
          const issueId = result?.issue;
          setWarehouseStatus(
            issueId
              ? `Solicitação #${requestId} atendida. Saída #${issueId} gerada.`
              : `Solicitação #${requestId} atendida com sucesso.`,
            false
          );
        } catch (error) {
          setWarehouseStatus(error.message, false);
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initWarehouseActions);
})();
