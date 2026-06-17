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

    autoSavePassword: false,
    defaultUsername: 'admin',
});
