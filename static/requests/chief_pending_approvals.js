(function () {
  function setApprovalStatus(message, isLoading) {
    const statusNode = document.getElementById("approval-status");
    if (!statusNode) return;
    if (!message) {
      statusNode.hidden = true;
      statusNode.textContent = "";
      statusNode.classList.remove("is-loading");
      return;
    }
    statusNode.hidden = false;
    statusNode.textContent = message;
    statusNode.classList.toggle("is-loading", isLoading === true);
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

    const tbody = document.querySelector("#chief-pending-table tbody");
    if (!tbody) return;
    if (!tbody.querySelector("tr")) {
      const emptyRow = document.createElement("tr");
      emptyRow.innerHTML =
        '<td colspan="6" class="muted-text">Nenhuma solicitação pendente para sua seção.</td>';
      tbody.appendChild(emptyRow);
    }
  }

  async function postAction(requestId, actionName, bodyData) {
    const url = `/api/solicitacoes-materiais/${requestId}/${actionName}/`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(bodyData || {}),
    });
    if (!response.ok) {
      const payload = await response.json().catch(function () {
        return {};
      });
      throw new Error(
        payload?.detail ||
          payload?.status?.[0] ||
          payload?.reason?.[0] ||
          "Não foi possível processar a solicitação."
      );
    }
    return response.json();
  }

  function initChiefActions() {
    document.querySelectorAll(".js-approve-request").forEach(function (button) {
      button.addEventListener("click", async function () {
        const requestId = button.dataset.requestId;
        if (!requestId) return;
        setApprovalStatus(`Aprovando solicitação #${requestId}...`, true);
        try {
          await postAction(requestId, "approve");
          removeRequestRow(requestId);
          setApprovalStatus(`Solicitação #${requestId} aprovada com sucesso.`, false);
        } catch (error) {
          setApprovalStatus(error.message, false);
        }
      });
    });

    document.querySelectorAll(".js-reject-request").forEach(function (button) {
      button.addEventListener("click", async function () {
        const requestId = button.dataset.requestId;
        if (!requestId) return;

        const reason = window.prompt("Informe o motivo da rejeição:");
        if (reason === null) return;
        if (!reason.trim()) {
          setApprovalStatus("Motivo da rejeição é obrigatório.", false);
          return;
        }

        setApprovalStatus(`Rejeitando solicitação #${requestId}...`, true);
        try {
          await postAction(requestId, "reject", { reason });
          removeRequestRow(requestId);
          setApprovalStatus(`Solicitação #${requestId} rejeitada com sucesso.`, false);
        } catch (error) {
          setApprovalStatus(error.message, false);
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initChiefActions);
})();
