/**
 * Hermes Agent 插件 - 通用 JavaScript 库
 * 用于 iStoreOS LuCI 界面
 */

// =============================================================================
// API 客户端
// =============================================================================
var HermesAPI = {
    /**
     * 调用 OpenClaw API 网关
     * @param {string} path - API 路径 (例如 "status", "chat")
     * @param {object} options - 请求选项
     * @param {string} [options.method] - HTTP 方法 (默认 GET)
     * @param {object} [options.body] - 请求体 (JSON 对象)
     * @returns {Promise<object>} - 解析后的 JSON 响应
     */
    call: function(path, options) {
        options = options || {};
        var method = options.method || 'GET';
        var body = options.body || null;

        // 构建目标 URL
        var baseUrl = 'http://' + hermesServerHost + ':' + hermesServerPort;
        var url = baseUrl + '/api/' + path;

        // 请求配置
        var xhr = new XMLHttpRequest();
        xhr.open(method, url, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.setRequestHeader('Accept', 'application/json');

        // API Key 认证
        if (hermesApiKey && hermesApiKey !== '') {
            xhr.setRequestHeader('Authorization', 'Bearer ' + hermesApiKey);
        }

        return new Promise(function(resolve, reject) {
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch (e) {
                        resolve(xhr.responseText);
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
                reject(new Error('无法连接到服务器 ' + baseUrl + '。请检查设置。'));
            };
            xhr.ontimeout = function() {
                reject(new Error('请求超时'));
            };
            xhr.timeout = 30000;

            if (body) {
                xhr.send(JSON.stringify(body));
            } else {
                xhr.send();
            }
        });
    },

    /**
     * 获取服务器状态
     */
    getStatus: function() {
        return this.call('status');
    },

    /**
     * 发送聊天消息
     * @param {string} message - 消息内容
     * @param {string} [sessionId] - 会话 ID
     */
    sendChat: function(message, sessionId) {
        return this.call('chat', {
            method: 'POST',
            body: {
                message: message,
                session_id: sessionId || null
            }
        });
    },

    /**
     * 获取会话列表
     */
    getSessions: function() {
        return this.call('sessions');
    },

    /**
     * 获取会话消息
     * @param {string} sessionId - 会话 ID
     */
    getSessionMessages: function(sessionId) {
        return this.call('sessions/' + encodeURIComponent(sessionId) + '/messages');
    },

    /**
     * 健康检查
     */
    healthCheck: function() {
        return this.call('health');
    }
};

// =============================================================================
// 仪表盘功能
// =============================================================================

/**
 * 刷新仪表盘状态
 */
function hermesRefreshStatus() {
    HermesAPI.getStatus()
        .then(function(data) {
            // 状态卡片
            var cardStatus = document.getElementById('card-status');
            if (cardStatus) {
                cardStatus.classList.remove('loading');
                var dot = cardStatus.querySelector('.hermes-status-dot');
                var text = cardStatus.querySelector('.hermes-status-text');
                if (data.hermes_api_running) {
                    dot.className = 'hermes-status-dot hermes-status-ok';
                    text.textContent = '✓ 已连接';
                } else {
                    dot.className = 'hermes-status-dot hermes-status-error';
                    text.textContent = '✗ 未连接';
                }
            }

            // 版本
            var cardVersion = document.getElementById('card-version');
            if (cardVersion) {
                cardVersion.classList.remove('loading');
                var body = cardVersion.querySelector('.hermes-card-body');
                body.textContent = data.hermes_version || '—';
            }

            // 活跃会话
            var cardSessions = document.getElementById('card-sessions');
            if (cardSessions) {
                cardSessions.classList.remove('loading');
                var body = cardSessions.querySelector('.hermes-card-body');
                body.textContent = data.session_count !== null && data.session_count !== undefined
                    ? data.session_count + ' 个活跃'
                    : '—';
            }

            // 响应时间 (健康检查的延迟)
            var cardUptime = document.getElementById('card-uptime');
            if (cardUptime) {
                cardUptime.classList.remove('loading');
                var body = cardUptime.querySelector('.hermes-card-body');
                // 用健康检查测量延迟
                var startTime = Date.now();
                HermesAPI.healthCheck().then(function() {
                    var ms = Date.now() - startTime;
                    body.textContent = ms + 'ms';
                }).catch(function() {
                    body.textContent = '—';
                });
            }

            // 加载会话列表
            hermesLoadSessions();
        })
        .catch(function(err) {
            // 所有卡片显示错误
            var cards = document.querySelectorAll('.hermes-card.loading');
            cards.forEach(function(card) {
                card.classList.remove('loading');
                var body = card.querySelector('.hermes-card-body');
                if (body) body.textContent = '❌ 错误';
            });

            var cardStatus = document.getElementById('card-status');
            if (cardStatus) {
                var dot = cardStatus.querySelector('.hermes-status-dot');
                var text = cardStatus.querySelector('.hermes-status-text');
                dot.className = 'hermes-status-dot hermes-status-error';
                text.textContent = '✗ ' + err.message;
            }

            // 显示错误到会话列表
            var sessionList = document.getElementById('hermes-session-list');
            if (sessionList) {
                sessionList.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">'
                    + '⚠️ ' + err.message
                    + '</div>';
            }
        });
}

/**
 * 加载会话列表
 */
function hermesLoadSessions() {
    HermesAPI.getSessions()
        .then(function(data) {
            var list = document.getElementById('hermes-session-list');
            if (!list) return;

            var sessions = data.sessions || [];
            if (sessions.length === 0) {
                list.innerHTML = '<div class="hermes-table-placeholder"><%:暂无最近的会话%></div>';
                return;
            }

            var html = '<table class="cbi-section-table">';
            html += '<tr><th><%:会话 ID%></th><th><%:来源%></th><th><%:模型%></th><th><%:消息数%></th><th><%:最后活跃%></th><th><%:操作%></th></tr>';

            sessions.forEach(function(session) {
                var lastActive = session.last_active
                    ? new Date(session.last_active * 1000).toLocaleString()
                    : '—';
                html += '<tr>';
                html += '<td>' + (session.id || session.title || '—').substring(0, 20) + '</td>';
                html += '<td>' + (session.source || '—') + '</td>';
                html += '<td>' + (session.model || '—') + '</td>';
                html += '<td>' + (session.message_count || 0) + '</td>';
                html += '<td>' + lastActive + '</td>';
                html += '<td><a href="<%=url("admin/services/hermes/chat")%>?session=' + encodeURIComponent(session.id) + '" class="cbi-button cbi-button-apply" style="font-size:12px;padding:2px 8px;">查看</a></td>';
                html += '</tr>';
            });

            html += '</table>';
            list.innerHTML = html;
        })
        .catch(function(err) {
            var list = document.getElementById('hermes-session-list');
            if (list) {
                list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
            }
        });
}
