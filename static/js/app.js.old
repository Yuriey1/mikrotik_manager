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
    resultsDiv.innerHTML = '<div class="toast toast-info">Проверяем IP и MAC адрес...</div>';

    // ШАГ 1: Проверка принадлежности IP к сетям микротика
    showAlert('Проверка принадлежности IP к сетям микротика...', 'info');
    
    // Сначала делаем проверку IP (это новый шаг)
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

                    // ШАГ 3: Получаем все очереди для выбора
                    fetch('/api/find_queues')
                        .then(response => response.json())
                        .then(queuesData => {
                            // Если очередь не выбрана, можно предложить пользователю выбрать из списка
                            if (!queue && queuesData.queues && queuesData.queues.length > 0) {
                                // Здесь можно добавить логику для предложения очередей
                                // Пока просто продолжаем без очереди
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
                            console.error('Ошибка получения очередей:', error);
                            // Продолжаем без очередей
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
    
    // Сбросим значения на пустые
    document.getElementById('full-name').value = "";                // Имя и фамилия сотрудника
    document.getElementById('position').value = "";                 // Должность сотрудника
    document.getElementById('ip-address').value = "";               // IP адрес сотрудника
    document.getElementById('mac-address').value = "";              // MAC адрес сотрудника (может быть пустым)
    document.getElementById('internet-access').unchecked;           // Доступ в интернет
    document.getElementById('queue-select').value = "";             // Название очереди (может быть пустым)
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
                queueTreeData = result.filtered;
                queueTreeFiltered = [...queueTreeData];
                
                // Сбрасываем состояние развернутости
                queueTreeExpanded = {};
                
                // Обновляем статистику
                updateQueueTreeStats(result.filtered, result.paidCount);
                
                // Отрисовываем дерево
                renderQueueTreeV2(result.filtered);
                
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

// Отрисовка нового дерева очереди с DST как корневыми узлами
function renderQueueTreeV2(tree, level = 0) {
    const container = document.getElementById('queue-tree-v2');
    
    if (!tree || tree.length === 0) {
        showEmptyQueueTree();
        return;
    }
    
    container.innerHTML = '';
    
    // Группируем очереди по DST для создания корневых узлов
    const queuesByDst = {};
    
    function processNode(node, parentDst = null) {
        // Определяем DST для текущего узла
        let dstText = '';
        if (node.dst && node.dst !== 'none') {
            dstText = node.dst;
        } else if (node.short_dst && node.short_dst !== 'none') {
            dstText = node.short_dst;
        } else if (parentDst) {
            dstText = parentDst;
        }
        
        // Если у узла нет DST, используем "Без DST"
        if (!dstText) {
            dstText = 'Без DST';
        }
        
        // Добавляем узел в соответствующую группу DST
        if (!queuesByDst[dstText]) {
            queuesByDst[dstText] = {
                name: dstText,
                enabled: true, // DST всегда включен
                children: [],
                isDstRoot: true
            };
        }
        
        // Создаем копию узла без детей (дети будут обработаны отдельно)
        const nodeCopy = {
            ...node,
            children: [] // Дети будут добавлены позже
        };
        
        // Добавляем узел в группу DST
        queuesByDst[dstText].children.push(nodeCopy);
        
        // Обрабатываем детей рекурсивно
        if (node.children && node.children.length > 0) {
            node.children.forEach(child => {
                processNode(child, dstText);
            });
        }
    }
    
    // Обрабатываем все узлы дерева
    tree.forEach(node => {
        processNode(node);
    });
    
    // Преобразуем группы DST в массив для отрисовки
    const dstRoots = Object.values(queuesByDst);
    
    // Определяем максимальные ширины для колонок
    let maxTargetWidth = 0;
    let maxDstWidth = 0;
    
    function calculateMaxWidths(nodes) {
        nodes.forEach(node => {
            if (node.isDstRoot) {
                // Для корневого DST вычисляем ширину имени
                const dstWidth = node.name.length * 8;
                maxDstWidth = Math.max(maxDstWidth, dstWidth);
            } else {
                // Для обычных очередей вычисляем ширину TARGET
                let targetText = '';
                if (node.short_target && node.short_target !== 'none') {
                    targetText = node.short_target;
                } else if (node.target && Array.isArray(node.target) && node.target.length > 0) {
                    targetText = node.target[0];
                }
                
                if (targetText) {
                    const targetWidth = targetText.length * 7;
                    maxTargetWidth = Math.max(maxTargetWidth, targetWidth);
                }
            }
            
            // Рекурсивно для детей
            if (node.children && node.children.length > 0) {
                calculateMaxWidths(node.children);
            }
        });
    }
    
    calculateMaxWidths(dstRoots);
    
    // Ограничиваем максимальную ширину
    maxTargetWidth = Math.min(maxTargetWidth, 200);
    maxDstWidth = Math.min(maxDstWidth, 200);
    
    // Создаем табличную структуру
    const table = document.createElement('div');
    table.style.display = 'table';
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    
    // Отрисовываем каждый корневой DST и его очереди
    dstRoots.forEach(dstRoot => {
        // Рендерим корневой DST узел
        renderDstRootRow(dstRoot, table, maxTargetWidth, maxDstWidth, 0);
        
        // Рендерим все очереди этого DST
        if (dstRoot.children && dstRoot.children.length > 0) {
            dstRoot.children.forEach(queue => {
                renderQueueRow(queue, table, maxTargetWidth, maxDstWidth, 1, dstRoot.name);
            });
        }
    });
    
    container.appendChild(table);
}

// Функция для отрисовки корневого DST узла
function renderDstRootRow(dstNode, table, maxTargetWidth, maxDstWidth, level) {
    const row = document.createElement('div');
    row.style.display = 'table-row';
    row.style.backgroundColor = '#f8f9fa'; // Светлый фон для корневых DST
    
    // Ячейка с именем DST
    const nameCell = document.createElement('div');
    nameCell.style.display = 'table-cell';
    nameCell.style.verticalAlign = 'middle';
    nameCell.style.padding = '12px 0';
    nameCell.style.borderBottom = '2px solid #dee2e6';
    nameCell.style.fontWeight = 'bold';
    
    // Проверяем, развернут ли узел
    const isExpanded = queueTreeExpanded[dstNode.name] !== false;
    const hasChildren = dstNode.children && dstNode.children.length > 0;
    
    // Создаем элемент DST
    const dstDiv = document.createElement('div');
    dstDiv.className = 'dst-root-item';
    dstDiv.style.display = 'flex';
    dstDiv.style.alignItems = 'center';
    dstDiv.style.cursor = 'pointer';
    
    // Индикатор развертывания
    if (hasChildren) {
        const expandIcon = document.createElement('i');
        expandIcon.className = `fas ${isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'}`;
        expandIcon.style.cursor = 'pointer';
        expandIcon.style.fontSize = '12px';
        expandIcon.style.color = '#3498db';
        expandIcon.style.marginRight = '8px';
        expandIcon.style.width = '15px';
        expandIcon.style.textAlign = 'center';
        expandIcon.onclick = (e) => {
            e.stopPropagation();
            toggleQueueNode(dstNode.name);
        };
        dstDiv.appendChild(expandIcon);
    } else {
        const spacer = document.createElement('span');
        spacer.style.width = '15px';
        spacer.style.display = 'inline-block';
        dstDiv.appendChild(spacer);
    }

    // Иконка DST
    const dstIcon = document.createElement('i');
    dstIcon.className = 'fas fa-project-diagram';
    dstIcon.style.color = '#3498db';
    dstIcon.style.fontSize = '14px';
    dstIcon.style.marginRight = '8px';
    dstDiv.appendChild(dstIcon);

    // Имя DST
    const nameSpan = document.createElement('span');
    nameSpan.className = 'dst-name';
    nameSpan.textContent = dstNode.name;
    nameSpan.style.color = '#2c3e50';
    nameSpan.style.fontSize = '15px';
    nameSpan.style.fontWeight = 'bold';
    dstDiv.appendChild(nameSpan);

    // Количество очередей в этом DST
    if (hasChildren) {
        const countSpan = document.createElement('span');
        countSpan.textContent = ` (${dstNode.children.length} очередей)`;
        countSpan.style.color = '#7f8c8d';
        countSpan.style.fontSize = '12px';
        countSpan.style.marginLeft = '10px';
        dstDiv.appendChild(countSpan);
    }

    // Иконка комментария (если есть комментарий у DST)
    if (dstNode.comment) {
        const commentIcon = document.createElement('i');
        commentIcon.className = 'fas fa-comment-alt';
        commentIcon.style.color = '#7f8c8d';
        commentIcon.style.fontSize = '11px';
        commentIcon.style.marginLeft = '15px';
        commentIcon.style.cursor = 'help';
        commentIcon.title = `Комментарий DST: ${dstNode.comment}`;
        commentIcon.onclick = (e) => {
            e.stopPropagation();
            showAlert(dstNode.comment, 'info');
        };
        dstDiv.appendChild(commentIcon);
    }

    // Пустое пространство для выравнивания
    const spacer = document.createElement('div');
    spacer.style.flex = '1';
    dstDiv.appendChild(spacer);

    // Статус DST (всегда включен)
    const statusDiv = document.createElement('div');
    statusDiv.className = 'dst-status';
    statusDiv.title = 'DST активен';
    statusDiv.style.width = '14px';
    statusDiv.style.height = '14px';
    statusDiv.style.borderRadius = '50%';
    statusDiv.style.backgroundColor = '#2ecc71';
    statusDiv.style.border = '2px solid #27ae60';
    statusDiv.style.marginLeft = 'auto';
    dstDiv.appendChild(statusDiv);

    dstDiv.onclick = () => {
        if (hasChildren) {
            toggleQueueNode(dstNode.name);
        }
    };

    nameCell.appendChild(dstDiv);
    
    // Пустые ячейки для TARGET и DST (так как это корневой DST)
    const targetCell = document.createElement('div');
    targetCell.style.display = 'table-cell';
    targetCell.style.verticalAlign = 'middle';
    targetCell.style.padding = '12px 10px';
    targetCell.style.borderBottom = '2px solid #dee2e6';
    targetCell.style.width = `${maxTargetWidth + 20}px`;
    targetCell.style.minWidth = '150px';
    
    // Пустая ячейка DST (так как это сам DST)
    const dstCell = document.createElement('div');
    dstCell.style.display = 'table-cell';
    dstCell.style.verticalAlign = 'middle';
    dstCell.style.padding = '12px 10px';
    dstCell.style.borderBottom = '2px solid #dee2e6';
    dstCell.style.width = `${maxDstWidth + 20}px`;
    dstCell.style.minWidth = '150px';
    
    // Ячейка лимита скорости (пустая для DST)
    const limitCell = document.createElement('div');
    limitCell.style.display = 'table-cell';
    limitCell.style.verticalAlign = 'middle';
    limitCell.style.padding = '12px 10px';
    limitCell.style.borderBottom = '2px solid #dee2e6';
    limitCell.style.textAlign = 'right';
    limitCell.style.width = '120px';
    limitCell.style.whiteSpace = 'nowrap';
    
    // Добавляем ячейки в строку
    row.appendChild(nameCell);
    row.appendChild(targetCell);
    row.appendChild(dstCell);
    row.appendChild(limitCell);
    
    table.appendChild(row);
}

// Функция для отрисовки строки очереди
function renderQueueRow(node, table, maxTargetWidth, maxDstWidth, level, parentDst = '') {
    const row = document.createElement('div');
    row.style.display = 'table-row';
    
    // Проверяем, развернут ли родительский DST
    if (parentDst && queueTreeExpanded[parentDst] === false) {
        return; // Не отображаем, если родительский DST свернут
    }
    
    // Ячейка с деревом и именем
    const nameCell = document.createElement('div');
    nameCell.style.display = 'table-cell';
    nameCell.style.verticalAlign = 'middle';
    nameCell.style.padding = level === 1 ? '8px 0' : '6px 0';
    nameCell.style.borderBottom = '1px solid #eee';
    
    // Проверяем, развернут ли узел
    const isExpanded = queueTreeExpanded[node.name] !== false;
    const hasChildren = node.children && node.children.length > 0;
    
    // Создаем элемент очереди
    const queueDiv = document.createElement('div');
    queueDiv.className = `queue-item-v2 ${node.enabled ? '' : 'disabled'}`;
    queueDiv.style.display = 'flex';
    queueDiv.style.alignItems = 'center';
    queueDiv.style.cursor = 'pointer';
    
    let prefix = '─ '.repeat(level - 1);
    if (level > 1) {
        prefix = '├' + prefix;
    }

    // Отступ для уровня вложенности
    const indent = document.createElement('span');
    indent.style.width = `${(level - 1) * 20 + 15}px`;
    indent.style.display = 'inline-block';
    queueDiv.appendChild(indent);

    // Индикатор развертывания
    if (hasChildren) {
        const expandIcon = document.createElement('i');
        expandIcon.className = `fas ${isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'}`;
        expandIcon.style.cursor = 'pointer';
        expandIcon.style.fontSize = level === 1 ? '11px' : '10px';
        expandIcon.style.color = '#666';
        expandIcon.style.marginRight = '5px';
        expandIcon.style.width = '15px';
        expandIcon.style.textAlign = 'center';
        expandIcon.onclick = (e) => {
            e.stopPropagation();
            toggleQueueNode(node.name);
        };
        queueDiv.appendChild(expandIcon);
    } else {
        const spacer = document.createElement('span');
        spacer.style.width = '15px';
        spacer.style.display = 'inline-block';
        queueDiv.appendChild(spacer);
    }

    // Имя очереди
    const nameSpan = document.createElement('span');
    nameSpan.className = 'queue-name';
    nameSpan.textContent = `${prefix} ${node.name}`;
    nameSpan.style.fontWeight = level === 1 ? 'bold' : 'normal';
    nameSpan.style.color = level === 1 ? '#2c3e50' : '#34495e';
    nameSpan.style.fontSize = level === 1 ? '14px' : '13px';
    nameSpan.style.marginRight = '20px';
    queueDiv.appendChild(nameSpan);

    // Иконка комментария (если есть комментарий)
    if (node.comment) {
        const commentIcon = document.createElement('i');
        commentIcon.className = 'fas fa-comment-alt';
        commentIcon.style.color = '#7f8c8d';
        commentIcon.style.fontSize = level === 1 ? '11px' : '10px';
        commentIcon.style.marginRight = '10px';
        commentIcon.style.cursor = 'help';
        commentIcon.title = `Комментарий: ${node.comment}`;
        commentIcon.onclick = (e) => {
            e.stopPropagation();
            showAlert(node.comment, 'info');
        };
        queueDiv.appendChild(commentIcon);
    }

    // Статус
    const statusDiv = document.createElement('div');
    statusDiv.className = `queue-status ${node.enabled ? '' : 'disabled'}`;
    statusDiv.title = node.enabled ? 'Включена' : 'Выключена';
    statusDiv.style.width = level === 1 ? '12px' : '10px';
    statusDiv.style.height = level === 1 ? '12px' : '10px';
    statusDiv.style.borderRadius = '50%';
    statusDiv.style.backgroundColor = node.enabled ? '#2ecc71' : '#e74c3c';
    statusDiv.style.border = `${level === 1 ? '2px' : '1px'} solid ${node.enabled ? '#27ae60' : '#c0392b'}`;
    statusDiv.style.marginLeft = 'auto';
    queueDiv.appendChild(statusDiv);

    queueDiv.onclick = () => {
        if (hasChildren) {
            toggleQueueNode(node.name);
        }
    };

    nameCell.appendChild(queueDiv);
    
    // Ячейка TARGET
    const targetCell = document.createElement('div');
    targetCell.style.display = 'table-cell';
    targetCell.style.verticalAlign = 'middle';
    targetCell.style.padding = level === 1 ? '8px 10px' : '6px 10px';
    targetCell.style.borderBottom = '1px solid #eee';
    targetCell.style.width = `${maxTargetWidth + 20}px`;
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
        const maxLength = level === 1 ? 25 : 20;
        if (displayTarget.length > maxLength) {
            displayTarget = displayTarget.substring(0, maxLength - 3) + '...';
        }
        
        targetDiv.textContent = displayTarget;
        targetDiv.title = `TARGET: ${targetText}`;
        targetDiv.style.backgroundColor = '#e8f4fd';
        targetDiv.style.color = '#2980b9';
        targetDiv.style.padding = level === 1 ? '4px 8px' : '3px 6px';
        targetDiv.style.borderRadius = '3px';
        targetDiv.style.fontSize = level === 1 ? '11px' : '10px';
        targetDiv.style.fontFamily = 'monospace';
        targetDiv.style.border = '1px solid #b3e0ff';
        targetDiv.style.whiteSpace = 'nowrap';
        targetDiv.style.overflow = 'hidden';
        targetDiv.style.textOverflow = 'ellipsis';
        targetDiv.style.maxWidth = `${maxTargetWidth}px`;
        targetCell.appendChild(targetDiv);
    }
    
    // Ячейка DST (пустая для обычных очередей, так как DST теперь в корне)
    const dstCell = document.createElement('div');
    dstCell.style.display = 'table-cell';
    dstCell.style.verticalAlign = 'middle';
    dstCell.style.padding = level === 1 ? '8px 10px' : '6px 10px';
    dstCell.style.borderBottom = '1px solid #eee';
    dstCell.style.width = `${maxDstWidth + 20}px`;
    dstCell.style.minWidth = '150px';
    
    // Ячейка лимита скорости (с выравниванием по правому краю)
    const limitCell = document.createElement('div');
    limitCell.style.display = 'table-cell';
    limitCell.style.verticalAlign = 'middle';
    limitCell.style.padding = level === 1 ? '8px 10px' : '6px 10px';
    limitCell.style.borderBottom = '1px solid #eee';
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
        limitDiv.style.padding = level === 1 ? '4px 8px' : '3px 6px';
        limitDiv.style.borderRadius = '3px';
        limitDiv.style.fontSize = level === 1 ? '11px' : '10px';
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
    
    // Рекурсивно отрисовываем детей (если узел развернут)
    if (hasChildren && isExpanded) {
        node.children.forEach(child => {
            renderQueueRow(child, table, maxTargetWidth, maxDstWidth, level + 1, parentDst);
        });
    }
}

// Переключение состояния узла (развернуть/свернуть)
function toggleQueueNode(queueName) {
    queueTreeExpanded[queueName] = !queueTreeExpanded[queueName];
    renderQueueTreeV2(queueTreeFiltered);
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
    renderQueueTreeV2(queueTreeFiltered);
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
    renderQueueTreeV2(queueTreeFiltered);
}

// Фильтрация дерева по имени
function filterQueueTree(searchTerm) {
    if (!searchTerm.trim()) {
        queueTreeFiltered = [...queueTreeData];
        renderQueueTreeV2(queueTreeFiltered);
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
    renderQueueTreeV2(queueTreeFiltered);
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
