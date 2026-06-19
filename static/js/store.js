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
    trafficQueues: {},
    trafficPopover: null,
    trafficPopoverDst: null,
    freeIpsData: null,

    showMacReplaceModal: false,
    macReplaceSub: null,

    showDeleteModal: false,
    deleteSub: null,

    showCleanupModal: false,

    floatingMenuSub: null,
    menuX: 0,
    menuY: 0,

    internetPopupSub: null,
    customDays: 0,
    customHours: 1,

    autoSavePassword: false,
    defaultUsername: 'admin',
});

store.menuEdit = function(sub) {
    store.floatingMenuSub = null;
    var parts = (sub.comment || '').split(' - ');
    var position = parts.length > 1 ? parts[0] : '';
    var name = parts.length > 1 ? parts.slice(1).join(' - ') : (sub.comment || '');
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
    for (var i = 0; i < (store.internetAccess || []).length; i++) {
        if (store.internetAccess[i] === sub.ip) { store.subscriberForm.internet_access = true; break; }
    }
    store.trafficChains = null;
};

store.menuMacReplace = function(sub) {
    store.floatingMenuSub = null;
    store.showMacReplaceModal = true;
    store.macReplaceSub = sub;
};

store.menuCopy = function(sub) {
    store.floatingMenuSub = null;
    var text = 'IP: ' + sub.ip + '\nMAC: ' + sub.mac + '\n' + sub.comment;
    navigator.clipboard.writeText(text).catch(function() {});
};

store.menuDelete = function(sub) {
    store.floatingMenuSub = null;
    store.showDeleteModal = true;
    store.deleteSub = sub;
};

store.setTimedInternet = async function(timeout) {
    var sub = store.internetPopupSub;
    store.internetPopupSub = null;
    if (!sub) return;
    try {
        await toggleInternet(sub.ip, true, sub.comment, timeout);
        if (store.internetAccess.indexOf(sub.ip) === -1) store.internetAccess.push(sub.ip);
    } catch (e) {
        store.error = e.message;
    }
};

store.applyCustomTimeout = function() {
    var d = parseInt(store.customDays) || 0;
    var h = parseInt(store.customHours) || 0;
    if (d === 0 && h === 0) return;
    var totalH = d * 24 + h;
    var timeout = String(totalH).padStart(2, '0') + ':00:00';
    store.customDays = 0;
    store.customHours = 1;
    store.setTimedInternet(timeout);
};
