const store = Vue.reactive({
    connected: false,
    currentDevice: null,
    connecting: false,
    connectingDevice: null,
    devicesLoading: false,

    devices: {},
    netboxConfigured: false,

    queueTree: [],
    allQueues: [],
    queueStats: {},
    dhcpPools: [],
    subscribers: [],
    internetAccess: [],
    channelsInfo: null,
    interfaces: [],

    activeTab: 'subscribers',
    selectedSubscriber: null,

    loading: false,
    loadingMessage: '',
    error: null,

    showIpModal: false,
    showNetBoxModal: false,
    showCredentialsModal: false,
    credentialsDevice: null,
    credentialsCallback: null,

    showSubscriberModal: false,
    subscriberModalMode: 'add',
    subscriberForm: null,
    subscriberQueues: [],
    editOldIp: null,
    trafficChains: null,
    trafficLoading: false,
    freeIpsData: null,

    showMacReplaceModal: false,
    macReplaceSub: null,

    showDeleteModal: false,
    deleteSub: null,

    floatingMenuSub: null,
};

store.menuEdit = function(sub) {
    store.floatingMenuSub = null;
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
        internet_access: false,
    };
    for (const ip of (store.internetAccess || [])) {
        if (ip === sub.ip) { store.subscriberForm.internet_access = true; break; }
    }
    store.subscriberQueues = [];
    store.trafficChains = null;
};

store.menuMacReplace = function(sub) {
    store.floatingMenuSub = null;
    store.showMacReplaceModal = true;
    store.macReplaceSub = sub;
};

store.menuCopy = function(sub) {
    store.floatingMenuSub = null;
    const text = 'IP: ' + sub.ip + '\nMAC: ' + sub.mac + '\n' + sub.comment;
    navigator.clipboard.writeText(text).catch(function() {});
};

store.menuDelete = function(sub) {
    store.floatingMenuSub = null;
    store.showDeleteModal = true;
    store.deleteSub = sub;
};

    autoSavePassword: false,
    defaultUsername: 'admin',
});
