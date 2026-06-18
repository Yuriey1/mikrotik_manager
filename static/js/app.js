const { createApp, onMounted, computed } = Vue;

window.addEventListener('error', function(e) {
    var el = document.getElementById('app');
    if (el) {
        el.setAttribute('style', 'display:block !important; padding:20px; color:#d44a3a; font-family:monospace; background:#0b0c0e;');
        el.innerHTML = '<h3>Ошибка JS:</h3><pre>' + (e.error ? e.error.stack || e.error.message : e.message) + '</pre>';
    }
});

try {

const app = createApp({
    setup() {
        onMounted(async () => {
            await loadDevices();
            try {
                const nc = await loadNetBoxConfig();
                if (nc.success) {
                    store.netboxConfigured = !!(nc.config && nc.config.url && nc.config.token);
                }
            } catch (e) {}
            const saved = JSON.parse(localStorage.getItem('mikrotik_settings') || '{}');
            if (saved.auto_save_password !== undefined) store.autoSavePassword = saved.auto_save_password;
            if (saved.default_username) store.defaultUsername = saved.default_username;
        });

        return { store, ...Vue, innerW: Vue.ref(window.innerWidth), innerH: Vue.ref(window.innerHeight) };
    },
});

app.component('app-header', {
    template: '#app-header',
    setup() {
        const queueCount = computed(() => store.queueStats?.total_queues || 0);
        const deviceTitle = computed(() => store.currentDevice || 'Нет устройства');
        const netboxLabel = computed(() => store.netboxConfigured ? 'NetBox: настроен' : 'NetBox: не настроен');

        async function refreshDevices() {
            await loadDevices();
        }

        async function doDisconnect() {
            await disconnectDevice();
        }

        return { store, queueCount, deviceTitle, netboxLabel, refreshDevices, doDisconnect };
    },
});

app.component('device-sidebar', {
    template: '#device-sidebar',
    setup() {
        const searchQuery = Vue.ref('');

        const filteredDevices = computed(() => {
            const q = searchQuery.value.toLowerCase().trim();
            const list = Object.values(store.devices);
            if (!q) return list;
            return list.filter(d =>
                d.name.toLowerCase().includes(q) ||
                d.ip.includes(q) ||
                (d.device_type && d.device_type.toLowerCase().includes(q))
            );
        });

        async function doConnect(name) {
            try {
                await connectDevice(name, '', '');
            } catch (e) {}
        }

        async function doDisconnect() {
            await disconnectDevice();
        }

        function openNetBoxConfig() { store.showNetBoxModal = true; }

        return { store, searchQuery, filteredDevices, doConnect, doDisconnect, openNetBoxConfig };
    },
});

app.component('tab-bar', {
    template: '#tab-bar',
    setup() {
        const tabs = [
            { key: 'subscribers', icon: 'fa-users', label: 'Абоненты' },
            { key: 'queues', icon: 'fa-sitemap', label: 'Очереди' },
        ];
        return { store, tabs };
    },
});

app.component('subscriber-tab', {
    template: '#subscriber-tab',
    setup() {
        const searchText = Vue.ref('');
        const selectedIp = Vue.ref(null);

        const filteredSubscribers = Vue.computed(() => {
            const q = searchText.value.toLowerCase().trim();
            if (!q) return store.subscribers;
            return store.subscribers.filter(s =>
                (s.ip && s.ip.toLowerCase().includes(q)) ||
                (s.comment && s.comment.toLowerCase().includes(q)) ||
                (s.mac && s.mac.toLowerCase().includes(q))
            );
        });

        function parseName(comment) {
            if (!comment) return '—';
            const parts = comment.split(' - ');
            return parts.length > 1 ? parts.slice(1).join(' - ') : comment;
        }
        function parsePosition(comment) {
            if (!comment) return '—';
            const parts = comment.split(' - ');
            return parts.length > 1 ? parts[0] : '';
        }
        function hasInternet(ip) {
            return store.internetAccess.includes(ip);
        }

        async function toggleNet(sub) {
            const enable = !hasInternet(sub.ip);
            try {
                await toggleInternet(sub.ip, enable, sub.comment);
                if (enable) {
                    if (!store.internetAccess.includes(sub.ip)) store.internetAccess.push(sub.ip);
                } else {
                    store.internetAccess = store.internetAccess.filter(i => i !== sub.ip);
                }
            } catch (e) {
                store.error = e.message;
            }
        }

        function selectSubscriber(sub) {
            selectedIp.value = sub.ip;
        }

        function openAddModal() {
            store.showSubscriberModal = true;
            store.subscriberModalMode = 'add';
            store.subscriberForm = { full_name: '', position: '', ip: '', mac: '', internet_access: false };
            store.trafficChains = null;
            store.editOldIp = null;
        }

        function editSubscriber(sub) {
            const parts = (sub.comment || '').split(' - ');
            const position = parts.length > 1 ? parts[0] : '';
            const name = parts.length > 1 ? parts.slice(1).join(' - ') : (sub.comment || '');
            store.showSubscriberModal = true;
            store.subscriberModalMode = 'edit';
            store.editOldIp = sub.ip;
            store.subscriberForm = {
                full_name: name,
                position: position,
                ip: sub.ip,
                mac: sub.mac || '',
                internet_access: hasInternet(sub.ip)
            };
            store.trafficChains = null;
        }

        function openMacReplace(sub) {
            store.showMacReplaceModal = true;
            store.macReplaceSub = sub;
        }

        function copySubscriber(sub) {
            const text = `IP: ${sub.ip}\nMAC: ${sub.mac}\n${sub.comment}`;
            navigator.clipboard.writeText(text).catch(() => {});
        }

        function confirmDelete(sub) {
            store.showDeleteModal = true;
            store.deleteSub = sub;
        }

        return { store, searchText, selectedIp,
                 filteredSubscribers, parseName, parsePosition, hasInternet,
                 toggleNet, selectSubscriber,
                 openAddModal, editSubscriber, openMacReplace, copySubscriber, confirmDelete };
    },
});

// ===== SUBSCRIBER MODAL (add/edit) =====
app.component('subscriber-modal', {
    template: '#subscriber-modal',
    setup() {
        const showModal = Vue.computed(() => store.showSubscriberModal);
        const mode = Vue.computed(() => store.subscriberModalMode || 'add');
        const form = Vue.computed(() => store.subscriberForm || { full_name: '', position: '', ip: '', mac: '', internet_access: false });
        const showTraffic = Vue.computed(() => !!trafficData.value || !!store.trafficLoading);
        const trafficLoading = Vue.computed(() => store.trafficLoading);
        const trafficData = Vue.computed(() => store.trafficChains);
        const popoverTop = Vue.ref(0);
        const popoverLeft = Vue.ref(0);
        const popoverQueues = Vue.ref([]);
        const saving = Vue.ref(false);
        let trafficTimer = null;

        function closeModal() {
            store.showSubscriberModal = false;
            store.trafficChains = null;
            store.trafficLoading = false;
            store.trafficPopover = null;
            if (trafficTimer) clearTimeout(trafficTimer);
        }

        async function onIpChange() {
            if (trafficTimer) clearTimeout(trafficTimer);
            const ip = form.value.ip;
            if (!ip) { store.trafficChains = null; return; }
            trafficTimer = setTimeout(async () => { await loadTrafficForIp(ip); }, 600);
        }

        async function loadTrafficForIp(ip) {
            store.trafficLoading = true;
            try {
                const [channels, queues] = await Promise.all([
                    analyzeChannels().catch(() => null),
                    findQueues(ip).catch(() => null),
                ]);
                if (channels?.success && queues?.success) {
                    const data = buildTrafficChains(channels, store.allQueues, queues, ip);
                    store.trafficChains = data;
                    if (data?.selectedQueues) {
                        store.trafficQueues = data.selectedQueues;
                    }
                }
            } catch (e) {} finally {
                store.trafficLoading = false;
            }
        }

        Vue.watch(() => store.showSubscriberModal, async (val) => {
            if (val && mode.value === 'edit' && form.value.ip) {
                await loadTrafficForIp(form.value.ip);
            }
        });

        function openTrafficPopover(event, chain) {
            const rect = event.currentTarget.getBoundingClientRect();
            popoverTop.value = rect.bottom + 5;
            popoverLeft.value = Math.max(10, rect.left - 100);
            store.trafficPopover = chain;
            store.trafficPopoverDst = chain.dst;

            const allFlat = (store.trafficChains && store.trafficChains.allFlat) || [];
            const filtered = allFlat.filter(q => {
                if (q.name && q.name.toLowerCase().startsWith('paid')) return false;
                if (!q.parent) return false;
                const qDst = (store.trafficChains && store.trafficChains.queueDstMap && store.trafficChains.queueDstMap instanceof Map)
                    ? store.trafficChains.queueDstMap.get(q.name)
                    : null;
                if (chain.dst && qDst && qDst !== chain.dst) return false;
                return true;
            });
            popoverQueues.value = filtered;
        }

        function closePopover() { store.trafficPopover = null; }

        function isPopoverSelected(q) {
            const sel = store.trafficQueues && store.trafficQueues[store.trafficPopoverDst];
            return sel && sel.name === q.name;
        }

        function selectQueueFromPopover(q) {
            if (store.trafficPopoverDst) {
                store.trafficQueues[store.trafficPopoverDst] = q;
                const data = store.trafficChains;
                if (data) {
                    data.selectedQueues = { ...store.trafficQueues };
                    const chains = data.chains.map(c => ({
                        ...c,
                        dstQueue: store.trafficQueues[c.dst] || c.dstQueue
                    }));
                    store.trafficChains = { ...data, chains };
                }
            }
            closePopover();
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
                    if (num >= 1e9) return (num / 1e9).toFixed(1).replace(/\.0$/, '') + ' Gbit/s';
                    if (num >= 1e6) return (num / 1e6).toFixed(1).replace(/\.0$/, '') + ' Mbit/s';
                    if (num >= 1e3) return (num / 1e3).toFixed(1).replace(/\.0$/, '') + ' Kbit/s';
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

        async function showFreeIps() {
            try {
                const data = await getFreeIps();
                store.freeIpsData = data;
                store.showIpModal = true;
            } catch (e) { store.error = e.message; }
        }

        async function saveSubscriber() {
            const f = form.value;
            if (!f.full_name || !f.position || !f.ip) {
                store.error = 'Заполните ФИО, должность и IP';
                return;
            }
            const selQueues = [];
            const data = store.trafficChains;
            if (data && data.chains) {
                for (const chain of data.chains) {
                    if (chain.dstQueue && chain.dstQueue.name) {
                        selQueues.push(chain.dstQueue.name);
                    }
                }
            }
            saving.value = true;
            try {
                const reqData = {
                    full_name: f.full_name,
                    position: f.position,
                    ip: f.ip,
                    mac: f.mac,
                    internet_access: f.internet_access,
                    queues: selQueues,
                };
                if (mode.value === 'add') {
                    const result = await addSubscriber(reqData);
                    if (result.success) {
                        closeModal();
                        await refreshData();
                    } else {
                        store.error = result.error || result.message;
                    }
                } else {
                    const result = await editSubscriber(store.editOldIp, reqData);
                    if (result.success) {
                        closeModal();
                        await refreshData();
                    } else {
                        store.error = result.error || result.message;
                    }
                }
            } catch (e) {
                store.error = e.message;
            } finally {
                saving.value = false;
            }
        }

        return { store, showModal, mode, form, showTraffic, trafficLoading, trafficData, saving,
                 popoverTop, popoverLeft, popoverQueues,
                 closeModal, onIpChange, showFreeIps, formatBandwidth,
                 openTrafficPopover, closePopover, isPopoverSelected, selectQueueFromPopover,
                 saveSubscriber };
    },
});

// ===== MAC REPLACE MODAL =====
app.component('mac-replace-modal', {
    template: '#mac-replace-modal',
    setup() {
        const showModal = Vue.computed(() => store.showMacReplaceModal);
        const macReplaceSub = Vue.computed(() => store.macReplaceSub);
        const replaceMode = Vue.ref('by-ip');
        const replaceNewIp = Vue.ref('');
        const replaceNewMac = Vue.ref('');
        const replaceClientId = Vue.ref('');
        const replaceRunning = Vue.ref(false);

        function closeModal() {
            store.showMacReplaceModal = false;
            store.macReplaceSub = null;
            replaceMode.value = 'by-ip';
            replaceNewIp.value = '';
            replaceNewMac.value = '';
            replaceClientId.value = '';
        }

        function onReplaceModeChange() {
            replaceNewIp.value = '';
            replaceNewMac.value = '';
            replaceClientId.value = '';
        }

        Vue.watch(replaceNewMac, (val) => {
            if (replaceMode.value === 'by-mac' && val && val.includes(':')) {
                replaceClientId.value = '1:' + val.toLowerCase().replace(/-/g, ':');
            }
        });

        async function executeReplace() {
            if (!macReplaceSub.value) return;
            replaceRunning.value = true;
            try {
                let data;
                if (replaceMode.value === 'by-ip') {
                    if (!replaceNewIp.value) { store.error = 'Укажите новый IP'; replaceRunning.value = false; return; }
                    data = { mode: 'by-ip', old_ip: macReplaceSub.value.ip, new_ip: replaceNewIp.value };
                } else {
                    if (!replaceNewMac.value) { store.error = 'Укажите новый MAC'; replaceRunning.value = false; return; }
                    data = { mode: 'by-mac', ip: macReplaceSub.value.ip, new_mac: replaceNewMac.value, client_id: replaceClientId.value || undefined };
                }
                const result = await replaceMac(data);
                if (result.success) {
                    closeModal();
                    await refreshData();
                } else {
                    store.error = result.error || result.message;
                }
            } catch (e) {
                store.error = e.message;
            } finally {
                replaceRunning.value = false;
            }
        }

        return { store, showModal, macReplaceSub, replaceMode, replaceNewIp, replaceNewMac, replaceClientId, replaceRunning,
                 closeModal, onReplaceModeChange, executeReplace };
    },
});

// ===== DELETE CONFIRM MODAL =====
app.component('delete-confirm-modal', {
    template: '#delete-confirm-modal',
    setup() {
        const showModal = Vue.computed(() => store.showDeleteModal);
        const deleteSub = Vue.computed(() => store.deleteSub);
        const deleteRunning = Vue.ref(false);

        function closeModal() {
            store.showDeleteModal = false;
            store.deleteSub = null;
        }

        async function executeDelete() {
            if (!deleteSub.value) return;
            const ip = deleteSub.value.ip;
            deleteRunning.value = true;
            try {
                const result = await deleteSubscriber(ip);
                if (result.success) {
                    closeModal();
                    store.subscribers = store.subscribers.filter(s => s.ip !== ip);
                    await refreshData();
                } else {
                    store.error = result.error || result.message;
                }
            } catch (e) {
                store.error = e.message;
            } finally {
                deleteRunning.value = false;
            }
        }

        return { showModal, deleteSub, deleteRunning, closeModal, executeDelete };
    },
});

app.component('queue-tab', {
    template: '#queue-tab',
    setup() {
        const treeFilter = Vue.ref('');
        const expandedNodes = Vue.reactive({});

        const filteredTree = Vue.computed(() => {
            const q = treeFilter.value.toLowerCase().trim();
            if (!q) return store.queueTree;
            function filterTree(nodes) {
                const result = [];
                for (const n of nodes) {
                    const nameMatch = n.name && n.name.toLowerCase().includes(q);
                    const childMatch = n.children && filterTree(n.children);
                    if (nameMatch || (childMatch && childMatch.length > 0)) {
                        const copy = { ...n, children: n.children ? filterTree(n.children) : [] };
                        if (nameMatch && n.children) copy.children = n.children;
                        result.push(copy);
                    }
                }
                return result;
            }
            return filterTree(store.queueTree);
        });

        async function loadTree() {
            await refreshData();
        }

        function expandAll() {
            function walk(nodes) {
                for (const n of nodes) {
                    if (n.children && n.children.length > 0) {
                        expandedNodes[n.id] = true;
                        walk(n.children);
                    }
                }
            }
            walk(store.queueTree);
        }

        function collapseAll() {
            for (const key of Object.keys(expandedNodes)) {
                delete expandedNodes[key];
            }
        }

        function toggleNode(nodeId) {
            if (expandedNodes[nodeId]) {
                delete expandedNodes[nodeId];
            } else {
                expandedNodes[nodeId] = true;
            }
        }

        return { store, treeFilter, expandedNodes, filteredTree, loadTree, expandAll, collapseAll, toggleNode };
    },
});

app.component('queue-node', {
    template: '#queue-node',
    props: { node: Object, depth: Number, expandedNodes: Object },
    emits: ['toggle'],
    setup(props) {
        const expanded = Vue.computed(() => !!props.expandedNodes[props.node.id]);
        return { expanded };
    },
});

app.component('loading-overlay', {
    template: '#loading-overlay',
    setup() {
        return { store };
    },
});

app.component('error-modal', {
    template: '#error-modal',
    setup() {
        function close() { store.error = null; }
        return { store, close };
    },
});

app.component('netbox-config-modal', {
    template: '#netbox-config-modal',
    setup() {
        const url = Vue.ref('');
        const token = Vue.ref('');
        const verifySsl = Vue.ref(true);

        onMounted(async () => {
            try {
                const data = await loadNetBoxConfig();
                if (data.success && data.config) {
                    url.value = data.config.url || '';
                    token.value = data.config.token || '';
                    verifySsl.value = data.config.verify_ssl !== false;
                }
            } catch (e) {}
        });

        async function doTest() {
            const result = await testNetBoxConnection({ url: url.value, token: token.value, verify_ssl: verifySsl.value });
            alert(result.success ? result.message : result.error);
        }

        async function doSave() {
            const result = await saveNetBoxConfig({ url: url.value, token: token.value, verify_ssl: verifySsl.value });
            if (result.success) {
                store.netboxConfigured = true;
                store.showNetBoxModal = false;
                await loadDevices();
            } else {
                alert(result.error);
            }
        }

        function close() { store.showNetBoxModal = false; }
        Vue.watch(() => store.showNetBoxModal, (val) => { if (!val) return; });

        return { store, url, token, verifySsl, doTest, doSave, close };
    },
});

app.component('ip-selector-modal', {
    template: '#ip-selector-modal',
    setup() {
        function selectIp(ip) {
            if (store.subscriberForm) {
                store.subscriberForm.ip = ip;
            }
            store.showIpModal = false;
        }
        return { store, selectIp };
    },
});

app.component('credentials-modal', {
    template: '#credentials-modal',
    setup() {
        const username = Vue.ref(store.defaultUsername);
        const password = Vue.ref('');
        const savePassword = Vue.ref(store.autoSavePassword);

        function submit() {
            store.showCredentialsModal = false;
            connectDevice(store.credentialsDevice, username.value, password.value)
                .catch(e => { store.error = e.message; });
        }

        function cancel() {
            store.showCredentialsModal = false;
            store.credentialsDevice = null;
        }

        return { store, username, password, savePassword, submit, cancel };
    },
});

app.mount('#app');

} catch(e) {
    var el = document.getElementById('app');
    if (el) {
        el.setAttribute('style', 'display:block !important; padding:20px; color:#d44a3a; font-family:monospace; background:#0b0c0e;');
        el.innerHTML = '<h3>Ошибка инициализации Vue:</h3><pre>' + (e.stack || e.message) + '</pre>';
    }
}
