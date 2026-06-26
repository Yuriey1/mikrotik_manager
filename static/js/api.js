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
    store.loading = true;
    store.loadingMessage = 'Подключение к ' + name + '...';
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
        store.loading = false;
        store.loadingMessage = '';
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

async function addSubscriber(data) {
    store.loading = true;
    store.loadingMessage = 'Добавление абонента...';
    try { return await apiPost('/api/add_employee', data); }
    finally { store.loading = false; store.loadingMessage = ''; }
}

async function editSubscriber(oldIp, data) {
    store.loading = true;
    store.loadingMessage = 'Сохранение изменений...';
    try { return await apiPost('/api/edit_subscriber', { ...data, old_ip: oldIp }); }
    finally { store.loading = false; store.loadingMessage = ''; }
}

async function deleteSubscriber(ip) {
    store.loading = true;
    store.loadingMessage = 'Удаление абонента...';
    try { return await apiPost('/api/delete_subscriber', { ip }); }
    finally { store.loading = false; store.loadingMessage = ''; }
}

async function getOldLeases(age) {
    return apiGet(`/api/old_leases?age=${age}`);
}

async function replaceMac(data) {
    store.loading = true;
    store.loadingMessage = 'Замена MAC адреса...';
    try { return await apiPost('/api/replace_mac', data); }
    finally { store.loading = false; store.loadingMessage = ''; }
}

async function toggleInternet(ip, enable, comment, timeout) {
    store.loading = true;
    store.loadingMessage = (enable ? 'Включение' : 'Отключение') + ' доступа в интернет...';
    try { return await apiPost('/api/internet_access/toggle', { ip, enable, comment: comment || '', timeout: timeout || '' }); }
    finally { store.loading = false; store.loadingMessage = ''; }
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

async function moveIp(ip, from_queue_id, to_queue_id) {
    return apiPost('/api/move_ip', { ip, from_queue_id, to_queue_id });
}

async function resetQueueTraffic(queue_id, new_value) {
    return apiPost('/api/reset_queue_traffic', { queue_id, new_value: new_value || 0 });
}

async function forgetCredentials(device) {
    return apiDelete(`/api/forget_credentials?device=${encodeURIComponent(device)}`);
}

async function saveCredentials(device, username, password) {
    return apiPost('/api/save_credentials', { device, username, password });
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
        console.error('refreshData: error', e);
        store.error = e.message;
    }
}

function buildTrafficChains(channels, fullQueues, ipQueuesData, ip) {
    if (!channels?.channels?.length) return null;

    const allFlat = [];
    const srcQueues = fullQueues || [];
    for (const n of srcQueues) {
        if (n.parent === 'none') n.parent = null;
        allFlat.push(n);
    }

    const dstMap = {};
    const queueDstMap = new Map();

    allFlat.forEach(q => {
        if (!q.dst || q.dst.trim() === '') return;
        const dst = q.dst.trim();
        if (!dstMap[dst]) dstMap[dst] = { parentQueues: [], children: new Set() };
        if (!q.parent) dstMap[dst].parentQueues.push(q);
    });

    allFlat.forEach(q => {
        if (!q.parent && q.dst && q.dst.trim() !== '') {
            const dst = q.dst.trim();
            queueDstMap.set(q.name, dst);
            const stack = [...(q.children || [])];
            while (stack.length) {
                const c = stack.pop();
                if (!queueDstMap.has(c.name)) queueDstMap.set(c.name, dst);
                if (c.children) stack.push(...c.children);
            }
        }
    });

    const trafficParentNames = new Set();
    Object.values(dstMap).forEach(info => {
        info.parentQueues.forEach(pq => trafficParentNames.add(pq.name));
    });

    function isAncestorOf(parent, child) {
        if (!parent || !child || !parent.children) return false;
        const stack = [...parent.children];
        while (stack.length) {
            const c = stack.pop();
            if (c.name === child.name) return true;
            if (c.children) stack.push(...c.children);
        }
        return false;
    }

    function getQueueDepth(q) {
        let depth = 0;
        let cur = q;
        while (cur && cur.parent) {
            depth++;
            cur = allFlat.find(p => p.name === cur.parent);
        }
        return depth;
    }

    function isInterfaceOnlyTarget(targetList) {
        if (!targetList || !targetList.length) return false;
        for (const t of targetList) {
            if (/^\d+\.\d+\.\d+\.\d+/.test(t.trim())) return false;
        }
        return true;
    }

    const selectedQueues = {};
    const autoPickedDsts = new Set();
    const defaultQueuePerDst = {};
    const existing = ipQueuesData?.existing || [];
    const ipData = ipQueuesData;

    Object.keys(dstMap).forEach(dst => {
        const isPaid = q => q.name && q.name.toLowerCase().startsWith('paid');
        const isMarked = q => !!(q.packet_marks && q.packet_marks.trim());

        var findDefault = function() {
            const dstQueues = allFlat.filter(q => queueDstMap.get(q.name) === dst && !isPaid(q) && !isMarked(q));
            const sorted = [...dstQueues].sort((a, b) => getQueueDepth(b) - getQueueDepth(a));

            function hasIpTarget(qq) {
                return qq.target && qq.target.length > 0 && /^\d+\.\d+\.\d+\.\d+/.test((qq.target[0] || '').trim());
            }
            function hasAllAddr(qq) {
                return qq.target && qq.target.some(function(t) {
                    t = (t || '').trim();
                    return t === '0.0.0.0/0' || t === '0.0.0.0';
                });
            }
            function hasEmptyTarget(qq) {
                return !qq.target || qq.target.length === 0;
            }
            function hasOurIp(qq) {
                var ipStripped = ip.split('/')[0];
                return qq.target && qq.target.some(function(t) {
                    return (t || '').trim().split('/')[0] === ipStripped;
                });
            }

            var pick = function(arr) { return arr.length > 0 ? arr[0] : null; };
            var nonParent = sorted.filter(function(q) { return !trafficParentNames.has(q.name); });
            var parent = sorted.filter(function(q) { return trafficParentNames.has(q.name); });

            var q = pick(nonParent.filter(function(q) { return isInterfaceOnlyTarget(q.target); }));
            if (!q) q = pick(nonParent.filter(hasAllAddr));
            if (!q) q = pick(nonParent.filter(hasEmptyTarget));
            if (!q) q = pick(nonParent.filter(hasOurIp));
            if (!q) q = pick(nonParent);
            if (!q) q = pick(parent.filter(function(q) { return isInterfaceOnlyTarget(q.target); }));
            if (!q) q = pick(parent.filter(hasAllAddr));
            if (!q) q = pick(parent.filter(hasEmptyTarget));
            if (!q) q = pick(parent);
            return q;
        };

        var defaultQ = findDefault();
        if (defaultQ) defaultQueuePerDst[dst] = defaultQ.name;

        let queue = null;
        let autoPicked = false;
        if (existing && existing.length > 0) {
            for (const name of existing) {
                if (queueDstMap.get(name) === dst) {
                    const q = allFlat.find(q => q.name === name);
                    if (q && !isPaid(q)) { queue = q; break; }
                }
            }
        }
        if (!queue) {
            autoPicked = true;
            queue = defaultQ;
        }
        if (queue) {
            selectedQueues[dst] = queue;
            if (autoPicked) autoPickedDsts.add(dst);
        }
    });

    const chains = [];
    const dstEntries = Object.entries(dstMap).sort((a, b) => b[1].parentQueues.length - a[1].parentQueues.length);

    const primaryDst = channels.primary_channel?.interface;
    const backupDst = channels.backup_channel?.interface;

    dstEntries.forEach(([dst, info]) => {
        const dstQueue = selectedQueues[dst];
        const isPrimary = primaryDst === dst;
        const isBackup = backupDst === dst;

        let ancestorParent = null;
        if (dstQueue) {
            for (const pq of info.parentQueues) {
                if (isAncestorOf(pq, dstQueue)) {
                    ancestorParent = pq;
                    break;
                }
            }
        }

        chains.push({
            dst,
            dstQueue,
            ancestorParent,
            isPrimary,
            isBackup,
            label: isPrimary ? 'Основной' : (isBackup ? 'Резервный' : dst),
            iconClass: isPrimary ? 'fa-bolt' : (isBackup ? 'fa-shield-alt' : 'fa-ethernet'),
            chainClass: isPrimary ? 'primary-chain' : (isBackup ? 'backup-chain' : ''),
            labelClass: isPrimary ? 'primary' : (isBackup ? 'backup' : ''),
        });
    });

    return { ip, chains, allFlat, queueDstMap, selectedQueues, autoPickedDsts, defaultQueuePerDst, userEditedDsts: new Set() };
}

function formatBandwidth(maxLimit) {
    if (!maxLimit || maxLimit === '0/0') return '';
    const parts = maxLimit.split('/');
    if (parts.length !== 2) return maxLimit;
    function fmtOne(v) {
        v = v.trim();
        if (!v || v === '0') return null;
        const m = v.match(/^(\d+(?:\.\d+)?)\s*(k|M|G)?$/i);
        if (m) {
            const num = parseFloat(m[1]);
            const unit = (m[2] || '').toUpperCase();
            if (unit === 'G') return num + ' Gbit/s';
            if (unit === 'M') return num + ' Mbit/s';
            if (unit === 'k' || unit === 'K') return num + ' Kbit/s';
            if (num >= 1000000000) return (num / 1000000000).toFixed(1).replace(/\.0$/, '') + ' Gbit/s';
            if (num >= 1000000) return (num / 1000000).toFixed(1).replace(/\.0$/, '') + ' Mbit/s';
            if (num >= 1000) return (num / 1000).toFixed(1).replace(/\.0$/, '') + ' Kbit/s';
            return num + ' bit/s';
        }
        return v;
    }
    const up = fmtOne(parts[0]);
    const down = fmtOne(parts[1]);
    if (up && down) return up + ' / ' + down;
    if (up) return up;
    if (down) return down;
    return '';
}
