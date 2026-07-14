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
    internetTimeouts: {},
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

    moveIpPopover: null,
    moveIpData: null,

    floatingMenuSub: null,
    menuX: 0,
    menuY: 0,

    internetPopupSub: null,
    customDays: 0,
    customHours: 1,

    autoSavePassword: false,
    defaultUsername: 'admin',

    matrixEnabled: false,
    pendingRequests: [],
    pendingCount: 0,
    matrixPendingId: null,
    showPendingList: false,
});

store.menuEdit = function(sub) {
    store.floatingMenuSub = null;
    var parts = (sub.comment || '').split(' - ');
    var position = parts.length > 1 ? parts[0] : '';
    var name = parts.length > 1 ? parts.slice(1).join(' - ') : (sub.comment || '');
    store.subscriberModalMode = 'edit';
    store.editOldIp = sub.ip;
    store.subscriberForm = {
        full_name: name,
        position: position,
        ip: sub.ip,
        mac: sub.mac || '',
        internet_access: false,
    };
    var cleanIp = (sub.ip || '').split('/')[0];
    for (var i = 0; i < (store.internetAccess || []).length; i++) {
        if ((store.internetAccess[i] || '').split('/')[0] === cleanIp) { store.subscriberForm.internet_access = true; break; }
    }
    store.trafficChains = null;
    store.showSubscriberModal = true;
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
        var cleanIp = (sub.ip || '').split('/')[0];
        if (!store.internetAccess.some(function(a) { return (a || '').split('/')[0] === cleanIp; })) store.internetAccess.push(sub.ip);
        store.internetTimeouts[(sub.ip || '').split('/')[0]] = timeout || '';
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
