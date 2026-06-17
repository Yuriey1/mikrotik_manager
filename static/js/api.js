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

async function toggleInternet(ip, enable, comment) {
    return apiPost('/api/internet_access/toggle', { ip, enable, comment: comment || '' });
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

async function loadSubscribers() {
    try {
        const data = await apiGet('/api/dhcp_subscribers?all=true');
        if (data.success) {
            store.subscribers = data.subscribers || [];
        }
    } catch (e) {
        store.error = e.message;
    }
}

async function refreshData() {
    try {
        const data = await apiGet('/api/sync');
        if (data.success !== false) {
            store.queueTree = data.queue_tree || [];
            store.allQueues = data.all_queues || [];
            store.queueStats = data.queue_stats || {};
            store.dhcpPools = data.dhcp_pools || [];
            store.subscribers = data.subscribers || [];
            store.internetAccess = data.internet_access || [];
            store.channelsInfo = data.channels || null;
            store.interfaces = data.interfaces || [];
        }
    } catch (e) {
        store.error = e.message;
    }
}

function buildTrafficChains(channels, queuesData, ip) {
    if (!channels?.channels?.length) return null;
    const chains = channels.channels.map(ch => ({
        name: ch.interface || ch.gateway || ch.name,
        type: ch.type || 'primary',
        ip: ch.ip_address || '',
        gateway: ch.gateway || '',
        nodes: [],
    }));
    if (queuesData?.queues) {
        const ipStripped = ip.split('/')[0];
        for (const chain of chains) {
            for (const q of queuesData.queues) {
                const dstMatch = q.dst && (
                    q.dst.includes(chain.gateway) || q.dst.includes(chain.ip.split('/')[0])
                );
                const targetMatch = q.target && q.target.some(t => t.split('/')[0] === ipStripped);
                if (dstMatch || targetMatch) {
                    chain.nodes.push({
                        id: q.id,
                        name: q.name,
                        target: q.target || [],
                        dst: q.dst || '',
                        max_limit: q.max_limit || '',
                        hasIp: targetMatch,
                    });
                }
            }
        }
    }
    return chains.filter(c => c.nodes.length > 0);
}
