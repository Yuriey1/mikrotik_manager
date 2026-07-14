async function getPendingRequests() {
    try {
        var data = await apiGet('/api/matrix/pending');
        if (data.success) {
            store.pendingRequests = data.requests || [];
            store.pendingCount = data.count || 0;
            store.matrixEnabled = true;
        }
    } catch (e) {
        // Плагин не загружен — тихо пропускаем
    }
}

async function confirmMatrixRequest(pendingId) {
    return apiPost('/api/matrix/confirm', { pending_id: pendingId });
}

async function rejectMatrixRequest(pendingId) {
    return apiPost('/api/matrix/reject', { pending_id: pendingId });
}

// Периодический опрос pending-заявок
var _matrixPollTimer = null;
function startMatrixPoll() {
    getPendingRequests();
    _matrixPollTimer = setInterval(getPendingRequests, 10000);
}
