let currentDevice = null;
let queueTree = [];

// Загрузка при старте
document.addEventListener('DOMContentLoaded', function() {
    loadDevices();
    loadSettings();
    
    // Инициализация модального окна
    const modal = document.getElementById('device-modal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                hideAddDeviceForm();
            }
        });
    }
});

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
        'tools': 'Инструменты'
    };
    return tabs[tabKey] || tabKey;
}

// Загрузка устройств
function loadDevices() {
    fetch('/api/devices')
        .then(response => response.json())
        .then(data => {
            const deviceList = document.getElementById('device-list');
            deviceList.innerHTML = '';

            if (data.devices && Object.keys(data.devices).length > 0) {
                for (const [name, device] of Object.entries(data.devices)) {
                    const li = document.createElement('li');
                    li.className = 'device-item';
                    if (currentDevice === name) {
                        li.classList.add('active');
                    }

                    const buttonText = currentDevice === name ? '🔓 Отключить' : '🔗 Подключить';
                    const buttonClass = currentDevice === name ? 'btn-danger' : '';

                    li.innerHTML = `
                        <div class="device-info">
                            <div class="device-name">${name}</div>
                            <div class="device-ip">${device.ip}:${device.port}</div>
                        </div>
                        <button class="connect-btn ${buttonClass}" onclick="connectDevice('${name}')">
                            ${buttonText}
                        </button>
                    `;
                    deviceList.appendChild(li);
                }
            } else {
                deviceList.innerHTML = '<li style="color: #999; padding: 10px;">Нет устройств</li>';
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки устройств:', error);
            showAlert('Ошибка загрузки устройств', 'error');
        });
}

// Подключение/отключение устройства
function connectDevice(deviceName) {
    if (currentDevice === deviceName) {
        disconnectDevice();
        return;
    }

    showAlert('Подключаемся...', 'info');

    fetch(`/api/connect?device=${encodeURIComponent(deviceName)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.action === 'connected') {
                    currentDevice = deviceName;
                    document.getElementById('connection-status').className = 'status-dot connected';
                    document.getElementById('connection-text').textContent = 'Подключено';
                    document.getElementById('device-name').textContent = deviceName;
                    document.getElementById('disconnect-btn').style.display = 'block';

                    showAlert(data.message, 'success');

                    // Загружаем дерево очередей
                    loadQueueTree();
                    
                    // ЗАГРУЖАЕМ ВСЕ ОЧЕРЕДИ ДЛЯ SELECT
                    loadAllQueues();
                    
                } else if (data.action === 'disconnected') {
                    currentDevice = null;
                    document.getElementById('connection-status').className = 'status-dot';
                    document.getElementById('connection-text').textContent = 'Не подключено';
                    document.getElementById('device-name').textContent = '';
                    document.getElementById('queue-stats').textContent = '';
                    document.getElementById('disconnect-btn').style.display = 'none';

                    showAlert(data.message, 'info');

                    // Очищаем дерево очередей
                    document.getElementById('queue-tree').innerHTML = '';
                    
                    // Очищаем select с очередями
                    resetQueueSelect();
                }

                loadDevices();
            } else {
                showAlert(data.error || 'Ошибка подключения', 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка подключения:', error);
            showAlert('Ошибка подключения', 'error');
        });
}

// Функция для отключения
function disconnectDevice() {
    if (!currentDevice) {
        showAlert('Нет активных подключений', 'info');
        return;
    }

    showAlert('Отключаемся...', 'info');

    fetch('/api/disconnect')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentDevice = null;
                document.getElementById('connection-status').className = 'status-dot';
                document.getElementById('connection-text').textContent = 'Не подключено';
                document.getElementById('device-name').textContent = '';
                document.getElementById('queue-stats').textContent = '';
                document.getElementById('disconnect-btn').style.display = 'none';

                showAlert(data.message, 'info');

                // Очищаем дерево очередей
                document.getElementById('queue-tree').innerHTML = '';

                // Очищаем select с очередями
                resetQueueSelect();

                loadDevices();
            }
        })
        .catch(error => {
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
    function addEmployee() {
        // Получаем значения из формы
        const fullName = document.getElementById('full-name').value.trim();      // Имя и фамилия сотрудника
        const position = document.getElementById('position').value.trim();       // Должность сотрудника
        const ip = document.getElementById('ip-address').value.trim();          // IP адрес сотрудника
        const manualMac = document.getElementById('mac-address').value.trim();   // MAC адрес сотрудника (может быть пустым)
        const internetAccess = document.getElementById('internet-access').checked; // Доступ в интернет
        const queue = document.getElementById('queue-select').value;             // Название очереди (может быть пустым)

        // Проверка заполнения обязательных полей
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
        resultsDiv.innerHTML = '<div class="toast toast-info">Проверяем MAC адрес...</div>';

        // Получаем текущий MAC из DHCP
        fetch(`/api/find_dhcp_lease?ip=${encodeURIComponent(ip)}`)
            .then(response => response.json())
            .then(dhcpData => {
                let finalMac;

                if (dhcpData.lease && dhcpData.lease['mac-address']) {  // Обращаемся к полю mac-address
                    // Нашли текущий MAC в DHCP - используем его
                    finalMac = dhcpData.lease['mac-address'];
                    document.getElementById('mac-address').value = finalMac;
                    showAlert('Использован MAC адрес из DHCP', 'info');
                } else if (manualMac) {
                    // Пользователь вручную заполнил MAC
                    finalMac = manualMac;
                    showAlert('Использован указанный вручную MAC адрес', 'info');
                } else {
                    // Ни DHCP, ни вручную MAC не указаны
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
                    queue: queue
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
                    if (result.success) {
                        showAlert(`Сотрудник ${fullName} успешно добавлен`, 'success');
                        resultsDiv.innerHTML = `
                            <div class="toast toast-success">
                                ✅ Сотрудник ${fullName} успешно добавлен!
                            </div>
                        `;
                    } else {
                        let message = result.message || 'Ошибка добавления сотрудника';
                        showAlert(message, 'error');
                        resultsDiv.innerHTML = `
                            <div class="toast toast-error">
                                ❌ ${message}
                            </div>
                        `;
                    }
                })
                .catch(error => {
                    console.error('Ошибка отправки данных:', error);
                    showAlert('Ошибка отправки данных', 'error');
                    resultsDiv.innerHTML = '';
                });
            })
            .catch(error => {
                console.error('Ошибка проверки DHCP:', error);
                showAlert('Ошибка проверки DHCP', 'error');
                resultsDiv.innerHTML = '';
            });
    }

    // Вспомогательная функция для показа уведомлений
    function showAlert(message, type) {
        alert(message); // Или можно заменить на собственный UI-компонент уведомления
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
                const filterPaidQueues = (nodes) => {
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
                            const childResult = filterPaidQueues(newNode.children);
                            newNode.children = childResult.filtered;
                            paidCount += childResult.paidCount;
                        }
                        
                        filtered.push(newNode);
                    });
                    
                    return { filtered, paidCount };
                };
                
                const result = filterPaidQueues(data.tree);
                queueTree = result.filtered;
                renderQueueTree(result.filtered);

                if (data.stats) {
                    let statsText = `Очередей: ${result.filtered.length} (вкл: ${result.filtered.filter(q => q.enabled).length})`;
                    if (result.paidCount > 0) {
                        statsText += ` (${result.paidCount} платных скрыто)`;
                    }
                    document.getElementById('queue-stats').textContent = statsText;
                }
            } else {
                showAlert(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка загрузки дерева:', error);
            showAlert('Ошибка загрузки дерева очередей', 'error');
        });
}

// Отрисовка дерева очередей
function renderQueueTree(tree) {
    const container = document.getElementById('queue-tree');
    container.innerHTML = '';

    function renderNode(node, level = 0) {
        const div = document.createElement('div');
        div.className = `queue-item ${node.enabled ? '' : 'disabled'}`;
        div.classList.add(`level-${level}`);

        let prefix = '─ '.repeat(level);
        if (level > 0) {
            prefix = '├' + prefix;
        }

        let ipInfo = '';
        if (node.ip_count > 0) {
            ipInfo = ` <span style="color: #3498db;">(${node.ip_count} IP)</span>`;
        }

        div.innerHTML = `
            <div style="display: flex; justify-content: space-between;">
                <span>${prefix} ${node.name}${ipInfo}</span>
                <span style="font-size: 12px; color: #7f8c8d;">
                    ${node.enabled ? '✅' : '❌'} ${node.max_limit || 'без лимита'}
                </span>
            </div>
            ${node.comment ? `<div style="font-size: 12px; color: #666; margin-left: ${level * 20 + 20}px;">${node.comment}</div>` : ''}
        `;

        container.appendChild(div);

        if (node.children && node.children.length > 0) {
            node.children.forEach(child => renderNode(child, level + 1));
        }
    }

    tree.forEach(node => renderNode(node));
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
                            // ФИЛЬТРУЕМ ПЛАТНЫЕ ОЧЕРЕДИ НА КЛИЕНТЕ
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

// Загружает ВСЕ очереди при подключении с фильтрацией платных на клиенте
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
                
                updateQueueSelect(freeQueues);
                
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

// Обновляет select с очередями
function updateQueueSelect(queues) {
    const select = document.getElementById('queue-select');
    if (!select) return;
    
    select.innerHTML = '<option value="">-- Не выбрана --</option>';
    
    if (queues.length === 0) {
        select.innerHTML += '<option value="">-- Нет бесплатных очередей --</option>';
    } else {
        queues.sort((a, b) => a.name.localeCompare(b.name));
        
        queues.forEach(queue => {
            const option = document.createElement('option');
            option.value = queue.name;
            
            let displayText = queue.name;
            if (queue.target) displayText += ` (${queue.target})`;
            if (queue.comment) displayText += ` - ${queue.comment}`;
            
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
