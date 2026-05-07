/**
 * Hermes Agent 插件 - 聊天界面 JavaScript
 * 为 iStoreOS 提供类似 ChatGPT 的交互体验
 */

var hermesCurrentSessionId = null;
var hermesChatHistory = [];
var hermesIsSending = false;

/**
 * 初始化聊天界面
 */
function hermesChatInit() {
    // 从 URL 参数恢复会话
    var params = new URLSearchParams(window.location.search);
    var sessionId = params.get('session');
    if (sessionId) {
        hermesCurrentSessionId = sessionId;
        hermesLoadHistory(sessionId);
        document.getElementById('hermes-chat-session-badge').textContent =
            '会话: ' + sessionId.substring(0, 8);
    }

    // 输入框自动调整高度
    var input = document.getElementById('hermes-chat-input');
    if (input) {
        input.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        });
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

    // 禁用到发送状态
    hermesIsSending = true;
    sendBtn.disabled = true;
    sendBtn.textContent = '⏳ 发送中...';
    input.value = '';
    input.style.height = 'auto';

    // 移除欢迎界面
    var welcome = document.querySelector('.hermes-chat-welcome');
    if (welcome) {
        welcome.style.display = 'none';
    }

    // 添加用户消息到界面
    hermesAddMessage('user', message);
    hermesChatHistory.push({ role: 'user', content: message });

    // 添加 "思考中..." 占位
    var thinkingId = hermesAddMessage('assistant', '🤔 思考中...', true);

    // 调用 API
    HermesAPI.sendChat(message, hermesCurrentSessionId)
        .then(function(data) {
            // 移除思考占位
            hermesRemoveThinking(thinkingId);

            // 更新会话 ID
            if (data.session_id && !hermesCurrentSessionId) {
                hermesCurrentSessionId = data.session_id;
                document.getElementById('hermes-chat-session-badge').textContent =
                    '会话: ' + data.session_id.substring(0, 8);
            }

            // 添加回复
            hermesAddMessage('assistant', data.response, false, data.model);
            hermesChatHistory.push({
                role: 'assistant',
                content: data.response,
                model: data.model
            });
        })
        .catch(function(err) {
            // 移除思考占位
            hermesRemoveThinking(thinkingId);

            // 显示错误
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

    // 保留欢迎界面
    msgContainer.innerHTML = '';
    if (welcome) {
        msgContainer.appendChild(welcome);
        welcome.style.display = 'block';
    } else {
        // 重新创建欢迎界面
        msgContainer.innerHTML = hermesCreateWelcomeHTML();
    }

    hermesCurrentSessionId = null;
    hermesChatHistory = [];
    document.getElementById('hermes-chat-session-badge').textContent = '新会话';
}

/**
 * 加载历史会话
 */
function hermesLoadHistory(sessionId) {
    var msgContainer = document.getElementById('hermes-chat-messages');
    var welcome = document.querySelector('.hermes-chat-welcome');
    if (welcome) welcome.style.display = 'none';

    msgContainer.innerHTML = '<div class="hermes-chat-loading">⏳ 加载会话记录...</div>';

    HermesAPI.getSessionMessages(sessionId)
        .then(function(data) {
            msgContainer.innerHTML = '';
            var messages = data.messages || [];

            messages.forEach(function(msg) {
                if (msg.role === 'user') {
                    hermesAddMessage('user', msg.content || '');
                } else if (msg.role === 'assistant') {
                    hermesAddMessage('assistant', msg.content || '(无文本响应)');
                }
            });

            if (messages.length === 0) {
                msgContainer.innerHTML = '<div class="hermes-chat-welcome" style="display:block;">'
                    + '<div class="hermes-chat-welcome-icon">🤖</div>'
                    + '<h3>空会话</h3>'
                    + '<p>该会话没有消息记录。</p>'
                    + '</div>';
            }

            // 滚动到底部
            msgContainer.scrollTop = msgContainer.scrollHeight;
        })
        .catch(function(err) {
            msgContainer.innerHTML = '<div class="hermes-chat-welcome" style="display:block;">'
                + '<div class="hermes-chat-welcome-icon">⚠️</div>'
                + '<h3>加载失败</h3>'
                + '<p>' + err.message + '</p>'
                + '</div>';
        });
}

/**
 * 添加消息到界面
 */
function hermesAddMessage(role, content, isThinking, model) {
    var msgContainer = document.getElementById('hermes-chat-messages');
    var msgDiv = document.createElement('div');
    msgDiv.className = 'hermes-chat-msg hermes-chat-msg-' + role;

    var avatar = role === 'user' ? '👤' : (role === 'system' ? '⚙️' : '🤖');
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

    // 如果是思考中，生成唯一 ID
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
 * 移除思考中的消息
 */
function hermesRemoveThinking(id) {
    var el = document.getElementById(id);
    if (el) {
        el.remove();
    }
}

/**
 * 格式化消息文本（支持代码块和链接）
 */
function hermesFormatMessage(text) {
    if (!text) return '';

    // HTML 转义
    text = text.replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // 代码块 (```)
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
        return '<pre><code class="lang-' + lang + '">'
            + code.replace(/</g, '&lt;').replace(/>/g, '&gt;')
            + '</code></pre>';
    });

    // 行内代码 (`code`)
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Markdown 链接
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // 换行转 <br>
    text = text.replace(/\n/g, '<br>');

    return text;
}

/**
 * 创建欢迎界面 HTML
 */
function hermesCreateWelcomeHTML() {
    return '<div class="hermes-chat-welcome">'
        + '<div class="hermes-chat-welcome-icon">🤖</div>'
        + '<h3>你好！我是你的 AI 助手</h3>'
        + '<p>我已经连接到 macOS 上的 Hermes Agent。有什么可以帮你的？</p>'
        + '<div class="hermes-chat-suggestions">'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'帮我查询系统状态\')">🖥️ 查询系统状态</button>'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'今天有什么待办事项？\')">📋 待办事项</button>'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'帮我写一段 Python 代码\')">💻 编写代码</button>'
        + '<button class="hermes-chat-suggestion" onclick="hermesSendQuick(\'搜索最新的科技新闻\')">🔍 搜索新闻</button>'
        + '</div></div>';
}
