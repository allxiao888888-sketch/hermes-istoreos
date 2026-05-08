/**
 * Hermes Agent 插件 v2.0 — AI 聊天界面 JavaScript
 * 本地 LLM API 聊天，路由器控制集成
 */

var hermesChatMessages = [];  // 消息历史
var hermesIsSending = false;

/**
 * 初始化聊天界面
 */
function hermesChatInit() {
    var input = document.getElementById('hermes-chat-input');
    if (input) {
        input.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        });
        input.focus();
    }
}

/**
 * 发送聊天消息
 */
function hermesSendMessage() {
    var input = document.getElementById('hermes-chat-input');
    var sendBtn = document.getElementById('hermes-chat-send-btn');
    var message = input.value.trim();

    if (!message || hermesIsSending) return;

    hermesIsSending = true;
    sendBtn.disabled = true;
    sendBtn.textContent = '⏳ 思考中...';
    input.value = '';
    input.style.height = 'auto';

    // 隐藏欢迎界面
    var welcome = document.querySelector('.hermes-chat-welcome');
    if (welcome) welcome.style.display = 'none';

    // 添加用户消息
    hermesAddMessage('user', message);
    hermesChatMessages.push({ role: 'user', content: message });

    // 思考占位
    var thinkingId = hermesAddMessage('assistant', '🤔 思考中...', true);

    // 调用本地 API
    HermesAPI.sendChat(message, hermesChatMessages)
        .then(function(data) {
            hermesRemoveThinking(thinkingId);

            if (data.error) {
                hermesAddMessage('system', '⚠️ ' + data.error);
                if (data.needs_config) {
                    hermesAddMessage('system', '请进入「设置」页面配置 API 密钥');
                }
            } else {
                var response = data.response || '(无响应)';
                // 如果服务端因内存不足清空了历史，同步清空前端
                if (data.cleared) {
                    hermesChatMessages = [];
                    hermesAddMessage('system', '🔄 内存使用过高，对话已自动重置');
                }
                hermesAddMessage('assistant', response, false, data.model);
                hermesChatMessages.push({
                    role: 'assistant',
                    content: response,
                    model: data.model
                });
            }
        })
        .catch(function(err) {
            hermesRemoveThinking(thinkingId);
            hermesAddMessage('system', '⚠️ ' + err.message);
        })
        .finally(function() {
            hermesIsSending = false;
            sendBtn.disabled = false;
            sendBtn.textContent = '发送 ▶';
            input.focus();
        });
}

/**
 * 快速发送预设消息
 */
function hermesSendQuick(message) {
    var input = document.getElementById('hermes-chat-input');
    if (input) {
        input.value = message;
        hermesSendMessage();
    }
}

/**
 * 清空聊天
 */
function hermesClearChat() {
    if (!confirm('确定清空当前对话？')) return;

    var msgContainer = document.getElementById('hermes-chat-messages');
    var welcome = document.querySelector('.hermes-chat-welcome');

    msgContainer.innerHTML = '';
    if (welcome) {
        msgContainer.appendChild(welcome);
        welcome.style.display = 'block';
    } else {
        msgContainer.innerHTML = hermesCreateWelcomeHTML();
    }

    hermesChatMessages = [];
}

/**
 * 添加消息到界面
 */
function hermesAddMessage(role, content, isThinking, model) {
    var msgContainer = document.getElementById('hermes-chat-messages');
    var msgDiv = document.createElement('div');
    msgDiv.className = 'hermes-chat-msg hermes-chat-msg-' + role;

    var avatar = role === 'user' ? '👤' : (role === 'system' ? '⚙️' : '🦞');
    var roleName = role === 'user' ? '你' : (role === 'system' ? '系统' : 'AI 助手');
    var modelInfo = model ? ' · ' + model : '';

    var thinkingClass = isThinking ? ' hermes-chat-thinking' : '';

    msgDiv.innerHTML = '<div class="hermes-chat-msg-avatar">' + avatar + '</div>'
        + '<div class="hermes-chat-msg-content">'
        + '<div class="hermes-chat-msg-header">'
        + '<strong>' + roleName + '</strong>'
        + '<span class="hermes-chat-msg-meta">' + modelInfo + '</span>'
        + '</div>'
        + '<div class="hermes-chat-msg-text' + thinkingClass + '">'
        + hermesFormatMessage(content)
        + '</div>'
        + '</div>';

    if (isThinking) {
        var id = 'thinking-' + Date.now();
        msgDiv.dataset.thinkingId = id;
        msgDiv.id = id;
    }

    msgContainer.appendChild(msgDiv);
    msgContainer.scrollTop = msgContainer.scrollHeight;

    return isThinking ? msgDiv.id : null;
}

/**
 * 移除思考占位
 */
function hermesRemoveThinking(id) {
    var el = document.getElementById(id);
    if (el) el.remove();
}

/**
 * 格式化消息
 */
function hermesFormatMessage(text) {
    if (!text) return '';

    // HTML 转义
    text = text.replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // 代码块
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
        return '<pre><code class="lang-' + lang + '">'
            + code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
            + '</code></pre>';
    });

    // 行内代码
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Markdown 链接
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // 换行
    text = text.replace(/\n/g, '<br>');

    return text;
}

/**
 * 创建欢迎界面 HTML
 */
function hermesCreateWelcomeHTML() {
    return '<div class="hermes-chat-welcome">'
        + '<div class="hermes-chat-welcome-icon">🦞</div>'
        + '<h3>你好！我是路由器 AI 助手</h3>'
        + '<p>我已经连接到本地 Hermes API，可以帮你管理 iStoreOS 路由器。</p>'
        + '<div class="hermes-chat-suggestions">'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'查看路由器系统状态\')">🖥️ 系统状态</button>'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'列出所有已安装的软件包\')">📦 软件包列表</button>'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'查看运行中的服务\')">⚙️ 运行服务</button>'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'查看网络接口状态\')">🌐 网络状态</button>'
        + '</div></div>';
}
