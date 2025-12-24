let currentDevice = null;
let queueTree = [];
let queueTreeData = []; // Хранит все данные дерева
let queueTreeFiltered = []; // Отфильтрованные данные
let queueTreeExpanded = {}; // Состояние развернутости узлов

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
                    const buttonClass = currentDevice === name ? 'btn-danger' : 'connect-btn';

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

                    // Загружаем дерево очередей (новая версия)
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
                    document.getElementById('queue-tree-v2').innerHTML = '';
                    
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
                document.getElementById('queue-tree-v2').innerHTML = '';

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

    // ШАГ 1: Проверка принадлежности IP к сетям микротика
    showAlert('Проверка принадлежности IP к сетям микротика...', 'info');
    
    // Сначала делаем проверку IP
    fetch(`/api/check_ip?ip=${encodeURIComponent(ip)}`)
        .then(response => response.json())
        .then(ipCheckData => {
            if (!ipCheckData.success) {
                // IP не принадлежит сетям микротика
                showAlert(ipCheckData.error || 'IP не принадлежит сетям микротика', 'error');
                resultsDiv.innerHTML = `
                    <div class="toast toast-error">
                        ❌ ${ipCheckData.error || 'IP не принадлежит сетям микротика'}
                    </div>
                `;
                return;
            }
            
            // IP прошел проверку, продолжаем
            showAlert('IP проверен успешно, ищем MAC адрес...', 'success');
            
            // ШАГ 2: Получаем текущий MAC из DHCP
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

                    // ШАГ 3: Подтверждение для работы без очередей (если не выбраны)
                    if (selectedQueues.length === 0) {
                        const proceed = confirm(
                            'Вы не выбрали очереди. Сотрудник будет добавлен без ограничений очередей.\n\n' +
                            'Вы можете использовать настройки по умолчанию или добавить в очередь позже.\n\n' +
                            'Продолжить?'
                        );
                        
                        if (!proceed) {
                            resultsDiv.innerHTML = `
                                <div class="toast toast-info">
                                    📋 Отменено пользователем
                                </div>
                            `;
                            return;
                        }
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
        })
        .catch(error => {
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
