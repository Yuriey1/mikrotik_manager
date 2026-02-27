let currentDevice = null;
let queueTree = [];
let queueTreeData = []; // Хранит все данные дерева
let queueTreeFiltered = []; // Отфильтрованные данные
let queueTreeExpanded = {}; // Состояние развернутости узлов
let netboxConfigured = false;
let allDevices = {}; // Хранит все устройства для поиска
let allSubscribers = []; // Хранит всех абонентов DHCP для замены MAC
let selectedSubscriber = null; // Выбранный абонент для действий
let internetAccessList = []; // Список IP с доступом в интернет

// Загрузка при старте
document.addEventListener('DOMContentLoaded', function() {
    loadDevices();
    loadSettings();
    

    loadNetBoxConfig();
    
    // Инициализация модальных окон
    initModals();

});


// Инициализация модальных окон
function initModals() {
    const modals = ['netbox-config-modal'];
    
    modals.forEach(modalId => {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === this) {
                    this.style.display = 'none';
                }
            });
            
            // Закрытие по Escape
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape' && modal.style.display === 'flex') {
                    modal.style.display = 'none';
                }
            });
        }
    });
}

function forgetPassword(deviceName) {
    if (!confirm(`Удалить сохраненные учетные данные для устройства "${deviceName}"?`)) {
        return;
    }
    
    fetch(`/api/forget_credentials?device=${encodeURIComponent(deviceName)}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            // Если это текущее устройство - отключаемся
            if (currentDevice === deviceName) {
                disconnectDevice();
            }
        } else {
            showAlert(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка удаления учетных данных:', error);
        showAlert('Ошибка удаления учетных данных', 'error');
    });
}

function showAddDeviceForm() {
    document.getElementById('device-modal').style.display = 'block';
}

function hideAddDeviceForm() {
    document.getElementById('device-modal').style.display = 'none';
}

function switchTab(tabName) {
    // Скрыть все вкладки
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });

    // Показать выбранную
    document.getElementById(tabName + '-tab').classList.add('active');
    document.querySelectorAll('.tab').forEach(tab => {
        if (tab.textContent.includes(getTabName(tabName))) {
            tab.classList.add('active');
        }
    });
}

function getTabName(tabKey) {
    const tabs = {
        'employee': 'Добавить сотрудника',
        'queues': 'Дерево очередей',
        'mac-replace': 'Замена MAC',
        'tools': 'Инструменты'
    };
    return tabs[tabKey] || tabKey;
}

// Загрузка устройств из NetBox
function loadDevices() {
    console.log('Загрузка устройств из NetBox...');
    
    showLoading('Загрузка устройств...');
    
    fetch('/api/devices')
        .then(response => response.json())
        .then(data => {
            hideLoading();
            const deviceList = document.getElementById('device-list');
            deviceList.innerHTML = '';

            netboxConfigured = data.netbox_configured || false;
            updateNetBoxStatus();
            
            if (data.error) {
                deviceList.innerHTML = `
                    <li class="device-item">
                        <div class="device-card">
                            <div class="device-name" style="color: #e74c3c;">
                                <i class="fas fa-exclamation-triangle"></i> Ошибка загрузки
                            </div>
                            <div class="device-actions">
                                <button class="btn btn-primary" onclick="showNetBoxConfig()">
                                    <i class="fas fa-cog"></i> Настроить NetBox
                                </button>
                            </div>
                        </div>
                    </li>
                `;
                return;
            }

            const devices = data.devices || {};
            const deviceCount = Object.keys(devices).length;

            // Сохраняем устройства для поиска
            allDevices = devices;

            // Обновляем счетчик
            document.getElementById('device-count').textContent = deviceCount;

            if (deviceCount > 0) {
                // Сортируем устройства по алфавиту
                const sortedDevices = Object.entries(devices).sort((a, b) => 
                    a[0].toLowerCase().localeCompare(b[0].toLowerCase())
                );

                sortedDevices.forEach(([name, device]) => {
                    const li = createDeviceCard(name, device);
                    deviceList.appendChild(li);
                });
            } else {
                deviceList.innerHTML = `
                    <li class="device-item">
                        <div class="device-card">
                            <div class="device-name" style="text-align: center; color: #7f8c8d;">
                                <i class="fas fa-server"></i> Нет устройств в NetBox
                            </div>
                            <div class="device-actions">
                                <button class="btn btn-primary" onclick="${netboxConfigured ? 'loadDevices()' : 'showNetBoxConfig()'}">
                                    <i class="fas ${netboxConfigured ? 'fa-sync-alt' : 'fa-cog'}"></i> 
                                    ${netboxConfigured ? 'Обновить' : 'Настроить NetBox'}
                                </button>
                            </div>
                        </div>
                    </li>
                `;
            }
        })
        .catch(error => {
            hideLoading();
            console.error('Ошибка загрузки устройств:', error);
            const deviceList = document.getElementById('device-list');
            deviceList.innerHTML = `
                <li class="device-item">
                    <div class="device-card">
                        <div class="device-name" style="color: #e74c3c;">
                            <i class="fas fa-exclamation-circle"></i> Ошибка сети
                        </div>
                        <div class="device-actions">
                            <button class="btn btn-primary" onclick="loadDevices()">
                                <i class="fas fa-redo"></i> Повторить
                            </button>
                        </div>
                    </div>
                </li>
            `;
        });
}

// Создание карточки устройства
function createDeviceCard(name, device) {
    const li = document.createElement('li');
    li.className = 'device-item';
    li.setAttribute('data-device-name', name); // Добавляем атрибут для поиска
    
    if (currentDevice === name) {
        li.classList.add('active');
    }

    const buttonText = currentDevice === name ? 'Отключить' : 'Подключить';
    const buttonIcon = currentDevice === name ? 'fa-unlink' : 'fa-plug';
    const buttonClass = currentDevice === name ? 'btn-danger' : 'connect-btn';

    li.innerHTML = `
        <div class="device-card">
            <!-- ИМЯ УСТРОЙСТВА (ВЕРХ) -->
            <div class="device-name" title="${name}">
                <i class="fas fa-server" style="color: #6c9efc; margin-right: 8px;"></i>
                ${name}
            </div>
            
            <!-- КНОПКА ПОДКЛЮЧЕНИЯ (СНИЗУ ИМЕНИ) -->
            <div class="device-actions">
                <button class="connect-btn ${buttonClass}" onclick="connectDevice('${name}')">
                    <i class="fas ${buttonIcon}"></i> ${buttonText}
                </button>

            ${currentDevice === name ? `
                    <button class="btn-forget" onclick="forgetPassword('${name}')" 
                        style="margin-top: 5px; background: #4a4a4a; color: #b0b0b0; 
                               border: none; padding: 5px 10px; border-radius: 4px; 
                               font-size: 11px; cursor: pointer;">
                        <i class="fas fa-trash-alt"></i> Забыть данные
                    </button>        ` : ''}
            </div>
            
            <!-- ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (ТОЛЬКО ДЛЯ АКТИВНОГО) -->
            <div class="device-details">
                <div class="device-detail-row">
                    <i class="fas fa-network-wired"></i>
                    <span>${device.ip}:${device.port}</span>
                </div>
                ${device.site ? `
                    <div class="device-detail-row">
                        <i class="fas fa-map-marker-alt"></i>
                        <span>${device.site}</span>
                    </div>
                ` : ''}
                ${device.role ? `
                    <div class="device-detail-row">
                        <i class="fas fa-user-tag"></i>
                        <span>${device.role}</span>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
    
    return li;
}

// Обновление статуса NetBox
function updateNetBoxStatus() {
    const statusDot = document.getElementById('netbox-status');
    const statusText = document.getElementById('netbox-status-text');
    
    if (netboxConfigured) {
        statusDot.className = 'status-dot connected';
        statusDot.title = 'NetBox подключен';
        statusText.textContent = 'NetBox: подключен';
    } else {
        statusDot.className = 'status-dot';
        statusDot.title = 'NetBox не настроен';
        statusText.textContent = 'NetBox: не настроен';
    }
}

// Загрузка конфигурации NetBox
function loadNetBoxConfig() {
    fetch('/api/netbox/config')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const config = data.config;
                if (config.url && config.token) {
                    netboxConfigured = true;
                    updateNetBoxStatus();
                }
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки конфигурации NetBox:', error);
        });
}

// Показать настройки NetBox
function showNetBoxConfig() {
    const modal = document.getElementById('netbox-config-modal');
    modal.style.display = 'flex';
    
    // Загружаем текущие настройки
    fetch('/api/netbox/config')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const config = data.config;
                document.getElementById('netbox-url').value = config.url || '';
                document.getElementById('netbox-token').value = config.token || '';
                document.getElementById('netbox-verify-ssl').checked = config.verify_ssl !== false;
            }
        });
}

// Скрыть настройки NetBox
function hideNetBoxConfig() {
    document.getElementById('netbox-config-modal').style.display = 'none';
}

// Сохранить настройки NetBox
function saveNetBoxConfig() {
    const config = {
        url: document.getElementById('netbox-url').value.trim(),
        token: document.getElementById('netbox-token').value.trim(),
        verify_ssl: document.getElementById('netbox-verify-ssl').checked
    };
    
    if (!config.url || !config.token) {
        showAlert('Заполните URL и токен NetBox', 'error');
        return;
    }
    
    showAlert('Сохранение настроек NetBox...', 'info');
    
    fetch('/api/netbox/save_config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Настройки NetBox сохранены', 'success');
            hideNetBoxConfig();
            loadDevices(); // Перезагружаем список устройств
        } else {
            showAlert(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка сохранения настроек NetBox:', error);
        showAlert('Ошибка сохранения настроек', 'error');
    });
}

// Тест соединения с NetBox
function testNetBoxConnection() {
    const config = {
        url: document.getElementById('netbox-url').value.trim(),
        token: document.getElementById('netbox-token').value.trim(),
        verify_ssl: document.getElementById('netbox-verify-ssl').checked
    };
    
    if (!config.url || !config.token) {
        showAlert('Заполните URL и токен NetBox', 'error');
        return;
    }
    
    showAlert('Проверка соединения с NetBox...', 'info');
    
    fetch(`/api/netbox/test?url=${encodeURIComponent(config.url)}&token=${encodeURIComponent(config.token)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Соединение с NetBox успешно установлено!', 'success');
            } else {
                showAlert(data.error || 'Не удалось подключиться к NetBox', 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка тестирования соединения:', error);
            showAlert('Ошибка тестирования соединения', 'error');
        });
}

// Обновление статуса устройства
function updateDeviceStatus(status, deviceName) {
    const statusDot = document.getElementById('connection-status');
    const statusText = document.getElementById('connection-text');
    const deviceNameSpan = document.getElementById('device-name');
    const disconnectBtn = document.getElementById('disconnect-btn');

    if (status === 'connected') {
        statusDot.className = 'status-dot connected';
        statusText.textContent = 'Подключено';
        deviceNameSpan.textContent = deviceName;
        disconnectBtn.style.display = 'block';
    } else {
        statusDot.className = 'status-dot';
        statusText.textContent = 'Не подключено';
        deviceNameSpan.textContent = 'Нет устройства';
        disconnectBtn.style.display = 'none';
    }
}

// обновляем функцию connectDevice()

function connectDevice(deviceName, username = '', password = '') {
    if (currentDevice === deviceName) {
        disconnectDevice();
        return;
    }

    showLoading('Подключение к ' + deviceName + '...');

    // Создаем URL с параметрами
    const params = new URLSearchParams();
    params.append('device', deviceName);
    if (username) params.append('username', username);
    if (password) params.append('password', password);

    fetch(`/api/connect?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Успешное подключение - показываем прогресс загрузки
                updateLoadingText('Успешное подключение!');
                currentDevice = deviceName;
                updateDeviceStatus('connected', deviceName);
                
                // Загружаем данные по очереди с обновлением статуса
                setTimeout(() => {
                    updateLoadingText('Загрузка дерева очередей...');
                    loadQueueTree();
                }, 300);
                
                setTimeout(() => {
                    updateLoadingText('Загрузка списка очередей...');
                    loadAllQueues();
                }, 600);
                
                setTimeout(() => {
                    updateLoadingText('Загрузка DHCP пулов и абонентов...');
                    loadDhcpPools(false); // Не скрывать спиннер автоматически
                }, 900);
                
                setTimeout(() => {
                    hideLoading();
                    showAlert(data.message, 'success');
                    // Очищаем поисковую строку устройств
                    const searchInput = document.getElementById('device-search');
                    if (searchInput) {
                        searchInput.value = '';
                    }
                    const clearBtn = document.getElementById('search-clear-btn');
                    if (clearBtn) {
                        clearBtn.style.display = 'none';
                    }
                    // Перерисовываем список (показываем кнопку "Отключить")
                    loadDevices();
                }, 1500);
                
            } else if (data.requires_credentials) {
                hideLoading();
                // Требуются учетные данные (логин и пароль)
                askForCredentials(deviceName, data.saved_username);
            } else {
                hideLoading();
                showErrorModal(data.error || 'Ошибка подключения');
            }
        })
        .catch(error => {
            hideLoading();
            console.error('Ошибка подключения:', error);
            showErrorModal('Ошибка подключения');
        });
}

// В app.js - создаем новую функцию askForCredentials()

function askForCredentials(deviceName, savedUsername = '') {
    // Если сохраненного логина нет, используем дефолтный (nur001)
    const defaultUsername = savedUsername || 'nur001';
    
    // Создаем модальное окно для ввода ЛОГИНА И ПАРОЛЯ
    const modal = document.createElement('div');
    modal.id = 'credentials-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
    `;
    
    modal.innerHTML = `
        <div style="background: linear-gradient(145deg, #2c2c2c, #262626);
                    padding: 25px;
                    border-radius: 8px;
                    width: 400px;
                    border: 1px solid #3a3a3a;
                    color: #d8d9da;">
            <h3 style="margin-bottom: 15px; color: #ffffff;">
                <i class="fas fa-key"></i> Введите учетные данные
            </h3>
            <p style="margin-bottom: 20px; font-size: 14px;">
                Для устройства: <strong>${deviceName}</strong>
            </p>
            
            <!-- ПОЛЕ ДЛЯ ЛОГИНА -->
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-size: 14px;">
                    <i class="fas fa-user"></i> Имя пользователя:
                </label>
                <input type="text" 
                       id="username-input" 
                       value="${defaultUsername}" 
                       placeholder="Имя пользователя" 
                       style="width: 100%; padding: 10px; border-radius: 4px; 
                              background: #1a1d23; border: 1px solid #3a3a3a; 
                              color: #ffffff;">
            </div>
            
            <!-- ПОЛЕ ДЛЯ ПАРОЛЯ -->
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 5px; font-size: 14px;">
                    <i class="fas fa-lock"></i> Пароль:
                </label>
                <input type="password" 
                       id="password-input" 
                       placeholder="Пароль устройства" 
                       style="width: 100%; padding: 10px; border-radius: 4px; 
                              background: #1a1d23; border: 1px solid #3a3a3a; 
                              color: #ffffff;">
            </div>
            
            <!-- ЧЕКБОКС ДЛЯ ЗАПОМИНАНИЯ -->
            <div style="margin-bottom: 15px;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="checkbox" id="remember-credentials" checked>
                    <span>Запомнить учетные данные</span>
                </label>
            </div>
            
            <!-- КНОПКИ -->
            <div style="display: flex; gap: 10px;">
                <button onclick="submitCredentials('${deviceName}')" 
                        style="flex: 1; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                               color: white; border: none; padding: 10px; border-radius: 4px;
                               cursor: pointer;">
                    <i class="fas fa-check"></i> Подключиться
                </button>
                <button onclick="cancelCredentials()" 
                        style="flex: 1; background: #4a4a4a; color: white; 
                               border: none; padding: 10px; border-radius: 4px;
                               cursor: pointer;">
                    <i class="fas fa-times"></i> Отмена
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById('username-input').focus();
    
    // Авто-фокус на пароле после ввода логина
    document.getElementById('username-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('password-input').focus();
        }
    });
    
    // Отправка формы по Enter в поле пароля
    document.getElementById('password-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            submitCredentials(deviceName);
        }
    });
}

// создаем новую функцию submitCredentials()

function submitCredentials(deviceName) {
    const usernameInput = document.getElementById('username-input');
    const passwordInput = document.getElementById('password-input');
    const rememberCheckbox = document.getElementById('remember-credentials');
    
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    
    if (!username || !password) {
        showAlert('Введите логин и пароль', 'error');
        return;
    }
    
    // Закрываем модальное окно
    const modal = document.getElementById('credentials-modal');
    if (modal) modal.remove();
    
    showAlert('Подключение...', 'info');
    
    // Отправляем запрос с логином и паролем
    connectDevice(deviceName, username, password);
    
    // Сообщение о запоминании данных
    if (rememberCheckbox.checked) {
        // Данные сохранятся автоматически на сервере при успешном подключении
        showAlert('Учетные данные будут сохранены', 'info');
    }
}

// В app.js - создаем новую функцию cancelCredentials()

function cancelCredentials() {
    const modal = document.getElementById('credentials-modal');
    if (modal) modal.remove();
}

// Функция для отключения
function disconnectDevice() {
    if (!currentDevice) {
        showAlert('Нет активных подключений', 'info');
        return;
    }

    showLoading('Отключение...');

    fetch('/api/disconnect')
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                currentDevice = null;
                document.getElementById('connection-status').className = 'status-dot';
                document.getElementById('connection-text').textContent = 'Не подключено';
                document.getElementById('device-name').textContent = '';
                document.getElementById('queue-stats').textContent = '';
                document.getElementById('disconnect-btn').style.display = 'none';

                showAlert(data.message, 'info');

                // Очищаем дерево очередей
                document.getElementById('queue-tree-v2').innerHTML = '';

                // Очищаем select с очередями
                resetQueueSelect();

                // Очищаем список абонентов
                clearSubscribersList();

                loadDevices();
            }
        })
        .catch(error => {
            hideLoading();
            console.error('Ошибка отключения:', error);
            showAlert('Ошибка отключения', 'error');
        });
}

// Сохранение устройства
function saveDevice() {
    const deviceData = {
        name: document.getElementById('device-name-input').value.trim(),
        ip: document.getElementById('device-ip').value.trim(),
        port: parseInt(document.getElementById('device-port').value) || 8728,
        username: document.getElementById('device-username').value.trim() || 'admin',
        password: document.getElementById('device-password').value,
        description: document.getElementById('device-description').value.trim(),
        savePassword: document.getElementById('save-password').checked
    };

    if (!deviceData.name || !deviceData.ip) {
        showAlert('Заполните имя и IP адрес', 'error');
        return;
    }

    fetch('/api/add_device', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(deviceData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            hideAddDeviceForm();
            loadDevices();

            document.getElementById('device-name-input').value = '';
            document.getElementById('device-ip').value = '';
            document.getElementById('device-password').value = '';
            document.getElementById('device-description').value = '';
        } else {
            showAlert(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка сохранения:', error);
        showAlert('Ошибка сохранения', 'error');
    });
}

// Загрузка настроек
function loadSettings() {
    const config = {
        auto_save_password: localStorage.getItem('auto_save_password') === 'true',
        default_username: localStorage.getItem('default_username') || 'admin'
    };

    document.getElementById('auto-save-password').checked = config.auto_save_password;
    document.getElementById('default-username').value = config.default_username;
}

// Сохранение настроек
function saveSettings() {
    const settings = {
        auto_save_password: document.getElementById('auto-save-password').checked,
        default_username: document.getElementById('default-username').value
    };

    localStorage.setItem('auto_save_password', settings.auto_save_password);
    localStorage.setItem('default_username', settings.default_username);

    fetch('/api/save_config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Настройки сохранены', 'success');
        } else {
            showAlert(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка сохранения настроек:', error);
        showAlert('Ошибка сохранения настроек', 'error');
    });
}

// Проверка DHCP
function checkDHCP() {
    const ip = document.getElementById('ip-address').value.trim();
    if (!ip) {
        showAlert('Введите IP адрес', 'error');
        return;
    }

    fetch(`/api/find_dhcp_lease?ip=${encodeURIComponent(ip)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.found) {
                    showAlert(`DHCP найден: ${data.lease.ip} (${data.lease.status})`, 'info');
                    if (data.lease.mac) {
                        document.getElementById('mac-address').value = data.lease.mac;
                    }
                } else {
                    showAlert('DHCP не найден', 'info');
                }
            } else {
                showAlert(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка проверки DHCP:', error);
            showAlert('Ошибка проверки DHCP', 'error');
        });
}

// Поиск очередей для IP (с фильтрацией платных очередей на клиенте)
function findQueues() {
    const ip = document.getElementById('ip-address').value.trim();
    if (!ip) {
        showAlert('Введите IP адрес', 'error');
        return;
    }

    if (!currentDevice) {
        showAlert('Сначала подключитесь к устройству', 'error');
        return;
    }

    fetch(`/api/find_queues?ip=${encodeURIComponent(ip)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('queue-select');
                select.innerHTML = '<option value="">-- Не выбрана --</option>';

                if (data.existing && data.existing.length > 0) {
                    showAlert(`IP уже находится в очередях: ${data.existing.join(', ')}`, 'warning');
                }

                if (data.queues && data.queues.length > 0) {
                    // ФИЛЬТРАЦИЯ НА КЛИЕНТЕ: исключаем очереди, начинающиеся с "paid"
                    const freeQueues = data.queues.filter(queue => {
                        const queueName = queue.name.toLowerCase();
                        return !queueName.startsWith('paid');
                    });

                    if (freeQueues.length > 0) {
                        freeQueues.forEach(queue => {
                            const option = document.createElement('option');
                            option.value = queue.name;
                            option.textContent = `${queue.name} (${queue.ip_count} IP)`;
                            select.appendChild(option);
                        });
                        
                        const paidCount = data.queues.length - freeQueues.length;
                        let message = `Найдено ${freeQueues.length} бесплатных очередей`;
                        if (paidCount > 0) {
                            message += ` (${paidCount} платных исключено)`;
                        }
                        showAlert(message, 'success');
                    } else {
                        showAlert('Бесплатных очередей не найдено', 'info');
                    }
                } else {
                    showAlert('Подходящих очередей не найдено', 'info');
                }
            } else {
                showAlert(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка поиска очередей:', error);
            showAlert('Ошибка поиска очередей', 'error');
        });
}

// Функция для добавления сотрудника с автоматическим поиском MAC адреса
// и проверкой принадлежности IP к сетям микротика
function addEmployee() {
    // Получаем значения из формы
    const fullName = document.getElementById('full-name').value.trim();      // Имя и фамилия сотрудника
    const position = document.getElementById('position').value.trim();       // Должность сотрудника
    const ip = document.getElementById('ip-address').value.trim();          // IP адрес сотрудника
    const manualMac = document.getElementById('mac-address').value.trim();   // MAC адрес сотрудника (может быть пустым)
    const internetAccess = document.getElementById('internet-access').checked; // Доступ в интернет
    
    // Получаем ВСЕ выбранные очереди (ОПЦИОНАЛЬНО)
    const select = document.getElementById('queue-select');
    const selectedQueues = Array.from(select.selectedOptions)
        .map(option => option.value)
        .filter(value => value && value !== "-- Нет бесплатных очередей --" && value !== "-- Загрузка очередей...");

    // Проверка заполнения обязательных полей (очереди НЕ обязательны)
    if (!fullName || !position || !ip) {
        showAlert('Заполните обязательные поля (ФИО, Должность, IP)', 'error');
        return;
    }

    // Проверка подключения к устройству
    if (!currentDevice) {
        showAlert('Сначала подключитесь к устройству', 'error');
        return;
    }

    // Элемент для показа результатов
    const resultsDiv = document.getElementById('employee-results');
    resultsDiv.innerHTML = '<div class="toast toast-info">Проверяем IP и MAC адрес...</div>';

    // Показываем спиннер
    showLoading('Добавление сотрудника...');

    // ШАГ 1: Проверка принадлежности IP к сетям микротика
    
    // Сначала делаем проверку IP
    fetch(`/api/check_ip?ip=${encodeURIComponent(ip)}`)
        .then(response => response.json())
        .then(ipCheckData => {
            if (!ipCheckData.success) {
                // IP не принадлежит сетям микротика
                hideLoading();
                showAlert(ipCheckData.error || 'IP не принадлежит сетям микротика', 'error');
                resultsDiv.innerHTML = `
                    <div class="toast toast-error">
                        ❌ ${ipCheckData.error || 'IP не принадлежит сетям микротика'}
                    </div>
                `;
                return;
            }
            
            // ШАГ 2: Получаем текущий MAC из DHCP
            fetch(`/api/find_dhcp_lease?ip=${encodeURIComponent(ip)}`)
                .then(response => response.json())
                .then(dhcpData => {
                    let finalMac;

                    if (dhcpData.lease && dhcpData.lease['mac-address']) {  // Обращаемся к полю mac-address
                        // Нашли текущий MAC в DHCP - используем его
                        finalMac = dhcpData.lease['mac-address'];
                        document.getElementById('mac-address').value = finalMac;
                    } else if (manualMac) {
                        // Пользователь вручную заполнил MAC
                        finalMac = manualMac;
                    } else {
                        // Ни DHCP, ни вручную MAC не указаны
                        hideLoading();
                        resultsDiv.innerHTML = `
                            <div class="toast toast-warning">
                                👉 MAC адрес не найден в DHCP. Укажите MAC адрес вручную.
                            </div>
                        `;
                        return;
                    }

                    // Готовые данные для отправки
                    const dataToSend = {
                        full_name: fullName,
                        position: position,
                        ip: ip,
                        mac: finalMac,
                        internet_access: internetAccess,
                        queues: selectedQueues // Может быть пустым массивом
                    };

                    // Отправляем данные на сервер
                    fetch('/api/add_employee', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(dataToSend)
                    })
                    .then(response => response.json())
                    .then(result => {
                        hideLoading();
                        if (result.success) {
                            let successMessage = `Сотрудник ${fullName} успешно добавлен`;
                            
                            // Добавляем информацию об очередях в сообщение
                            if (selectedQueues.length > 0) {
                                successMessage += ` в ${selectedQueues.length} очередь(ей): ${selectedQueues.join(', ')}`;
                            } else {
                                successMessage += ' (без ограничений очередей)';
                            }
                            
                            showAlert(successMessage, 'success');
                            resultsDiv.innerHTML = `
                                <div class="toast toast-success">
                                    ✅ ${successMessage}
                                    ${result.details_list ? '<div style="margin-top: 10px; font-size: 12px;">' + 
                                      result.details_list.join('<br>') + '</div>' : ''}
                                </div>
                            `;
                            
                            // Обновляем дерево очередей, только если сотрудник был добавлен в очередь
                            if (selectedQueues.length > 0 && result.details && result.details.queues) {
                                const successfulQueues = result.details.queues.filter(q => q.success);
                                if (successfulQueues.length > 0) {
                                    loadQueueTree();
                                }
                            }
                            
                            // Сбрасываем значения формы
                            resetEmployeeForm();
                            
                        } else {
                            let message = result.message || 'Ошибка добавления сотрудника';
                            showAlert(message, 'error');
                            resultsDiv.innerHTML = `
                                <div class="toast toast-error">
                                    ❌ ${message}
                                    ${result.details_list ? '<div style="margin-top: 10px; font-size: 12px;">' + 
                                      result.details_list.join('<br>') + '</div>' : ''}
                                </div>
                            `;
                        }
                    })
                    .catch(error => {
                        hideLoading();
                        console.error('Ошибка отправки данных:', error);
                        showAlert('Ошибка отправки данных', 'error');
                        resultsDiv.innerHTML = '';
                    });
                })
                .catch(error => {
                    hideLoading();
                    console.error('Ошибка проверки DHCP:', error);
                    showAlert('Ошибка проверки DHCP', 'error');
                    resultsDiv.innerHTML = '';
                });
        })
        .catch(error => {
            hideLoading();
            console.error('Ошибка проверки IP:', error);
            showAlert('Ошибка проверки IP', 'error');
            resultsDiv.innerHTML = '';
        });
}

// Функция для сброса формы сотрудника
function resetEmployeeForm() {
    document.getElementById('full-name').value = "";                // Имя и фамилия сотрудника
    document.getElementById('position').value = "";                 // Должность сотрудника
    document.getElementById('ip-address').value = "";               // IP адрес сотрудника
    document.getElementById('mac-address').value = "";              // MAC адрес сотрудника
    document.getElementById('internet-access').checked = false;     // Доступ в интернет
    
    // Очищаем выбор очередей
    const select = document.getElementById('queue-select');
    if (select) {
        Array.from(select.options).forEach(option => {
            option.selected = false;
        });
        updateSelectedQueuesCount();
    }
}

// Отправка данных сотрудника на сервер (старая версия, оставлена для совместимости)
function sendEmployeeData(employeeData, resultsDiv) {
    resultsDiv.innerHTML = '<div class="toast toast-info">Добавляем сотрудника...</div>';

    fetch('/api/add_employee', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(employeeData)
    })
    .then(response => response.json())
    .then(data => {
        resultsDiv.innerHTML = '';

        if (data.success || data.results) {
            let html = '<div class="result-item success">✅ Сотрудник добавлен</div>';

            if (data.results) {
                for (const [key, value] of Object.entries(data.results)) {
                    const resultText = {
                        'dhcp': 'DHCP запись',
                        'arp': 'ARP запись',
                        'queue': 'Очередь',
                        'firewall': 'Firewall правило'
                    }[key] || key;

                    html += `<div class="result-item ${value ? 'success' : 'error'}">
                        ${value ? '✅' : '❌'} ${resultText}
                    </div>`;
                }
            }

            resultsDiv.innerHTML = html;

            // Очищаем форму
            resetEmployeeForm();

            // Обновляем дерево очередей
            loadQueueTree();
        } else {
            showAlert(data.error || 'Ошибка добавления', 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка добавления:', error);
        showAlert('Ошибка добавления сотрудника', 'error');
    });
}


// Отправка данных сотрудника на сервер
function sendEmployeeData(employeeData, resultsDiv) {
    resultsDiv.innerHTML = '<div class="toast toast-info">Добавляем сотрудника...</div>';

    fetch('/api/add_employee', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(employeeData)
    })
    .then(response => response.json())
    .then(data => {
        resultsDiv.innerHTML = '';

        if (data.success || data.results) {
            let html = '<div class="result-item success">✅ Сотрудник добавлен</div>';

            if (data.results) {
                for (const [key, value] of Object.entries(data.results)) {
                    const resultText = {
                        'dhcp': 'DHCP запись',
                        'arp': 'ARP запись',
                        'queue': 'Очередь',
                        'firewall': 'Firewall правило'
                    }[key] || key;

                    html += `<div class="result-item ${value ? 'success' : 'error'}">
                        ${value ? '✅' : '❌'} ${resultText}
                    </div>`;
                }
            }

            resultsDiv.innerHTML = html;

            // Очищаем форму
            document.getElementById('full-name').value = '';
            document.getElementById('position').value = '';
            document.getElementById('ip-address').value = '';
            document.getElementById('mac-address').value = '';
            document.getElementById('internet-access').checked = false;
            document.getElementById('queue-select').value = '';

            // Обновляем дерево очередей
            loadQueueTree();
        } else {
            showAlert(data.error || 'Ошибка добавления', 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка добавления:', error);
        showAlert('Ошибка добавления сотрудника', 'error');
    });
}

// ========== НОВЫЕ ФУНКЦИИ ДЛЯ ДЕРЕВА ОЧЕРЕДЕЙ ==========

// Функция для рекурсивной фильтрации платных очередей
function filterPaidQueuesRecursive(nodes) {
    const filtered = [];
    let paidCount = 0;
    
    nodes.forEach(node => {
        // Пропускаем платные очереди (начинающиеся с "paid")
        if (node.name.toLowerCase().startsWith('paid')) {
            paidCount++;
            return;
        }
        
        const newNode = { ...node };
        
        // Рекурсивно фильтруем детей
        if (newNode.children && newNode.children.length > 0) {
            const childResult = filterPaidQueuesRecursive(newNode.children);
            newNode.children = childResult.filtered;
            paidCount += childResult.paidCount;
        }
        
        filtered.push(newNode);
    });
    
    return { filtered, paidCount };
}

// Загрузка дерева очередей с фильтрацией платных на клиенте
function loadQueueTree() {
    if (!currentDevice) {
        showAlert('Сначала подключитесь к устройству', 'error');
        return;
    }

    fetch('/api/tree')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // ФИЛЬТРУЕМ ПЛАТНЫЕ ОЧЕРЕДИ НА КЛИЕНТЕ
                const result = filterPaidQueuesRecursive(data.tree);
                
                queueTreeData = result.filtered;
                queueTreeFiltered = [...queueTreeData];
                
                // Сбрасываем состояние развернутости
                queueTreeExpanded = {};
                
                // Обновляем статистику
                updateQueueTreeStats(result.filtered, result.paidCount);
                
                // Отрисовываем дерево КАК ЕСТЬ (без перестройки)
                renderQueueTree(queueTreeFiltered);
                
                // Обновляем глобальную статистику в шапке
                if (data.stats) {
                    let statsText = `Очередей: ${result.filtered.length} (вкл: ${result.filtered.filter(q => q.enabled).length})`;
                    if (result.paidCount > 0) {
                        statsText += ` (${result.paidCount} платных скрыто)`;
                    }
                    document.getElementById('queue-stats').textContent = statsText;
                }
            } else {
                showAlert(data.error, 'error');
                showEmptyQueueTree();
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки дерева:', error);
            showAlert('Ошибка загрузки дерева очередей', 'error');
            showEmptyQueueTree();
        });
}

// Обновление статистики дерева
function updateQueueTreeStats(tree, paidCount = 0) {
    const totalQueues = tree.length;
    const enabledQueues = tree.filter(q => q.enabled).length;
    let totalIPs = 0;
    
    // Считаем общее количество IP
    function countIPs(nodes) {
        nodes.forEach(node => {
            totalIPs += node.ip_count || 0;
            if (node.children && node.children.length > 0) {
                countIPs(node.children);
            }
        });
    }
    countIPs(tree);
    
    let statsText = `${totalQueues} очередей • ${enabledQueues} вкл • ${totalIPs} IP`;
    if (paidCount > 0) {
        statsText += ` • ${paidCount} платных скрыто`;
    }
    
    document.getElementById('queue-tree-stats').textContent = statsText;
}

// Отрисовка дерева очередей КАК ЕСТЬ (без перестройки)
function renderQueueTree(nodes, level = 0, parentName = '') {
    const container = document.getElementById('queue-tree-v2');
    
    if (!nodes || nodes.length === 0) {
        showEmptyQueueTree();
        return;
    }
    
    container.innerHTML = '';
    
    // Создаем табличную структуру
    const table = document.createElement('div');
    table.style.display = 'table';
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    
    // Отрисовываем каждый узел рекурсивно
    function renderNodes(nodes, level, parentName) {
        nodes.forEach(node => {
            // Проверяем, развернут ли родитель
            if (parentName && queueTreeExpanded[parentName] === false) {
                return;
            }
            
            // Рендерим строку узла
            renderTreeNodeRow(node, table, level, parentName);
            
            // Рекурсивно рендерим детей (если узел развернут)
            if (node.children && node.children.length > 0 && queueTreeExpanded[node.name] !== false) {
                renderNodes(node.children, level + 1, node.name);
            }
        });
    }
    
    renderNodes(nodes, 0, '');
    container.appendChild(table);
}

// Функция для отрисовки строки узла дерева
function renderTreeNodeRow(node, table, level, parentName = '') {
    const row = document.createElement('div');
    row.style.display = 'table-row';
    
    // Ячейка с деревом и именем
    const nameCell = document.createElement('div');
    nameCell.style.display = 'table-cell';
    nameCell.style.verticalAlign = 'middle';
    nameCell.style.padding = level === 0 ? '10px 0' : '8px 0';
    nameCell.style.borderBottom = level === 0 ? '2px solid #dee2e6' : '1px solid #eee';
    
    // Проверяем, развернут ли узел
    const isExpanded = queueTreeExpanded[node.name] !== false;
    const hasChildren = node.children && node.children.length > 0;
    
    // Создаем элемент очереди
    const nodeDiv = document.createElement('div');
    nodeDiv.className = `queue-item-v2 ${node.enabled ? '' : 'disabled'}`;
    nodeDiv.style.display = 'flex';
    nodeDiv.style.alignItems = 'center';
    nodeDiv.style.cursor = hasChildren ? 'pointer' : 'default';
    
    // Отступ для уровня вложенности
    const indent = document.createElement('span');
    indent.style.width = `${level * 20 + 15}px`;
    indent.style.display = 'inline-block';
    nodeDiv.appendChild(indent);

    // Индикатор развертывания (только если есть дети)
    if (hasChildren) {
        const expandIcon = document.createElement('i');
        expandIcon.className = `fas ${isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'}`;
        expandIcon.style.cursor = 'pointer';
        expandIcon.style.fontSize = level === 0 ? '12px' : '11px';
        expandIcon.style.color = level === 0 ? '#3498db' : '#666';
        expandIcon.style.marginRight = '8px';
        expandIcon.style.width = '15px';
        expandIcon.style.textAlign = 'center';
        expandIcon.onclick = (e) => {
            e.stopPropagation();
            toggleQueueNode(node.name);
        };
        nodeDiv.appendChild(expandIcon);
    } else {
        const spacer = document.createElement('span');
        spacer.style.width = '15px';
        spacer.style.display = 'inline-block';
        nodeDiv.appendChild(spacer);
    }

    // Иконка узла (разная для корневых и дочерних)
    const icon = document.createElement('i');
    if (level === 0) {
        icon.className = 'fas fa-project-diagram';
        icon.style.color = '#3498db';
    } else {
        icon.className = 'fas fa-code-branch';
        icon.style.color = '#7f8c8d';
    }
    icon.style.fontSize = level === 0 ? '14px' : '12px';
    icon.style.marginRight = '8px';
    nodeDiv.appendChild(icon);

    // Имя очереди
    const nameSpan = document.createElement('span');
    nameSpan.className = 'queue-name';
    nameSpan.textContent = node.name;
    nameSpan.style.fontWeight = level === 0 ? 'bold' : 'normal';
    nameSpan.style.color = level === 0 ? '#2c3e50' : '#34495e';
    nameSpan.style.fontSize = level === 0 ? '15px' : '14px';
    nameSpan.style.marginRight = '15px';
    nodeDiv.appendChild(nameSpan);

    // Иконка комментария (если есть комментарий)
    if (node.comment) {
        const commentIcon = document.createElement('i');
        commentIcon.className = 'fas fa-comment-alt';
        commentIcon.style.color = '#7f8c8d';
        commentIcon.style.fontSize = level === 0 ? '11px' : '10px';
        commentIcon.style.marginRight = '10px';
        commentIcon.style.cursor = 'help';
        commentIcon.title = `Комментарий: ${node.comment}`;
        commentIcon.onclick = (e) => {
            e.stopPropagation();
            showAlert(node.comment, 'info');
        };
        nodeDiv.appendChild(commentIcon);
    }

    // Пустое пространство для выравнивания
    const spacer = document.createElement('div');
    spacer.style.flex = '1';
    nodeDiv.appendChild(spacer);

    // Статус
    const statusDiv = document.createElement('div');
    statusDiv.className = `queue-status ${node.enabled ? '' : 'disabled'}`;
    statusDiv.title = node.enabled ? 'Включена' : 'Выключена';
    statusDiv.style.width = level === 0 ? '14px' : '12px';
    statusDiv.style.height = level === 0 ? '14px' : '12px';
    statusDiv.style.borderRadius = '50%';
    statusDiv.style.backgroundColor = node.enabled ? '#2ecc71' : '#e74c3c';
    statusDiv.style.border = `${level === 0 ? '2px' : '1px'} solid ${node.enabled ? '#27ae60' : '#c0392b'}`;
    statusDiv.style.marginLeft = 'auto';
    nodeDiv.appendChild(statusDiv);

    if (hasChildren) {
        nodeDiv.onclick = () => {
            toggleQueueNode(node.name);
        };
    }

    nameCell.appendChild(nodeDiv);
    
    // Ячейка TARGET
    const targetCell = document.createElement('div');
    targetCell.style.display = 'table-cell';
    targetCell.style.verticalAlign = 'middle';
    targetCell.style.padding = level === 0 ? '10px 10px' : '8px 10px';
    targetCell.style.borderBottom = level === 0 ? '2px solid #dee2e6' : '1px solid #eee';
    targetCell.style.width = '200px';
    targetCell.style.minWidth = '150px';
    
    let targetText = '';
    if (node.short_target && node.short_target !== 'none') {
        targetText = node.short_target;
    } else if (node.target && Array.isArray(node.target) && node.target.length > 0) {
        targetText = node.target[0];
        if (node.target.length > 1) {
            targetText += ` +${node.target.length - 1}`;
        }
    }
    
    if (targetText) {
        const targetDiv = document.createElement('div');
        targetDiv.className = 'queue-target';
        
        let displayTarget = targetText;
        const maxLength = level === 0 ? 25 : 20;
        if (displayTarget.length > maxLength) {
            displayTarget = displayTarget.substring(0, maxLength - 3) + '...';
        }
        
        targetDiv.textContent = displayTarget;
        targetDiv.title = `TARGET: ${targetText}`;
        targetDiv.style.backgroundColor = '#e8f4fd';
        targetDiv.style.color = '#2980b9';
        targetDiv.style.padding = level === 0 ? '5px 10px' : '4px 8px';
        targetDiv.style.borderRadius = '4px';
        targetDiv.style.fontSize = level === 0 ? '12px' : '11px';
        targetDiv.style.fontFamily = 'monospace';
        targetDiv.style.border = '1px solid #b3e0ff';
        targetDiv.style.whiteSpace = 'nowrap';
        targetDiv.style.overflow = 'hidden';
        targetDiv.style.textOverflow = 'ellipsis';
        targetDiv.style.maxWidth = '180px';
        targetCell.appendChild(targetDiv);
    }
    
    // Ячейка DST
    const dstCell = document.createElement('div');
    dstCell.style.display = 'table-cell';
    dstCell.style.verticalAlign = 'middle';
    dstCell.style.padding = level === 0 ? '10px 10px' : '8px 10px';
    dstCell.style.borderBottom = level === 0 ? '2px solid #dee2e6' : '1px solid #eee';
    dstCell.style.width = '200px';
    dstCell.style.minWidth = '150px';
    
    let dstText = '';
    if (node.dst && node.dst !== 'none') {
        dstText = node.dst;
    } else if (node.short_dst && node.short_dst !== 'none') {
        dstText = node.short_dst;
    }
    
    if (dstText) {
        const dstDiv = document.createElement('div');
        dstDiv.className = 'queue-dst';
        
        let displayDst = dstText;
        const maxLength = level === 0 ? 25 : 20;
        if (displayDst.length > maxLength) {
            displayDst = displayDst.substring(0, maxLength - 3) + '...';
        }
        
        dstDiv.textContent = displayDst;
        dstDiv.title = `DST: ${dstText}`;
        dstDiv.style.backgroundColor = '#f0f7ff';
        dstDiv.style.color = '#3498db';
        dstDiv.style.padding = level === 0 ? '5px 10px' : '4px 8px';
        dstDiv.style.borderRadius = '4px';
        dstDiv.style.fontSize = level === 0 ? '12px' : '11px';
        dstDiv.style.fontFamily = 'monospace';
        dstDiv.style.border = '1px solid #a8d4ff';
        dstDiv.style.whiteSpace = 'nowrap';
        dstDiv.style.overflow = 'hidden';
        dstDiv.style.textOverflow = 'ellipsis';
        dstDiv.style.maxWidth = '180px';
        dstCell.appendChild(dstDiv);
    }
    
    // Ячейка лимита скорости (с выравниванием по правому краю)
    const limitCell = document.createElement('div');
    limitCell.style.display = 'table-cell';
    limitCell.style.verticalAlign = 'middle';
    limitCell.style.padding = level === 0 ? '10px 10px' : '8px 10px';
    limitCell.style.borderBottom = level === 0 ? '2px solid #dee2e6' : '1px solid #eee';
    limitCell.style.textAlign = 'right';
    limitCell.style.width = '120px';
    limitCell.style.whiteSpace = 'nowrap';
    
    // Лимит скорости
    if (node.max_limit && node.max_limit !== '0/0') {
        const limitDiv = document.createElement('div');
        limitDiv.className = 'queue-limit';
        limitDiv.textContent = node.max_limit;
        limitDiv.title = 'Макс. скорость';
        limitDiv.style.backgroundColor = '#fef9e7';
        limitDiv.style.color = '#f39c12';
        limitDiv.style.padding = level === 0 ? '5px 10px' : '4px 8px';
        limitDiv.style.borderRadius = '4px';
        limitDiv.style.fontSize = level === 0 ? '12px' : '11px';
        limitDiv.style.border = '1px solid #f8c471';
        limitDiv.style.display = 'inline-block';
        limitCell.appendChild(limitDiv);
    }
    
    // Добавляем ячейки в строку
    row.appendChild(nameCell);
    row.appendChild(targetCell);
    row.appendChild(dstCell);
    row.appendChild(limitCell);
    
    table.appendChild(row);
}

// Переключение состояния узла (развернуть/свернуть)
function toggleQueueNode(queueName) {
    queueTreeExpanded[queueName] = !queueTreeExpanded[queueName];
    renderQueueTree(queueTreeFiltered);
}

// Развернуть все узлы
function expandAllQueues() {
    function expandNode(nodes) {
        nodes.forEach(node => {
            if (node.children && node.children.length > 0) {
                queueTreeExpanded[node.name] = true;
                expandNode(node.children);
            }
        });
    }
    expandNode(queueTreeFiltered);
    renderQueueTree(queueTreeFiltered);
}

// Свернуть все узлы
function collapseAllQueues() {
    function collapseNode(nodes) {
        nodes.forEach(node => {
            if (node.children && node.children.length > 0) {
                queueTreeExpanded[node.name] = false;
                collapseNode(node.children);
            }
        });
    }
    collapseNode(queueTreeFiltered);
    renderQueueTree(queueTreeFiltered);
}

// Фильтрация дерева по имени
function filterQueueTree(searchTerm) {
    if (!searchTerm.trim()) {
        queueTreeFiltered = [...queueTreeData];
        renderQueueTree(queueTreeFiltered);
        return;
    }
    
    const term = searchTerm.toLowerCase().trim();
    
    function filterNodes(nodes) {
        const filtered = [];
        
        nodes.forEach(node => {
            const matches = node.name.toLowerCase().includes(term) ||
                           (node.comment && node.comment.toLowerCase().includes(term));
            
            // Если узел совпадает или есть совпадающие дети
            let childMatches = [];
            if (node.children && node.children.length > 0) {
                childMatches = filterNodes(node.children);
            }
            
            if (matches || childMatches.length > 0) {
                const newNode = { ...node };
                if (childMatches.length > 0) {
                    newNode.children = childMatches;
                    // Разворачиваем узлы с совпадениями
                    queueTreeExpanded[node.name] = true;
                }
                filtered.push(newNode);
            }
        });
        
        return filtered;
    }
    
    queueTreeFiltered = filterNodes(queueTreeData);
    renderQueueTree(queueTreeFiltered);
}

// Показать пустое состояние дерева
function showEmptyQueueTree() {
    const container = document.getElementById('queue-tree-v2');
    container.innerHTML = `
        <div class="queue-tree-empty">
            <i class="fas fa-sitemap"></i>
            <p>${currentDevice ? 'Нет данных об очередях' : 'Подключитесь к устройству'}</p>
            ${currentDevice ? 
                '<button class="btn btn-primary mt-10" onclick="loadQueueTree()">' +
                '<i class="fas fa-sync-alt"></i> Загрузить дерево</button>' : 
                '<button class="btn btn-primary mt-10" onclick="switchTab(\'employee\')">' +
                '<i class="fas fa-plug"></i> Подключиться к устройству</button>'
            }
        </div>
    `;
}

// Проверка IP
function checkIP() {
    const ip = document.getElementById('check-ip').value.trim();
    if (!ip) {
        showAlert('Введите IP адрес', 'error');
        return;
    }

    if (!currentDevice) {
        showAlert('Сначала подключитесь к устройству', 'error');
        return;
    }

    const resultsDiv = document.getElementById('tools-results');
    resultsDiv.innerHTML = '<div class="alert alert-info">Проверяем...</div>';

    // Проверяем DHCP
    fetch(`/api/find_dhcp_lease?ip=${encodeURIComponent(ip)}`)
        .then(response => response.json())
        .then(dhcpData => {
            let html = '';

            if (dhcpData.success && dhcpData.found) {
                html += `<div class="result-item success">
                    ✅ DHCP найден: ${dhcpData.lease.ip} (${dhcpData.lease.status})
                    ${dhcpData.lease.mac ? `<br>MAC: ${dhcpData.lease.mac}` : ''}
                    ${dhcpData.lease.comment ? `<br>Комментарий: ${dhcpData.lease.comment}` : ''}
                </div>`;
            } else {
                html += `<div class="result-item error">❌ DHCP не найден</div>`;
            }

            // Проверяем очереди
            fetch(`/api/find_queues?ip=${encodeURIComponent(ip)}`)
                .then(response => response.json())
                .then(queueData => {
                    if (queueData.success) {
                        if (queueData.existing && queueData.existing.length > 0) {
                            html += `<div class="result-item warning">
                                ⚠️ Уже в очередях: ${queueData.existing.join(', ')}
                            </div>`;
                        }

                        if (queueData.queues && queueData.queues.length > 0) {
                            const freeQueues = queueData.queues.filter(queue => {
                                return !queue.name.toLowerCase().startsWith('paid');
                            });
                            
                            html += `<div class="result-item success">
                                ✅ Найдено ${freeQueues.length} бесплатных очередей
                            </div>`;
                        } else {
                            html += `<div class="result-item info">ℹ️ Бесплатных очередей не найдено</div>`;
                        }
                    }

                    resultsDiv.innerHTML = html;
                });
        })
        .catch(error => {
            console.error('Ошибка проверки IP:', error);
            showAlert('Ошибка проверки IP', 'error');
        });
}

// Toast уведомления
function showToast(message, type = 'info', duration = 5000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    
    toast.innerHTML = `
        <i class="toast-icon ${icons[type] || icons.info}"></i>
        <div class="toast-content">${message}</div>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
        <div class="toast-progress"></div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.animation = 'toastFadeOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }
    }, duration);
    
    toast.addEventListener('click', function(e) {
        if (!e.target.closest('.toast-close')) {
            this.style.animation = 'toastFadeOut 0.3s ease';
            setTimeout(() => this.remove(), 300);
        }
    });
    
    return toast;
}

// Алиас для обратной совместимости
function showAlert(message, type = 'info') {
    return showToast(message, type);
}

// Загружает ВСЕ очереди при подключении с группировкой по DST
function loadAllQueues() {
    if (!currentDevice) {
        console.log('loadAllQueues: Нет подключенного устройства');
        return;
    }

    const queueSelect = document.getElementById('queue-select');
    if (queueSelect) {
        queueSelect.innerHTML = '<option value="">-- Загрузка очередей... --</option>';
        queueSelect.disabled = true;
    }

    fetch('/api/find_queues')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.queues) {
                // ФИЛЬТРАЦИЯ НА КЛИЕНТЕ
                const freeQueues = data.queues.filter(queue => {
                    const queueName = queue.name.toLowerCase();
                    return !queueName.startsWith('paid');
                });
                
                updateQueueSelectWithGroups(freeQueues);
                
                const paidCount = data.queues.length - freeQueues.length;
                let message = `Загружено ${freeQueues.length} бесплатных очередей`;
                if (paidCount > 0) {
                    message += ` (${paidCount} платных исключено)`;
                }
                showAlert(message, 'success');
                
            } else {
                showAlert('Ошибка загрузки очередей', 'error');
                resetQueueSelect();
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки очередей:', error);
            showAlert('Ошибка соединения с сервером', 'error');
            resetQueueSelect();
        });
}

// Обновляет select с группировкой по DST
function updateQueueSelectWithGroups(queues) {
    const select = document.getElementById('queue-select');
    if (!select) return;
    
    select.innerHTML = '';
    
    if (queues.length === 0) {
        const option = document.createElement('option');
        option.value = "";
        option.textContent = "-- Нет бесплатных очередей --";
        select.appendChild(option);
        select.disabled = true;
        return;
    }
    
    // Группируем очереди по DST
    const queuesByDst = {};
    const queuesWithoutDst = [];
    
    queues.forEach(queue => {
        let dst = '';
        if (queue.dst && queue.dst !== 'none') {
            dst = queue.dst;
        } else if (queue.short_dst && queue.short_dst !== 'none') {
            dst = queue.short_dst;
        }
        
        if (dst) {
            if (!queuesByDst[dst]) {
                queuesByDst[dst] = [];
            }
            queuesByDst[dst].push(queue);
        } else {
            queuesWithoutDst.push(queue);
        }
    });
    
    // Создаем optgroup для каждой DST группы
    Object.keys(queuesByDst).forEach(dstName => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `DST: ${dstName}`;
        optgroup.className = 'queue-group-header';
        
        queuesByDst[dstName].forEach(queue => {
            const option = createQueueOption(queue, dstName);
            optgroup.appendChild(option);
        });
        
        select.appendChild(optgroup);
    });
    
    // Очереди без DST
    if (queuesWithoutDst.length > 0) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = "Без DST";
        optgroup.className = 'queue-group-header';
        
        queuesWithoutDst.forEach(queue => {
            const option = createQueueOption(queue, '');
            optgroup.appendChild(option);
        });
        
        select.appendChild(optgroup);
    }
    
    select.disabled = false;
    
    // Добавляем обработчик для подсчета выбранных
    select.addEventListener('change', updateSelectedQueuesCount);
    updateSelectedQueuesCount();

    //Выводим кастомный тултип
    //setTimeout(setupSimpleTooltips, 100);
    setupSimpleTooltips();
}

// Добавьте в updateQueueSelectWithGroups() после создания select:
select.addEventListener('mouseenter', function(e) {
    if (e.target.tagName === 'OPTION') {
        const option = e.target;
        setTimeout(() => {
            showCustomTooltip(option);
        }, 800);
    }
});

function showCustomTooltip(option) {
    // Удаляем старый тултип если есть
    const oldTooltip = document.getElementById('simple-queue-tooltip');
    if (oldTooltip) oldTooltip.remove();
    
    // Создаем новый
    const tooltip = document.createElement('div');
    tooltip.id = 'simple-queue-tooltip';
    tooltip.style.cssText = `
        position: fixed;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        max-width: 250px;
        z-index: 9999;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        white-space: pre-line;
        line-height: 1.5;
    `;
    
    // Используем тот же текст что в title
    tooltip.textContent = option.title;
    
    document.body.appendChild(tooltip);
    
    // Позиционируем возле курсора
    const rect = option.getBoundingClientRect();
    tooltip.style.left = (rect.right + 10) + 'px';
    tooltip.style.top = rect.top + 'px';
    
    // Удаляем через 3 секунды или при уходе мыши
    setTimeout(() => {
        tooltip.remove();
    }, 3000);
}

function createQueueOption(queue, dstName) {
    const option = document.createElement('option');
    option.value = queue.name;
    option.className = `queue-option ${queue.enabled ? 'enabled' : 'disabled'}`;
    
    // В селекторе имя очереди + иконка статуса
    const statusIcon = queue.enabled ? '🟢' : '🔴';
    option.textContent = `${statusIcon} ${queue.name}`;
    
    // Формируем HTML для тултипа (с переносами строк через <br>)
    let tooltipHTML = `<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; line-height: 1.5; color: #d8d9da;">`;
    tooltipHTML += `<div style="color: #3498db; font-weight: bold; margin-bottom: 8px;">📊 ${queue.name}</div>`;
    tooltipHTML += `<div style="border-bottom: 1px solid #3498db; margin-bottom: 10px; padding-bottom: 5px;"></div>`;
    
    tooltipHTML += `<div style="margin-bottom: 8px;">`;
    tooltipHTML += `<span style="color: ${queue.enabled ? '#2ecc71' : '#e74c3c'}; margin-right: 8px;">${queue.enabled ? '🟢' : '🔴'}</span>`;
    tooltipHTML += `<span>Статус: <strong>${queue.enabled ? 'ВКЛ' : 'ВЫКЛ'}</strong></span>`;
    tooltipHTML += `</div>`;
    
    if (queue.short_target && queue.short_target !== 'none') {
        tooltipHTML += `<div style="margin-bottom: 8px;">`;
        tooltipHTML += `<span style="color: #f39c12; margin-right: 8px;">🎯</span>`;
        tooltipHTML += `<span>TARGET:</span><br>`;
        tooltipHTML += `<div style="margin-left: 24px; margin-top: 4px; color: #ecf0f1; font-family: monospace; font-size: 12px;">${queue.short_target}</div>`;
        tooltipHTML += `</div>`;
    }
    
    if (queue.dst && queue.dst !== 'none') {
        tooltipHTML += `<div style="margin-bottom: 8px;">`;
        tooltipHTML += `<span style="color: #9b59b6; margin-right: 8px;">📍</span>`;
        tooltipHTML += `<span>DST:</span><br>`;
        tooltipHTML += `<div style="margin-left: 24px; margin-top: 4px; color: #ecf0f1; font-family: monospace; font-size: 12px;">${queue.dst}</div>`;
        tooltipHTML += `</div>`;
    }
    
    if (queue.max_limit && queue.max_limit !== '0/0') {
        tooltipHTML += `<div style="margin-bottom: 8px;">`;
        tooltipHTML += `<span style="color: #f1c40f; margin-right: 8px;">⚡</span>`;
        tooltipHTML += `<span>Лимит:</span><br>`;
        tooltipHTML += `<div style="margin-left: 24px; margin-top: 4px; color: #f1c40f; font-weight: bold;">${queue.max_limit}</div>`;
        tooltipHTML += `</div>`;
    }
    
    if (queue.ip_count > 0) {
        tooltipHTML += `<div style="margin-bottom: 8px;">`;
        tooltipHTML += `<span style="color: #e67e22; margin-right: 8px;">👥</span>`;
        tooltipHTML += `<span>IP адресов: <strong style="color: #e67e22;">${queue.ip_count}</strong></span>`;
        tooltipHTML += `</div>`;
    }
    
    if (queue.comment) {
        tooltipHTML += `<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #2c3e50;">`;
        tooltipHTML += `<span style="color: #3498db; margin-right: 8px;">💬</span>`;
        tooltipHTML += `<span style="font-style: italic; color: #7f8c8d;">${queue.comment}</span>`;
        tooltipHTML += `</div>`;
    }
    
    tooltipHTML += `</div>`;
    
    // Сохраняем HTML в data-атрибут
    option.setAttribute('data-tooltip-html', tooltipHTML);
    option.title = ''; // Пустой title убирает системный тултип
    
    return option;
}

// Обновляет счетчик выбранных очередей
function updateSelectedQueuesCount() {
    const select = document.getElementById('queue-select');
    const countElement = document.getElementById('selected-queues-count');
    
    if (!select || !countElement) return;
    
    const selectedCount = Array.from(select.selectedOptions).length;
    countElement.textContent = `Выбрано: ${selectedCount}`;
    
    // Меняем цвет в зависимости от количества
    if (selectedCount === 0) {
        countElement.style.background = '#95a5a6';
    } else if (selectedCount === 1) {
        countElement.style.background = '#3498db';
    } else {
        countElement.style.background = '#2ecc71';
    }
}

// Показывает превью выбранных очередей в стиле Grafana
function showQueuePreview() {
    const select = document.getElementById('queue-select');
    if (!select) return;
    
    const selectedOptions = Array.from(select.selectedOptions);
    
    if (selectedOptions.length === 0) {
        showAlert('Не выбрано ни одной очереди', 'warning');
        return;
    }
    
    // Создаем модальное окно в стиле Grafana
    let modal = document.getElementById('queue-preview-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'queue-preview-modal';
        modal.className = 'queue-preview-modal';
        modal.innerHTML = `
            <div class="queue-preview-content">
                <h2><i class="fas fa-eye"></i> Выбранные очереди</h2>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <span class="status-indicator status-active">
                        <i class="fas fa-check-circle"></i> Выбрано: ${selectedOptions.length}
                    </span>
                    <button class="btn btn-secondary" onclick="hideQueuePreview()" style="padding: 6px 12px;">
                        <i class="fas fa-times"></i> Закрыть
                    </button>
                </div>
                <div class="queue-preview-list" id="queue-preview-list"></div>
            </div>
        `;
        document.body.appendChild(modal);
        
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                hideQueuePreview();
            }
        });
    }
    
    // Заполняем список
    const list = document.getElementById('queue-preview-list');
    list.innerHTML = '';
    
    selectedOptions.forEach((option, index) => {
        const item = document.createElement('div');
        item.className = 'queue-preview-item';
        
        // Парсим HTML option для получения данных
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = option.innerHTML;
        
        const queueName = option.value;
        const statusDot = tempDiv.querySelector('.queue-status-dot');
        const isEnabled = statusDot.classList.contains('enabled');
        
        item.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <div class="queue-name">#${index + 1}. ${queueName}</div>
                    <div class="queue-details" style="margin-top: 8px;">
                        ${tempDiv.querySelector('.queue-details').innerHTML}
                    </div>
                </div>
                <span class="status-indicator ${isEnabled ? 'status-active' : 'status-inactive'}" 
                      style="font-size: 10px; padding: 3px 8px;">
                    <i class="fas fa-${isEnabled ? 'check' : 'times'}"></i>
                    ${isEnabled ? 'Активна' : 'Неактивна'}
                </span>
            </div>
            <div style="margin-top: 10px; font-size: 11px; color: #7f8c8d; opacity: 0.8;">
                <i class="fas fa-info-circle"></i> ${option.getAttribute('data-tooltip')?.replace(/\n/g, ' • ') || 'Нет дополнительной информации'}
            </div>
        `;
        
        list.appendChild(item);
    });
    
    modal.style.display = 'block';
}

// Скрывает превью очередей
function hideQueuePreview() {
    const modal = document.getElementById('queue-preview-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Поиск очередей для IP с подсказкой, но без автоматического выделения
function findQueues() {
    const ip = document.getElementById('ip-address').value.trim();
    if (!ip) {
        showAlert('Введите IP адрес', 'error');
        return;
    }

    if (!currentDevice) {
        showAlert('Сначала подключитесь к устройству', 'error');
        return;
    }

    fetch(`/api/find_queues?ip=${encodeURIComponent(ip)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.existing && data.existing.length > 0) {
                    showAlert(`Внимание: IP уже находится в очередях: ${data.existing.join(', ')}`, 'warning');
                }

                if (data.queues && data.queues.length > 0) {
                    // ФИЛЬТРАЦИЯ НА КЛИЕНТЕ
                    const freeQueues = data.queues.filter(queue => {
                        const queueName = queue.name.toLowerCase();
                        return !queueName.startsWith('paid');
                    });

                    if (freeQueues.length > 0) {
                        // Показываем найденные очереди, но НЕ выделяем автоматически
                        const paidCount = data.queues.length - freeQueues.length;
                        let message = `Найдено ${freeQueues.length} подходящих очередей`;
                        if (paidCount > 0) {
                            message += ` (${paidCount} платных исключено)`;
                        }
                        
                        // Предлагаем пользователю посмотреть очереди
                        const viewQueues = confirm(
                            `${message}\n\n` +
                            'Хотите посмотреть найденные очереди в селекторе?\n\n' +
                            'Примечание: Вы можете не выбирать очереди и использовать настройки по умолчанию.'
                        );
                        
                        if (viewQueues) {
                            // Прокручиваем к селектору очередей
                            const queueSelect = document.getElementById('queue-select');
                            if (queueSelect) {
                                queueSelect.focus();
                                showAlert('Найденные очереди доступны для выбора в списке', 'info');
                            }
                        }
                    } else {
                        showAlert('Бесплатных очередей не найдено', 'info');
                    }
                } else {
                    showAlert('Подходящих очередей не найдено', 'info');
                }
            } else {
                showAlert(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка поиска очередей:', error);
            showAlert('Ошибка поиска очереди', 'error');
        });
}

// Очищает выбранные очереди
function clearQueueSelection() {
    const select = document.getElementById('queue-select');
    if (select) {
        Array.from(select.options).forEach(option => {
            option.selected = false;
        });
        updateSelectedQueuesCount();
        showAlert('Выбор очередей очищен', 'info');
    }
}

// Обновляет select с очередями
function updateQueueSelect(queues) {
    const select = document.getElementById('queue-select');
    if (!select) return;
    
    select.innerHTML = '<option value="">-- Не выбрана --</option>';
    
    if (queues.length === 0) {
        select.innerHTML += '<option value="">-- Нет бесплатных очередей --</option>';
    } else {
        // НЕ СОРТИРУЕМ! Оставляем в естественном порядке как пришли с сервера
        // queues.sort((a, b) => a.name.localeCompare(b.name));
        
        queues.forEach(queue => {
            const option = document.createElement('option');
            option.value = queue.name;
            
            let displayText = queue.name;
            
            // Добавляем TARGET
            let targetText = '';
            if (queue.short_target && queue.short_target !== 'none') {
                targetText = queue.short_target;
            }
            
            let dstText = '';
            if (queue.dst && queue.dst !== 'none') {
                dstText = queue.dst;
            }
            
            if (targetText || dstText) {
                displayText += ' [';
                if (targetText) {
                    displayText += `T:${targetText}`;
                }
                if (targetText && dstText) {
                    displayText += ', ';
                }
                if (dstText) {
                    displayText += `D:${dstText}`;
                }
                displayText += ']';
            }
            
            // Добавляем количество IP (если есть)
            if (queue.ip_count > 0) {
                displayText += ` (${queue.ip_count} IP)`;
            }
            
            // Добавляем комментарий (если есть)
            if (queue.comment) {
                displayText += ` - ${queue.comment}`;
            }
            
            option.textContent = displayText;
            select.appendChild(option);
        });
    }
    
    select.disabled = false;
}

// Сбрасывает select
function resetQueueSelect() {
    const select = document.getElementById('queue-select');
    if (select) {
        select.innerHTML = '<option value="">-- Не подключено --</option>';
        select.disabled = true;
    }
}

function setupSimpleTooltips() {
    const select = document.getElementById('queue-select');
    if (!select) return;
    
    // Создаем кастомный тултип
    const tooltip = document.createElement('div');
    tooltip.id = 'custom-queue-tooltip';
    tooltip.style.cssText = `
        position: fixed;
        background: #1a1d23;
        border: 1px solid #3498db;
        border-radius: 6px;
        padding: 12px;
        max-width: 300px;
        z-index: 10000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        display: none;
        pointer-events: none;
    `;
    document.body.appendChild(tooltip);
    
    let hoverTimer;
    let mouseX = 0;
    let mouseY = 0;
    
    // Отслеживаем позицию мыши
    document.addEventListener('mousemove', function(e) {
        mouseX = e.clientX;
        mouseY = e.clientY;
        
        // Если тултип видим, обновляем его позицию
        if (tooltip.style.display === 'block') {
            positionTooltipAtMouse(tooltip);
        }
    });
    
    select.addEventListener('mouseover', function(e) {
        if (e.target.tagName === 'OPTION' && e.target.value) {
            const option = e.target;
            
            // Отменяем предыдущий таймер
            if (hoverTimer) clearTimeout(hoverTimer);
            
            // Запускаем новый таймер
            hoverTimer = setTimeout(() => {
                const tooltipHTML = option.getAttribute('data-tooltip-html');
                if (!tooltipHTML) return;
                
                // Вставляем HTML
                tooltip.innerHTML = tooltipHTML;
                tooltip.style.display = 'block';
                
                // Позиционируем относительно курсора мыши
                positionTooltipAtMouse(tooltip);
            }, 600); // Задержка 600ms
        }
    });
    
    select.addEventListener('mouseout', function() {
        if (hoverTimer) {
            clearTimeout(hoverTimer);
            hoverTimer = null;
        }
        tooltip.style.display = 'none';
    });
    
    function positionTooltipAtMouse(tooltipElement) {
        const tooltipWidth = tooltipElement.offsetWidth;
        const tooltipHeight = tooltipElement.offsetHeight;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        // Начальная позиция - справа от курсора
        let left = mouseX + 15;
        let top = mouseY + 15;
        
        // Если не помещается справа - показываем слева
        if (left + tooltipWidth > windowWidth - 10) {
            left = mouseX - tooltipWidth - 15;
        }
        
        // Если не помещается снизу - показываем сверху
        if (top + tooltipHeight > windowHeight - 10) {
            top = mouseY - tooltipHeight - 15;
        }
        
        // Устанавливаем позицию
        tooltipElement.style.left = left + 'px';
        tooltipElement.style.top = top + 'px';
    }
    
    // Скрываем при скролле
    window.addEventListener('scroll', function() {
        tooltip.style.display = 'none';
        if (hoverTimer) {
            clearTimeout(hoverTimer);
            hoverTimer = null;
        }
    });
}

// Обновляем функцию показа модалки для правильной инициализации кнопки
function showFreeIPs() {
    if (!currentDevice) {
        showAlert('Сначала подключитесь к устройству', 'error');
        return;
    }
    
    const modal = document.getElementById('ip-selector-modal');
    modal.style.display = 'flex';
    
    // Сохраняем текущее значение IP из поля ввода для отмены
    const currentIP = document.getElementById('ip-address').value.trim();
    window.originalIP = currentIP; // Сохраняем для возможности отмены
    
    // НЕ устанавливаем selectedIPInModal автоматически!
    // Пусть пользователь сам выберет или снимет выбор
    window.selectedIPInModal = null; // Начинаем с пустого значения
    window.selectedPoolInModal = '';
    
    // Показываем загрузку
    document.getElementById('free-ips-loading').style.display = 'block';
    document.getElementById('free-ips-content').style.display = 'none';
    document.getElementById('free-ips-error').style.display = 'none';
    
    // Настраиваем кнопку "Сохранить" - она активна, даже если нет выбора (чтобы очистить поле)
    const saveBtn = document.getElementById('use-ip-btn');
    saveBtn.disabled = false; // Всегда активна!
    saveBtn.innerHTML = `<i class="fas fa-save"></i> Сохранить`;
    
    // Загружаем свободные IP
    fetch('/api/free_ips')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderFreeIPs(data.free_ips, currentIP);
            } else {
                showFreeIPsError(data.error || 'Ошибка загрузки');
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки свободных IP:', error);
            showFreeIPsError('Ошибка соединения с сервером');
        });
}

// Отмена выбора IP
function cancelIPSelection() {
    // Восстанавливаем оригинальное значение IP
    document.getElementById('ip-address').value = window.originalIP || '';
    
    // Закрываем модальное окно
    hideIPSelector();
}

// Рендерит список свободных IP в стиле Grafana
function renderFreeIPs(freeIPs, currentIP = '') {
    const contentDiv = document.getElementById('free-ips-content');
    const loadingDiv = document.getElementById('free-ips-loading');
    const errorDiv = document.getElementById('free-ips-error');
    
    loadingDiv.style.display = 'none';
    errorDiv.style.display = 'none';
    contentDiv.style.display = 'block';
    
    if (!freeIPs || Object.keys(freeIPs).length === 0) {
        contentDiv.innerHTML = `
            <div class="ip-empty-state">
                <i class="fas fa-info-circle"></i>
                <p>Нет свободных IP адресов в DHCP пулах</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    let totalFree = 0;
    let totalPools = Object.keys(freeIPs).length;
    
    // Общая статистика
    Object.values(freeIPs).forEach(pool => {
        totalFree += pool.free_ips;
    });
    
// Проверяем, есть ли текущий IP в списке свободных и устанавливаем его как выбранный
if (currentIP) {
    for (const [poolName, poolData] of Object.entries(freeIPs)) {
        if (poolData.free_list && poolData.free_list.includes(currentIP)) {
            window.selectedIPInModal = currentIP; // Устанавливаем как выбранный
            window.selectedPoolInModal = poolName;
            break;
        }
    }
}
    
    html += `
        <div class="ip-stats-panel">
            <div class="ip-stats-header">
                <h4>
                    <i class="fas fa-chart-pie"></i> Общая статистика
                </h4>
                <span class="ip-stats-badge">
                    ${totalFree} свободных IP
                </span>
            </div>
            <div class="ip-stats-text">
                Найдено <strong>${totalFree}</strong> свободных IP адресов в <strong>${totalPools}</strong> пулах
            </div>
        </div>
        
        <div class="ip-pool-container">
    `;
    
    // Для каждого пула
    for (const [poolName, poolData] of Object.entries(freeIPs)) {
        html += `
            <div class="ip-pool-card">
                <div class="ip-pool-header">
                    <div class="ip-pool-title">
                        <i class="fas fa-database" style="color: var(--accent-secondary);"></i>
                        <span class="ip-pool-name">${poolName}</span>
                    </div>
                    <div class="ip-pool-stats">
                        <div class="ip-pool-stat">
                            <span class="stat-label">Всего:</span>
                            <span class="stat-value">${poolData.total_ips}</span>
                        </div>
                        <div class="ip-pool-stat">
                            <span class="stat-label">Используется:</span>
                            <span class="stat-value">${poolData.used_ips}</span>
                        </div>
                        <div class="ip-pool-stat">
                            <span class="stat-label" style="color: var(--success);">Свободно:</span>
                            <span class="stat-value" style="color: var(--success); font-weight: 700;">${poolData.free_ips}</span>
                        </div>
                    </div>
                </div>
                
                <div class="ip-pool-range">
                    <i class="fas fa-arrows-alt-h"></i>
                    <span>${poolData.ranges}</span>
                </div>
                
                <div class="ip-list-container">
        `;
        
        if (poolData.free_list && poolData.free_list.length > 0) {
            html += `<div class="ip-list-grid">`;
            
            poolData.free_list.forEach(ip => {
                // Проверяем, является ли этот IP выбранным в модалке
                const isSelected = window.selectedIPInModal === ip;
                
                html += `
                    <div class="ip-option ${isSelected ? 'selected' : ''}" 
                         onclick="selectIPInModal('${ip}', '${poolName}')"
                         data-ip="${ip}"
                         data-pool="${poolName}">
                        <div class="ip-address">${ip}</div>
                        <div class="ip-pool-label">${poolName}</div>
                        ${isSelected ? '<div class="ip-selected-indicator"><i class="fas fa-check"></i></div>' : ''}
                    </div>
                `;
            });
            
            html += `</div>`;
            
            if (poolData.has_more) {
                const moreCount = poolData.free_ips - poolData.free_list.length;
                html += `
                    <div style="text-align: center; margin-top: 15px; padding: 10px; background: var(--bg-card); border-radius: var(--border-radius); border: 1px solid var(--border-color);">
                        <i class="fas fa-ellipsis-h" style="color: var(--text-muted);"></i>
                        <span style="color: var(--text-muted); font-size: 12px; margin-left: 8px;">
                            И еще ${moreCount} свободных IP в этом пуле
                        </span>
                    </div>
                `;
            }
        } else {
            html += `
                <div class="ip-empty-state" style="padding: 30px 20px;">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Нет свободных IP в этом пуле</p>
                </div>
            `;
        }
        
        html += `
                </div>
            </div>
        `;
    }
    
    html += `</div>`;
    contentDiv.innerHTML = html;
    
    // Обновляем текст кнопки после рендеринга
    const saveBtn = document.getElementById('use-ip-btn');
    if (window.selectedIPInModal) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = `<i class="fas fa-save"></i> Сохранить ${window.selectedIPInModal}`;
    } else {
        saveBtn.disabled = true;
        saveBtn.innerHTML = `<i class="fas fa-save"></i> Сохранить`;
    }
}

// Показывает ошибку при загрузке свободных IP
function showFreeIPsError(message) {
    document.getElementById('free-ips-loading').style.display = 'none';
    document.getElementById('free-ips-content').style.display = 'none';
    
    const errorDiv = document.getElementById('free-ips-error');
    errorDiv.style.display = 'block';
    document.getElementById('free-ips-error-text').textContent = message;
}

// Выбирает IP в модальном окне
function selectIPInModal(ip, poolName) {
    const clickedElement = event.currentTarget;
    const saveBtn = document.getElementById('use-ip-btn');
    
    // Проверяем, не выбран ли уже этот IP
    if (window.selectedIPInModal === ip) {
        // Если кликнули на уже выбранный IP - СНИМАЕМ выбор
        window.selectedIPInModal = null;
        window.selectedPoolInModal = null;
        
        // Снимаем выделение
        clickedElement.classList.remove('selected');
        
        // Обновляем текст кнопки
        saveBtn.disabled = false; // Кнопка ВСЕГДА активна!
        saveBtn.innerHTML = `<i class="fas fa-save"></i> Сохранить`;
    } else {
        // Выбираем новый IP
        // Снимаем выделение со всех IP
        document.querySelectorAll('.ip-option').forEach(el => {
            el.classList.remove('selected');
        });
        
        // Выделяем выбранный IP
        clickedElement.classList.add('selected');
        
        // Сохраняем выбранный IP
        window.selectedIPInModal = ip;
        window.selectedPoolInModal = poolName;
        
        // Обновляем текст кнопки
        saveBtn.disabled = false; // Кнопка ВСЕГДА активна!
        saveBtn.innerHTML = `<i class="fas fa-save"></i> Сохранить ${ip}`;
    }
}

// Сохраняет выбранный IP (или очищает поле если нет выбора)
function saveSelectedIP() {
    const ipField = document.getElementById('ip-address');
    
    // Если есть выбранный IP - вставляем его
    if (window.selectedIPInModal) {
        ipField.value = window.selectedIPInModal;
        showAlert(`Выбран IP: ${window.selectedIPInModal}`, 'success');
        
        // Автоматически проверяем DHCP для этого IP
        checkDHCPForIP(window.selectedIPInModal);
    } else {
        // Если НЕТ выбранного IP - ОЧИЩАЕМ поле
        ipField.value = '';
        showAlert('Поле IP адреса очищено', 'info');
    }
    
    // Закрываем модальное окно в ЛЮБОМ случае
    hideIPSelector();
}

// Проверяет DHCP для указанного IP (чтобы узнать, не используется ли он уже)
function checkDHCPForIP(ip) {
    fetch(`/api/find_dhcp_lease?ip=${encodeURIComponent(ip)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.found) {
                if (data.lease.status === 'bound') {
                    showAlert(`Внимание: IP ${ip} уже используется в DHCP`, 'warning');
                } else {
                    showAlert(`IP ${ip} найден в DHCP (${data.lease.status})`, 'info');
                }
                
                if (data.lease['mac-address']) {
                    // Автоматически заполняем MAC адрес, если нашли в DHCP
                    document.getElementById('mac-address').value = data.lease['mac-address'];
                }
            }
        })
        .catch(error => {
            console.error('Ошибка проверки DHCP:', error);
        });
}

// Добавляем CSS для выделения IP
const style = document.createElement('style');
style.textContent = `
    .ip-option:hover {
        background: #f8f9fa !important;
        border-color: #3498db !important;
    }
    
    .pool-section {
        transition: transform 0.2s;
    }
    
    .pool-section:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
`;
document.head.appendChild(style);

// Очищает выбор IP
function clearIPSelection() {
    // Снимаем выделение со всех IP
    document.querySelectorAll('.ip-option').forEach(el => {
        el.classList.remove('selected');
    });
    
    // Сбрасываем выбранный IP
    window.selectedIP = null;
    window.selectedPool = null;
    
    // Получаем кнопки
    const useBtn = document.getElementById('use-ip-btn');
    const clearBtn = document.getElementById('clear-ip-btn');
    
    // Деактивируем кнопки
    useBtn.disabled = true;
    clearBtn.disabled = true;
    useBtn.innerHTML = `<i class="fas fa-check"></i> Использовать выбранный IP`;
    
    // Показываем уведомление
    showToast('Выбор IP очищен', 'info', 2000);
}

// Скрывает модальное окно выбора IP
function hideIPSelector() {
    document.getElementById('ip-selector-modal').style.display = 'none';
    window.selectedIP = null;
    window.selectedPool = null;
}

// Отмена выбора IP
function cancelIPSelection() {
    // Восстанавливаем оригинальное значение IP
    const ipField = document.getElementById('ip-address');
    ipField.value = window.originalIP || '';
    
    // Закрываем модальное окно
    hideIPSelector();
    
    showAlert('Изменения отменены', 'info');
}

// ===== ФУНКЦИИ ПОИСКА УСТРОЙСТВ =====

// Поиск устройств в реальном времени - только прокрутка к найденному
function searchDevices(query) {
    const clearBtn = document.getElementById('search-clear-btn');
    const deviceList = document.getElementById('device-list');
    const deviceItems = deviceList.querySelectorAll('.device-item');
    
    // Показываем/скрываем кнопку очистки
    if (query.length > 0) {
        clearBtn.style.display = 'flex';
    } else {
        clearBtn.style.display = 'none';
    }
    
    // Убираем подсветку со всех
    deviceItems.forEach(item => item.classList.remove('found'));
    
    // Если поисковый запрос пуст - прокручиваем в верх
    if (!query || query.trim() === '') {
        const scrollContainer = document.querySelector('.device-list-scroll');
        if (scrollContainer) {
            scrollContainer.scrollTop = 0;
        }
        return;
    }
    
    const searchTerm = query.toLowerCase().trim();
    
    // Ищем первое совпадение по data-device-name атрибуту
    for (const item of deviceItems) {
        // Получаем имя устройства из data-атрибута
        const deviceName = (item.getAttribute('data-device-name') || '').toLowerCase();
        
        // Поиск подстроки в любом месте имени
        if (deviceName.includes(searchTerm)) {
            // Подсвечиваем найденное
            item.classList.add('found');
            
            // Прокручиваем ТОЛЬКО контейнер списка, не страницу
            const scrollContainer = document.querySelector('.device-list-scroll');
            if (scrollContainer) {
                // Позиция элемента относительно контейнера прокрутки
                const containerRect = scrollContainer.getBoundingClientRect();
                const itemRect = item.getBoundingClientRect();
                
                // Вычисляем новую позицию прокрутки
                const scrollTop = scrollContainer.scrollTop;
                const relativeTop = itemRect.top - containerRect.top;
                const newScrollTop = scrollTop + relativeTop - 10;
                
                scrollContainer.scrollTop = newScrollTop;
            }
            break; // Прерываем после первого найденного
        }
    }
}

// Очистка поиска устройств
function clearDeviceSearch() {
    const searchInput = document.getElementById('device-search');
    const clearBtn = document.getElementById('search-clear-btn');
    const deviceList = document.getElementById('device-list');
    
    // Очищаем поле поиска
    searchInput.value = '';
    clearBtn.style.display = 'none';
    
    // Убираем подсветку со всех устройств
    const deviceItems = deviceList.querySelectorAll('.device-item');
    deviceItems.forEach(item => item.classList.remove('found'));
    
    // Прокручиваем список в самый верх
    const scrollContainer = document.querySelector('.device-list-scroll');
    if (scrollContainer) {
        scrollContainer.scrollTop = 0;
    }
    
    // Фокус на поле поиска
    searchInput.focus();
}

// Обработчик горячих клавиш для поиска
document.addEventListener('keydown', function(e) {
    // Ctrl+F или / - фокус на поиск
    if ((e.ctrlKey && e.key === 'f') || (e.key === '/' && document.activeElement.tagName !== 'INPUT')) {
        const searchInput = document.getElementById('device-search');
        if (searchInput) {
            e.preventDefault();
            searchInput.focus();
            searchInput.select();
        }
    }
    
    // Escape - очистить поиск и убрать фокус
    if (e.key === 'Escape') {
        const searchInput = document.getElementById('device-search');
        if (searchInput && document.activeElement === searchInput) {
            clearDeviceSearch();
            searchInput.blur();
        }
    }
});

// ===== ФУНКЦИИ СПИННЕРА ЗАГРУЗКИ =====

// Показать спиннер
function showLoading(text = 'Загрузка...') {
    const overlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    if (overlay) {
        loadingText.textContent = text;
        overlay.style.display = 'flex';
    }
}

// Обновить текст спиннера (для многошаговых операций)
function updateLoadingText(text) {
    const loadingText = document.getElementById('loading-text');
    if (loadingText) {
        loadingText.textContent = text;
    }
}

// Скрыть спиннер
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

// ===== МОДАЛЬНОЕ ОКНО ОШИБОК =====

// Показать модальное окно ошибки
function showErrorModal(errorText) {
    hideLoading(); // Сначала скрываем спиннер
    
    const modal = document.getElementById('error-modal');
    const textEl = document.getElementById('error-modal-text');
    if (modal && textEl) {
        textEl.textContent = errorText;
        modal.style.display = 'flex';
    }
}

// Скрыть модальное окно ошибки
function hideErrorModal() {
    const modal = document.getElementById('error-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Закрытие по клику вне окна
document.addEventListener('click', function(e) {
    const modal = document.getElementById('error-modal');
    if (e.target === modal) {
        hideErrorModal();
    }
});

// Закрытие по Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        hideErrorModal();
    }
});

// ===== ФУНКЦИИ ЗАМЕНЫ MAC =====

// Загрузка DHCP пулов
function loadDhcpPools(hideSpinnerAfterLoad = true) {
    if (!currentDevice) {
        return;
    }
    
    fetch('/api/dhcp_pools')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('mac-pool-filter');
                select.innerHTML = '<option value="">Все пулы</option>';
                
                data.pools.forEach(pool => {
                    const option = document.createElement('option');
                    option.value = pool.name;
                    option.textContent = `${pool.name} (${pool.ranges})`;
                    select.appendChild(option);
                });
                
                // Обновляем текст спиннера
                updateLoadingText('Загрузка списка доступа в интернет...');
                
                // Сначала загружаем список internet_access
                loadInternetAccessList(hideSpinnerAfterLoad);
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки пулов:', error);
            if (hideSpinnerAfterLoad) hideLoading();
        });
}

// Загрузка списка IP с доступом в интернет
function loadInternetAccessList(hideSpinnerAfterLoad) {
    fetch('/api/internet_access')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                internetAccessList = data.ips || [];
                console.log(`📋 Загружено ${internetAccessList.length} IP с доступом в интернет`);
            } else {
                internetAccessList = [];
            }
            
            // Теперь загружаем абонентов
            updateLoadingText('Загрузка абонентов...');
            loadSubscribers(hideSpinnerAfterLoad);
        })
        .catch(error => {
            console.error('Ошибка загрузки internet_access:', error);
            internetAccessList = [];
            loadSubscribers(hideSpinnerAfterLoad);
        });
}

// Загрузка абонентов (автоматически при подключении)
function loadSubscribers(hideSpinner = false) {
    if (!currentDevice) {
        return;
    }
    
    const poolSelect = document.getElementById('mac-pool-filter');
    const poolName = poolSelect ? poolSelect.value : '';
    
    let url = '/api/dhcp_subscribers';
    if (poolName) {
        url += `?pool=${encodeURIComponent(poolName)}`;
    }
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (hideSpinner) hideLoading();
            if (data.success) {
                allSubscribers = data.subscribers;
                renderSubscribersTable(data.subscribers);
            } else {
                console.error('Ошибка загрузки абонентов:', data.error);
                renderSubscribersTable([]);
            }
        })
        .catch(error => {
            if (hideSpinner) hideLoading();
            console.error('Ошибка загрузки абонентов:', error);
            renderSubscribersTable([]);
        });
}

// Обновить список абонентов
function refreshSubscribers() {
    if (!currentDevice) {
        showAlert('Сначала подключитесь к устройству', 'error');
        return;
    }
    
    showLoading('Загрузка DHCP пулов...');
    clearSubscriberSelection();
    
    // Загружаем пулы и абонентов со скрытием спиннера после завершения
    loadDhcpPools(true);
}

// Отрисовка таблицы абонентов
function renderSubscribersTable(subscribers) {
    const tbody = document.getElementById('subscribers-tbody');
    const countEl = document.getElementById('subscribers-count');
    const shownEl = document.getElementById('subscribers-shown');
    
    // Считаем сколько абонентов с доступом в интернет
    let inetCount = 0;
    subscribers.forEach(sub => {
        if (internetAccessList.includes(sub.ip)) {
            inetCount++;
        }
    });
    
    // Обновляем статистику
    if (countEl) countEl.textContent = allSubscribers.length;
    if (shownEl) shownEl.textContent = subscribers.length;
    
    if (!subscribers || subscribers.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="4">
                    <div class="empty-state">
                        <i class="fas fa-users"></i>
                        <p>${currentDevice ? 'Нет абонентов в DHCP' : 'Подключитесь к устройству для загрузки абонентов'}</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = subscribers.map(sub => {
        const hasInet = internetAccessList.includes(sub.ip);
        const rowClass = hasInet ? 'has-internet' : '';
        
        return `
            <tr data-ip="${sub.ip}" data-mac="${sub.mac || ''}" data-comment="${escapeHtml(sub.comment || '')}" class="${rowClass}" onclick="selectSubscriber(this)">
                <td class="col-inet" onclick="event.stopPropagation()">
                    <label class="inet-checkbox" title="${hasInet ? 'Доступ есть. Нажмите чтобы выключить' : 'Доступа нет. Нажмите чтобы включить'}">
                        <input type="checkbox" ${hasInet ? 'checked' : ''} onchange="toggleInternetAccess('${sub.ip}', this.checked, '${escapeHtml(sub.comment || '')}')">
                        <span class="checkmark"></span>
                    </label>
                </td>
                <td class="ip-cell">${sub.ip}</td>
                <td class="mac-cell">${sub.mac || '<span style="color: var(--text-muted);">—</span>'}</td>
                <td class="comment-cell" title="${escapeHtml(sub.comment || '')}">${sub.comment || '<span style="color: var(--text-muted);">—</span>'}</td>
            </tr>
        `;
    }).join('');
}

// Включить/выключить доступ в интернет
function toggleInternetAccess(ip, enable, comment) {
    console.log(`Toggle internet: ${ip} -> ${enable}`);
    
    fetch('/api/internet_access/toggle', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            ip: ip,
            enable: enable,
            comment: comment
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Обновляем локальный список
            if (enable) {
                if (!internetAccessList.includes(ip)) {
                    internetAccessList.push(ip);
                }
            } else {
                const idx = internetAccessList.indexOf(ip);
                if (idx > -1) {
                    internetAccessList.splice(idx, 1);
                }
            }
            
            // Обновляем стиль строки
            const row = document.querySelector(`tr[data-ip="${ip}"]`);
            if (row) {
                if (enable) {
                    row.classList.add('has-internet');
                } else {
                    row.classList.remove('has-internet');
                }
            }
            
            showAlert(data.message || `Доступ ${enable ? 'включён' : 'выключен'} для ${ip}`, 'success');
        } else {
            // Возвращаем чекбокс в прежнее состояние
            const checkbox = document.querySelector(`tr[data-ip="${ip}"] .inet-checkbox input`);
            if (checkbox) {
                checkbox.checked = !enable;
            }
            showAlert(data.error || 'Ошибка изменения доступа', 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка toggle internet:', error);
        // Возвращаем чекбокс
        const checkbox = document.querySelector(`tr[data-ip="${ip}"] .inet-checkbox input`);
        if (checkbox) {
            checkbox.checked = !enable;
        }
        showAlert('Ошибка соединения', 'error');
    });
}

// Экранирование HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Выбор абонента
function selectSubscriber(row) {
    console.log('Выбор абонента:', row);
    
    // Снимаем выделение со всех
    const rows = document.querySelectorAll('#subscribers-tbody tr');
    rows.forEach(r => r.classList.remove('selected'));
    
    // Выделяем выбранную строку
    row.classList.add('selected');
    
    // Сохраняем данные выбранного абонента
    selectedSubscriber = {
        ip: row.getAttribute('data-ip'),
        mac: row.getAttribute('data-mac'),
        comment: row.getAttribute('data-comment')
    };
    
    console.log('Данные абонента:', selectedSubscriber);
    
    // Показываем панель действий
    showActionPanel(selectedSubscriber);
}

// Показать панель действий
function showActionPanel(subscriber) {
    const panel = document.getElementById('subscriber-action-panel');
    
    if (!panel) {
        console.error('Панель действий не найдена!');
        return;
    }
    
    document.getElementById('selected-ip').textContent = subscriber.ip;
    document.getElementById('selected-mac').textContent = subscriber.mac || 'нет MAC';
    document.getElementById('selected-comment').textContent = subscriber.comment || '';
    
    panel.style.display = 'block';
    
    // Прокручиваем к панели действий
    setTimeout(() => {
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
    
    // Скрываем диалог замены MAC если открыт
    hideMacReplaceDialog();
    
    console.log('Панель действий показана для:', subscriber.ip);
}

// Очистить выбор абонента
function clearSubscriberSelection() {
    selectedSubscriber = null;
    
    // Снимаем выделение
    const rows = document.querySelectorAll('#subscribers-tbody tr');
    rows.forEach(r => r.classList.remove('selected'));
    
    // Скрываем панель
    const panel = document.getElementById('subscriber-action-panel');
    panel.style.display = 'none';
    
    // Скрываем диалог
    hideMacReplaceDialog();
}

// Очистить весь список абонентов (при отключении)
function clearSubscribersList() {
    allSubscribers = [];
    selectedSubscriber = null;
    internetAccessList = []; // Очищаем список доступа
    
    // Очищаем таблицу
    const tbody = document.getElementById('subscribers-tbody');
    if (tbody) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="3">
                    <div class="empty-state">
                        <i class="fas fa-plug"></i>
                        <p>Подключитесь к устройству для загрузки абонентов</p>
                    </div>
                </td>
            </tr>
        `;
    }
    
    // Сбрасываем статистику
    document.getElementById('subscribers-count').textContent = '0';
    document.getElementById('subscribers-shown').textContent = '0';
    
    // Очищаем фильтр пулов
    const poolFilter = document.getElementById('mac-pool-filter');
    if (poolFilter) {
        poolFilter.innerHTML = '<option value="">Все пулы</option>';
    }
    
    // Скрываем панель действий
    const panel = document.getElementById('subscriber-action-panel');
    if (panel) {
        panel.style.display = 'none';
    }
    
    // Скрываем диалог
    hideMacReplaceDialog();
}

// Фильтрация абонентов по тексту
function filterSubscribers(query) {
    if (!allSubscribers || allSubscribers.length === 0) return;
    
    const searchTerm = query.toLowerCase().trim();
    
    if (!searchTerm) {
        renderSubscribersTable(allSubscribers);
        return;
    }
    
    const filtered = allSubscribers.filter(sub => {
        const ip = (sub.ip || '').toLowerCase();
        const mac = (sub.mac || '').toLowerCase();
        const comment = (sub.comment || '').toLowerCase();
        
        return ip.includes(searchTerm) || mac.includes(searchTerm) || comment.includes(searchTerm);
    });
    
    renderSubscribersTable(filtered);
}

// Фильтрация по пулу
function filterSubscribersByPool(poolName) {
    // Перезагружаем абонентов с фильтром по пулу
    loadSubscribers();
    clearSubscriberSelection();
}

// Показать диалог замены MAC
function showMacReplaceDialog() {
    console.log('showMacReplaceDialog вызвана');
    console.log('selectedSubscriber:', selectedSubscriber);
    
    if (!selectedSubscriber) {
        showAlert('Сначала выберите абонента', 'error');
        return;
    }
    
    const dialog = document.getElementById('mac-replace-dialog');
    const oldIpEl = document.getElementById('dialog-old-ip');
    const oldMacEl = document.getElementById('dialog-old-mac');
    const targetInput = document.getElementById('mac-target-input');
    const targetSelect = document.getElementById('mac-target-select');
    const newMacInput = document.getElementById('new-mac-input');
    const newClientIdInput = document.getElementById('new-clientid-input');
    
    console.log('dialog:', dialog);
    console.log('oldIpEl:', oldIpEl);
    console.log('oldMacEl:', oldMacEl);
    
    if (!dialog) {
        console.error('Диалог не найден!');
        showAlert('Ошибка: диалог не найден', 'error');
        return;
    }
    
    // Заполняем текущие данные
    if (oldIpEl) oldIpEl.textContent = selectedSubscriber.ip;
    if (oldMacEl) oldMacEl.textContent = selectedSubscriber.mac || 'нет MAC';
    
    // Очищаем поля ввода
    if (targetInput) targetInput.value = '';
    if (newMacInput) newMacInput.value = '';
    if (newClientIdInput) newClientIdInput.value = '';
    
    // Сбрасываем режим на "по IP"
    switchReplaceMode('by-ip');
    const radioBtn = document.querySelector('input[name="replace-mode"][value="by-ip"]');
    if (radioBtn) radioBtn.checked = true;
    
    // Заполняем выпадающий список абонентами (для быстрого выбора)
    if (targetSelect) {
        targetSelect.innerHTML = '<option value="">Из списка</option>';
        
        if (allSubscribers && allSubscribers.length > 0) {
            allSubscribers.forEach(sub => {
                if (sub.ip !== selectedSubscriber.ip) {
                    const option = document.createElement('option');
                    option.value = sub.ip;
                    option.textContent = `${sub.ip} (${sub.comment || 'без имени'})`;
                    targetSelect.appendChild(option);
                }
            });
        }
        
        // При выборе из списка - заполняем поле ввода
        targetSelect.onchange = function() {
            if (this.value && targetInput) {
                targetInput.value = this.value;
            }
        };
    }
    
    dialog.style.display = 'block';
    console.log('Диалог показан');
}

// Переключение режима замены
function switchReplaceMode(mode) {
    const modeByIp = document.getElementById('mode-by-ip');
    const modeByMac = document.getElementById('mode-by-mac');
    
    if (mode === 'by-ip') {
        modeByIp.style.display = 'block';
        modeByMac.style.display = 'none';
    } else {
        modeByIp.style.display = 'none';
        modeByMac.style.display = 'block';
    }
    
    // Очищаем результаты при переключении
    document.getElementById('mac-replace-results').innerHTML = '';
}

// Автозаполнение ClientID из MAC
function updateClientIdFromMac(macValue) {
    const clientidInput = document.getElementById('new-clientid-input');
    
    if (macValue && macValue.trim()) {
        // Формируем ClientID: 1: + MAC в нижнем регистре
        const cleanMac = macValue.trim().toLowerCase();
        clientidInput.value = '1:' + cleanMac;
    } else {
        clientidInput.value = '';
    }
}

// Ручное автозаполнение ClientID
function autoFillClientId() {
    const macInput = document.getElementById('new-mac-input');
    const macValue = macInput.value.trim();
    
    if (!macValue) {
        showAlert('Сначала введите MAC адрес', 'warning');
        return;
    }
    
    updateClientIdFromMac(macValue);
}

// Скрыть диалог замены MAC
function hideMacReplaceDialog() {
    const dialog = document.getElementById('mac-replace-dialog');
    const resultsDiv = document.getElementById('mac-replace-results');
    
    dialog.style.display = 'none';
    resultsDiv.innerHTML = '';
}

// Выполнить замену MAC
function executeMacReplace() {
    if (!selectedSubscriber) {
        showAlert('Сначала выберите абонента', 'error');
        return;
    }
    
    // Определяем выбранный режим
    const selectedMode = document.querySelector('input[name="replace-mode"]:checked').value;
    const resultsDiv = document.getElementById('mac-replace-results');
    
    if (selectedMode === 'by-ip') {
        // Режим 1: По IP устройства
        executeMacReplaceByIp(resultsDiv);
    } else {
        // Режим 2: Ввести MAC вручную
        executeMacReplaceByMac(resultsDiv);
    }
}

// Режим 1: Замена MAC по IP устройства
function executeMacReplaceByIp(resultsDiv) {
    const targetInput = document.getElementById('mac-target-input');
    const newIp = targetInput.value.trim();
    
    if (!newIp) {
        showAlert('Введите IP адрес нового устройства', 'error');
        return;
    }
    
    const oldIp = selectedSubscriber.ip;
    
    if (oldIp === newIp) {
        showAlert('IP адреса должны быть разными', 'error');
        return;
    }
    
    // Валидация IP
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(newIp)) {
        showAlert('Неверный формат IP адреса', 'error');
        return;
    }
    
    // Подтверждение
    const confirmText = `Замена MAC адреса (по IP)\n\n` +
        `Старый IP: ${oldIp}\n` +
        `Новый IP: ${newIp}\n\n` +
        `Настройки с IP ${oldIp} будут перенесены.\n` +
        `MAC и ClientID будут взяты с нового устройства.\n\n` +
        `Продолжить?`;
    
    if (!confirm(confirmText)) {
        return;
    }
    
    showLoading('Инициализация замены MAC...');
    resultsDiv.innerHTML = '<div class="toast toast-info">Выполняется операция...</div>';
    
    // Симулируем прогресс операции
    setTimeout(() => updateLoadingText('Получение данных старого устройства...'), 300);
    setTimeout(() => updateLoadingText('Получение MAC нового устройства...'), 800);
    setTimeout(() => updateLoadingText('Обновление DHCP записи...'), 1300);
    setTimeout(() => updateLoadingText('Обновление ARP таблицы...'), 1800);
    
    fetch('/api/replace_mac', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            mode: 'by-ip',
            old_ip: oldIp,
            new_ip: newIp
        })
    })
    .then(response => response.json())
    .then(data => {
        handleMacReplaceResponse(data, resultsDiv);
    })
    .catch(error => {
        handleMacReplaceError(error, resultsDiv);
    });
}

// Режим 2: Замена MAC вручную
function executeMacReplaceByMac(resultsDiv) {
    const newMacInput = document.getElementById('new-mac-input');
    const newClientIdInput = document.getElementById('new-clientid-input');
    
    const newMac = newMacInput.value.trim();
    const newClientId = newClientIdInput.value.trim();
    
    // Валидация MAC
    if (!newMac) {
        showAlert('Введите новый MAC адрес', 'error');
        return;
    }
    
    const macRegex = /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/;
    if (!macRegex.test(newMac)) {
        showAlert('Неверный формат MAC адреса\nИспользуйте формат: AA:BB:CC:DD:EE:FF', 'error');
        return;
    }
    
    // Валидация ClientID (опционально, но рекомендуется)
    if (!newClientId) {
        if (!confirm('ClientID не указан. Продолжить без него?\n\nРекомендуется указать ClientID в формате: 1:aa:bb:cc:dd:ee:ff')) {
            return;
        }
    }
    
    const oldIp = selectedSubscriber.ip;
    const oldMac = selectedSubscriber.mac || 'нет';
    
    // Подтверждение
    const confirmText = `Замена MAC адреса (вручную)\n\n` +
        `IP: ${oldIp}\n` +
        `Старый MAC: ${oldMac}\n` +
        `Новый MAC: ${newMac}\n` +
        `ClientID: ${newClientId || 'не указан'}\n\n` +
        `Продолжить?`;
    
    if (!confirm(confirmText)) {
        return;
    }
    
    showLoading('Инициализация замены MAC...');
    resultsDiv.innerHTML = '<div class="toast toast-info">Выполняется операция...</div>';
    
    // Симулируем прогресс операции
    setTimeout(() => updateLoadingText('Обновление DHCP lease...'), 300);
    setTimeout(() => updateLoadingText('Установка нового MAC...'), 600);
    setTimeout(() => updateLoadingText('Установка ClientID...'), 900);
    setTimeout(() => updateLoadingText('Обновление ARP таблицы...'), 1200);
    
    fetch('/api/replace_mac', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            mode: 'by-mac',
            ip: oldIp,
            new_mac: newMac,
            client_id: newClientId
        })
    })
    .then(response => response.json())
    .then(data => {
        handleMacReplaceResponse(data, resultsDiv);
    })
    .catch(error => {
        handleMacReplaceError(error, resultsDiv);
    });
}

// Обработка успешного ответа
function handleMacReplaceResponse(data, resultsDiv) {
    hideLoading();
    
    if (data.success) {
        resultsDiv.innerHTML = `
            <div class="toast toast-success">
                ✅ ${data.message}
                ${data.steps ? '<div style="margin-top: 10px; font-size: 12px; text-align: left;">' + 
                  data.steps.map(s => `<div>${s}</div>`).join('') + '</div>' : ''}
            </div>
        `;
        showAlert('MAC адрес успешно заменен', 'success');
        
        // Обновляем список
        setTimeout(() => {
            updateLoadingText('Обновление списка абонентов...');
            showLoading('Обновление списка абонентов...');
            clearSubscriberSelection();
            loadDhcpPools(true);
        }, 2000);
    } else {
        resultsDiv.innerHTML = `
            <div class="toast toast-error">
                ❌ ${data.error || 'Ошибка замены MAC'}
                ${data.steps ? '<div style="margin-top: 10px; font-size: 12px; text-align: left;">' + 
                  data.steps.map(s => `<div>${s}</div>`).join('') + '</div>' : ''}
            </div>
        `;
        showErrorModal(data.error || 'Ошибка замены MAC адреса');
    }
}

// Обработка ошибки
function handleMacReplaceError(error, resultsDiv) {
    hideLoading();
    console.error('Ошибка замены MAC:', error);
    resultsDiv.innerHTML = `
        <div class="toast toast-error">
            ❌ Ошибка соединения с сервером
        </div>
    `;
    showErrorModal('Ошибка соединения с сервером');
}

// Переключение выпадающего меню "Ещё"
function toggleActionDropdown() {
    const menu = document.getElementById('action-dropdown-menu');
    menu.classList.toggle('show');
}

// Закрытие dropdown при клике вне его
document.addEventListener('click', function(e) {
    const dropdown = document.querySelector('.action-dropdown');
    const menu = document.getElementById('action-dropdown-menu');
    
    if (dropdown && menu && !dropdown.contains(e.target)) {
        menu.classList.remove('show');
    }
});

// Копировать данные абонента
function copySubscriberData() {
    if (!selectedSubscriber) return;
    
    const text = `IP: ${selectedSubscriber.ip}\nMAC: ${selectedSubscriber.mac || 'нет'}\nКомментарий: ${selectedSubscriber.comment || 'нет'}`;
    
    navigator.clipboard.writeText(text).then(() => {
        showAlert('Данные скопированы в буфер обмена', 'success');
    }).catch(() => {
        showAlert('Не удалось скопировать', 'error');
    });
}

// Удалить lease (заглушка)
function deleteSubscriberLease(e) {
    e.preventDefault();
    showAlert('Функция в разработке', 'info');
}

// Заблокировать абонента (заглушка)
function blockSubscriber(e) {
    e.preventDefault();
    showAlert('Функция в разработке', 'info');
}

// Показать статистику (заглушка)
function showSubscriberStats(e) {
    e.preventDefault();
    showAlert('Функция в разработке', 'info');
}

// Редактировать комментарий (заглушка)
function editSubscriberComment() {
    showAlert('Функция в разработке', 'info');
}
