const { createApp, onMounted, computed } = Vue;

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

        return { store, ...Vue };
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

        async function doSaveSettings() {
            localStorage.setItem('mikrotik_settings', JSON.stringify({
                auto_save_password: store.autoSavePassword,
                default_username: store.defaultUsername,
            }));
            try { await saveSettings(); } catch (e) {}
        }

        function openNetBoxConfig() { store.showNetBoxModal = true; }

        return { store, searchQuery, filteredDevices, doConnect, doDisconnect, doSaveSettings, openNetBoxConfig };
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
        return { store };
    },
});

app.component('queue-tab', {
    template: '#queue-tab',
    setup() {
        function loadQueueTree() {
            store.error = 'Загрузка дерева очередей будет реализована в Фазе 4';
        }
        return { store, loadQueueTree };
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
        return { store };
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
