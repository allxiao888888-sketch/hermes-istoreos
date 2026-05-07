/**
 * Hermes Agent 插件 v2.0 — 通用 JavaScript 库
 * 本地 API 客户端 + 仪表盘功能
 * 所有请求通过 LuCI Lua API 代理转发到本地 Python 服务
 */

// =============================================================================
// API 客户端 — 通过 LuCI 代理调用本地 API
// =============================================================================
var HermesAPI = {
    /**
     * 通过 LuCI 代理调用本地 Hermes API
     * @param {string} path - API 路径 (例如 "status", "chat")
     * @param {object} options - 请求选项
     * @returns {Promise<object>}
     */
    call: function(path, options) {
        options = options || {};
        var method = options.method || 'GET';
        var body = options.body || null;

        return new Promise(function(resolve, reject) {
            // 使用 LuCI 内建方式
            var xhr = new XMLHttpRequest();
            var url = location.pathname.replace(/\/[^/]+$/, '/api') + 
                      '?path=' + encodeURIComponent(path) + 
                      '&_method=' + method;

            xhr.open('POST', url, true);
            xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');

            var params = 'path=' + encodeURIComponent(path) +
                         '&_method=' + method;

            if (body) {
                params += '&body=' + encodeURIComponent(JSON.stringify(body));
            }

            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch (e) {
                        resolve({ raw: xhr.responseText });
                    }
                } else {
                    var errMsg = 'API 错误 (' + xhr.status + '): ';
                    try {
                        var errData = JSON.parse(xhr.responseText);
                        errMsg += errData.detail || errData.error || xhr.responseText;
                    } catch (e) {
                        errMsg += xhr.statusText;
                    }
                    reject(new Error(errMsg));
                }
            };

            xhr.onerror = function() {
                reject(new Error('无法连接到本地 API 服务器。请检查服务是否运行。'));
            };

            xhr.ontimeout = function() {
                reject(new Error('请求超时'));
            };
            xhr.timeout = 60000;

            xhr.send(params);
        });
    },

    /**
     * 获取 API 服务器状态
     */
    getStatus: function() {
        return this.call('status');
    },

    /**
     * 健康检查
     */
    healthCheck: function() {
        return this.call('health');
    },

    /**
     * 发送聊天消息
     */
    sendChat: function(message, history) {
        return this.call('chat', {
            method: 'POST',
            body: {
                message: message,
                messages: history || []
            }
        });
    },

    /**
     * 获取路由器系统信息
     */
    getRouterInfo: function() {
        return this.call('router/info');
    },

    /**
     * 获取软件包列表
     */
    getPackages: function(query) {
        var path = 'router/packages';
        if (query) path += '?q=' + encodeURIComponent(query);
        return this.call(path);
    },

    /**
     * 安装软件包
     */
    installPackage: function(name) {
        return this.call('router/packages/install', {
            method: 'POST',
            body: { name: name }
        });
    },

    /**
     * 卸载软件包
     */
    removePackage: function(name) {
        return this.call('router/packages/remove', {
            method: 'POST',
            body: { name: name }
        });
    },

    /**
     * 更新软件包列表
     */
    updatePackages: function() {
        return this.call('router/packages/update', {
            method: 'POST'
        });
    },

    /**
     * 获取服务列表
     */
    getServices: function() {
        return this.call('router/services');
    },

    /**
     * 服务操作
     */
    serviceAction: function(action, name) {
        return this.call('router/services/' + action + '/' + name, {
            method: 'POST'
        });
    },

    /**
     * 获取网络信息
     */
    getNetwork: function() {
        return this.call('router/network');
    },

    /**
     * 执行命令
     */
    execCommand: function(command, timeout) {
        return this.call('exec', {
            method: 'POST',
            body: {
                command: command,
                timeout: timeout || 30
            }
        });
    }
};

// =============================================================================
// 仪表盘功能
// =============================================================================

/**
 * 刷新仪表盘状态
 */
function hermesRefreshStatus() {
    // 1. 获取 API 状态
    HermesAPI.getStatus()
        .then(function(data) {
            // API 状态
            var cardStatus = document.getElementById('card-status');
            if (cardStatus) {
                cardStatus.classList.remove('loading');
                var dot = cardStatus.querySelector('.hermes-status-dot');
                var text = cardStatus.querySelector('.hermes-status-text');
                if (data.version) {
                    dot.className = 'hermes-status-dot hermes-status-ok';
                    text.textContent = '✓ 运行中 v' + data.version;
                } else {
                    dot.className = 'hermes-status-dot hermes-status-error';
                    text.textContent = '✗ 异常';
                }
            }

            // AI 连接状态
            var cardLLM = document.getElementById('card-llm');
            if (cardLLM) {
                cardLLM.classList.remove('loading');
                var body = cardLLM.querySelector('.hermes-card-body');
                if (data.config_ok) {
                    body.textContent = data.config_provider + ' ✓';
                } else {
                    body.innerHTML = '⚠ 未配置';
                }
            }
        })
        .catch(function(err) {
            var cards = document.querySelectorAll('.hermes-card.loading');
            cards.forEach(function(card) {
                card.classList.remove('loading');
            });
            var cardStatus = document.getElementById('card-status');
            if (cardStatus) {
                var dot = cardStatus.querySelector('.hermes-status-dot');
                var text = cardStatus.querySelector('.hermes-status-text');
                dot.className = 'hermes-status-dot hermes-status-error';
                text.textContent = '✗ ' + err.message.substring(0, 40);
            }
        });

    // 2. 获取路由器信息
    HermesAPI.getRouterInfo()
        .then(function(info) {
            // 主机名
            var cardHost = document.getElementById('card-hostname');
            if (cardHost) {
                cardHost.classList.remove('loading');
                var body = cardHost.querySelector('.hermes-card-body');
                body.textContent = info.hostname || '—';
            }

            // 运行时间
            var cardUptime = document.getElementById('card-uptime');
            if (cardUptime) {
                cardUptime.classList.remove('loading');
                var body = cardUptime.querySelector('.hermes-card-body');
                body.textContent = info.uptime || '—';
            }

            // CPU
            var cardCPU = document.getElementById('card-cpu');
            if (cardCPU) {
                cardCPU.classList.remove('loading');
                var body = cardCPU.querySelector('.hermes-card-body');
                body.textContent = info.cpu && info.cpu.cores ? info.cpu.cores + ' 核' : '—';
                var sub = cardCPU.querySelector('.hermes-card-sub');
                if (sub && info.loadavg && info.loadavg.length) {
                    sub.textContent = info.cpu.model ? info.cpu.model.substring(0, 25) : '负载: ' + info.loadavg.join(' / ');
                }
            }

            // 内存
            var cardMem = document.getElementById('card-memory');
            if (cardMem) {
                cardMem.classList.remove('loading');
                var body = cardMem.querySelector('.hermes-card-body');
                if (info.memory && info.memory.usage_pct !== undefined) {
                    body.textContent = info.memory.usage_pct + '%';
                    var sub = cardMem.querySelector('.hermes-card-sub');
                    sub.textContent = info.memory.used_mb + ' / ' + info.memory.total_mb + ' MB';
                } else {
                    body.textContent = '—';
                }
            }

            // 磁盘
            var cardDisk = document.getElementById('card-disk');
            if (cardDisk) {
                cardDisk.classList.remove('loading');
                var body = cardDisk.querySelector('.hermes-card-body');
                if (info.disk && info.disk.partitions && info.disk.partitions.length > 0) {
                    var root = info.disk.partitions[0];
                    body.textContent = root.usage_pct || '—';
                    var sub = cardDisk.querySelector('.hermes-card-sub');
                    sub.textContent = root.mount || '根分区';
                } else {
                    body.textContent = '—';
                }
            }
        })
        .catch(function(err) {
            var cards = document.querySelectorAll('.hermes-card.loading');
            cards.forEach(function(c) { c.classList.remove('loading'); });
        });

    // 3. 获取网络信息
    HermesAPI.getNetwork()
        .then(function(net) {
            var list = document.getElementById('hermes-network-list');
            if (!list) return;

            if (!net.interfaces || net.interfaces.length === 0) {
                list.innerHTML = '<div class="hermes-table-placeholder">无法获取网络信息</div>';
                return;
            }

            var html = '<table class="cbi-section-table">' +
                '<tr><th><%:接口%></th><th><%:状态%></th><th><%:MAC 地址%></th><th><%:IP 地址%></th></tr>';

            net.interfaces.forEach(function(iface) {
                var stateClass = iface.state === 'up' ? 'hermes-status-ok' : 'hermes-status-error';
                html += '<tr>' +
                    '<td>' + iface.name + '</td>' +
                    '<td><span class="hermes-status-dot ' + stateClass + '" style="width:8px;height:8px;display:inline-block;vertical-align:middle;"></span> ' + iface.state + '</td>' +
                    '<td>' + (iface.mac || '—') + '</td>' +
                    '<td>' + (iface.ip || '—') + '</td>' +
                    '</tr>';
            });

            if (net.default_gateway) {
                html += '<tr><td colspan="4" style="color:var(--text-muted,#666);font-size:12px;">默认网关: ' + net.default_gateway + '</td></tr>';
            }

            html += '</table>';
            list.innerHTML = html;
        })
        .catch(function() {});

    // 4. 获取软件包数量
    HermesAPI.getPackages()
        .then(function(pkgs) {
            var cardPkg = document.getElementById('card-packages');
            if (!cardPkg) return;
            cardPkg.classList.remove('loading');
            var body = cardPkg.querySelector('.hermes-card-body');
            var sub = cardPkg.querySelector('.hermes-card-sub');
            body.textContent = pkgs.count || pkgs.packages.length || '—';
            if (sub) sub.textContent = '已安装';
        })
        .catch(function() {});
}
