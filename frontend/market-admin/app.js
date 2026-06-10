const state = {
    apiBase: localStorage.getItem("apiBase") || "https://yeshivachill.com",
    token: localStorage.getItem("adminToken") || "",
};

const apiBaseEl = document.getElementById("apiBase");
const adminTokenEl = document.getElementById("adminToken");
const allowOut = document.getElementById("allowOut");
const inviteOut = document.getElementById("inviteOut");
const feedbackOut = document.getElementById("feedbackOut");

apiBaseEl.value = state.apiBase;
adminTokenEl.value = state.token;

document.getElementById("saveConfig").onclick = () => {
    state.apiBase = apiBaseEl.value.trim();
    state.token = adminTokenEl.value.trim();
    localStorage.setItem("apiBase", state.apiBase);
    localStorage.setItem("adminToken", state.token);
};

async function callApi(path, options = {}) {
    const res = await fetch(`${state.apiBase}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            "x-admin-token": state.token,
            ...(options.headers || {}),
        },
    });
    const text = await res.text();
    try {
        return JSON.parse(text);
    } catch {
        return { raw: text };
    }
}

document.getElementById("addAllow").onclick = async () => {
    const phone = document.getElementById("allowPhone").value.trim();
    const label = document.getElementById("allowLabel").value.trim();
    const result = await callApi("/api/market-updates/admin/allowlist", {
        method: "POST",
        body: JSON.stringify({ phone_number: phone, label, enabled: true }),
    });
    allowOut.textContent = JSON.stringify(result, null, 2);
};

document.getElementById("refreshAllow").onclick = async () => {
    const result = await callApi("/api/market-updates/admin/allowlist");
    allowOut.textContent = JSON.stringify(result, null, 2);
};

document.getElementById("refreshInvites").onclick = async () => {
    const result = await callApi("/api/market-updates/admin/invite-requests?status=pending");
    inviteOut.textContent = JSON.stringify(result, null, 2);
};

document.getElementById("refreshFeedback").onclick = async () => {
    const result = await callApi("/api/market-updates/admin/feedback?limit=100");
    feedbackOut.textContent = JSON.stringify(result, null, 2);
};
