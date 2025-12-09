        let currentDevice = null;
        let queueTree = [];

        // Загрузка при старте
        document.addEventListener('DOMContentLoaded', function() {
            loadDevices();
            loadSettings();
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

                            // Определяем текст кнопки
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
            // Если уже подключены к этому устройству - отключаемся
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
                        }

                        // Обновляем список устройств
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

                        // Обновляем список устройств
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

                    // Очищаем форму
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

            fetch(`/api/check_dhcp?ip=${encodeURIComponent(ip)}`)
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

        // Поиск очередей для IP
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
                            data.queues.forEach(queue => {
                                const option = document.createElement('option');
                                option.value = queue.name;
                                option.textContent = `${queue.name} (${queue.ip_count} IP)`;
                                select.appendChild(option);
                            });
                            showAlert(`Найдено ${data.count} подходящих очередей`, 'success');
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

        // Добавление сотрудника
        function addEmployee() {
            const employeeData = {
                full_name: document.getElementById('full-name').value.trim(),
                position: document.getElementById('position').value.trim(),
                ip: document.getElementById('ip-address').value.trim(),
                mac: document.getElementById('mac-address').value.trim(),
                internet_access: document.getElementById('internet-access').checked,
                queue: document.getElementById('queue-select').value
            };

            // Валидация
            if (!employeeData.full_name || !employeeData.position || !employeeData.ip) {
                showAlert('Заполните обязательные поля (ФИО, Должность, IP)', 'error');
                return;
            }

            if (!currentDevice) {
                showAlert('Сначала подключитесь к устройству', 'error');
                return;
            }

            const resultsDiv = document.getElementById('employee-results');
            resultsDiv.innerHTML = '<div class="alert alert-info">Добавляем сотрудника...</div>';

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

        // Загрузка дерева очередей
        function loadQueueTree() {
            if (!currentDevice) {
                showAlert('Сначала подключитесь к устройству', 'error');
                return;
            }

            fetch('/api/tree')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        queueTree = data.tree;
                        renderQueueTree(data.tree);

                        // Обновляем статистику
                        if (data.stats) {
                            const statsText = `Очередей: ${data.stats.total_queues} (вкл: ${data.stats.enabled_queues})`;
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
            fetch(`/api/check_dhcp?ip=${encodeURIComponent(ip)}`)
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
                                    html += `<div class="result-item success">
                                        ✅ Подходящих очередей: ${queueData.count}
                                    </div>`;
                                } else {
                                    html += `<div class="result-item info">ℹ️ Подходящих очередей не найдено</div>`;
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

        // Вспомогательная функция для показа уведомлений
        function showAlert(message, type = 'info') {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type}`;
            alertDiv.textContent = message;

            // Добавляем в начало контента
            const content = document.querySelector('.content');
            content.insertBefore(alertDiv, content.firstChild);

            // Удаляем через 5 секунд
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.parentNode.removeChild(alertDiv);
                }
            }, 5000);
        }
