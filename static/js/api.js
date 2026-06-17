async function apiFetch(url, options = {}) {
    try {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data.error || `HTTP ${resp.status}`);
        }
        return await resp.json();
    } catch (e) {
        if (e instanceof TypeError && e.message.includes('fetch')) {
            throw new Error('Сервер недоступен');
        }
        throw e;
    }
}

function apiGet(url) {
    return apiFetch(url);
}

function apiPost(url, data) {
    return apiFetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
}

function apiDelete(url) {
    return apiFetch(url, { method: 'DELETE' });
}

async function loadDevices() {
    store.devicesLoading = true;
    try {
        const data = await apiGet('/api/devices');
        store.devices = data.devices || {};
        store.netboxConfigured = data.netbox_configured || false;
    } catch (e) {
        store.error = e.message;
    } finally {
        store.devicesLoading = false;
    }
}

async function connectDevice(name, username, password) {
    store.connecting = true;
    store.connectingDevice = name;
    try {
        const params = new URLSearchParams({ device: name });
        if (username) params.set('username', username);
        if (password) params.set('password', password);
        const data = await apiGet(`/api/connect?${params}`);

        if (data.requires_credentials) {
            store.credentialsDevice = name;
            store.showCredentialsModal = true;
            return null;
        }

        if (data.success) {
            store.connected = true;
            store.currentDevice = name;
            const sync = await apiGet('/api/sync');
            if (sync.success !== false) {
                store.queueTree = sync.queue_tree || [];
                store.allQueues = sync.all_queues || [];
                store.queueStats = sync.queue_stats || {};
                store.dhcpPools = sync.dhcp_pools || [];
                store.subscribers = sync.subscribers || [];
                store.internetAccess = sync.internet_access || [];
                store.channelsInfo = sync.channels || null;
                store.interfaces = sync.interfaces || [];
            }
            return data;
        }
        throw new Error(data.error || 'Ошибка подключения');
    } catch (e) {
        store.error = e.message;
        throw e;
    } finally {
        store.connecting = false;
        store.connectingDevice = null;
    }
}

async function disconnectDevice() {
    try {
        await apiGet('/api/disconnect');
    } catch (e) {
    }
    store.connected = false;
    store.currentDevice = null;
    store.queueTree = [];
    store.allQueues = [];
    store.queueStats = {};
    store.dhcpPools = [];
    store.subscribers = [];
    store.internetAccess = [];
    store.channelsInfo = null;
    store.interfaces = [];
    store.selectedSubscriber = null;
}

async function loadNetBoxConfig() {
    return apiGet('/api/netbox/config');
}

async function testNetBoxConnection(config) {
    const params = new URLSearchParams(config);
    return apiGet(`/api/netbox/test?${params}`);
}

async function saveNetBoxConfig(config) {
    return apiPost('/api/netbox/save_config', config);
}

async function saveSettings() {
    return apiPost('/api/save_config', {
        auto_save_password: store.autoSavePassword,
        default_username: store.defaultUsername,
    });
}

async function addSubscriber(data) {
    return apiPost('/api/add_employee', data);
}

async function editSubscriber(oldIp, data) {
    return apiPost('/api/edit_subscriber', { ...data, old_ip: oldIp });
}

async function deleteSubscriber(ip) {
    return apiPost('/api/delete_subscriber', { ip });
}

async function replaceMac(data) {
    return apiPost('/api/replace_mac', data);
}

async function toggleInternet(ip, enable) {
    return apiPost('/api/internet_access/toggle', { ip, enable });
}

async function checkMacExists(mac, excludeIp) {
    const params = new URLSearchParams({ mac });
    if (excludeIp) params.set('exclude_ip', excludeIp);
    return apiGet(`/api/check_mac?${params}`);
}

async function getFreeIps() {
    return apiGet('/api/free_ips');
}

async function checkIp(ip) {
    return apiGet(`/api/check_ip?ip=${encodeURIComponent(ip)}`);
}

async function findDhcpLease(ip) {
    return apiGet(`/api/find_dhcp_lease?ip=${encodeURIComponent(ip)}`);
}

async function analyzeChannels() {
    return apiGet('/api/analyze_channels');
}

async function findQueues(ip) {
    const params = ip ? `?ip=${encodeURIComponent(ip)}` : '';
    return apiGet(`/api/find_queues${params}`);
}

async function forgetCredentials(device) {
    return apiDelete(`/api/forget_credentials?device=${encodeURIComponent(device)}`);
}
