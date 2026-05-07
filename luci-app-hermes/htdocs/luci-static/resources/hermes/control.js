/**
 * Hermes Agent 插件 v2.0 — 路由器管理 JavaScript
 * 软件包管理 + 服务管理 + 命令终端
 */

// =============================================================================
// 标签页切换
// =============================================================================

function hermesSwitchTab(tabName) {
    // 切换标签按钮高亮
    document.querySelectorAll('.hermes-tab').forEach(function(tab) {
        tab.classList.remove('hermes-tab-active');
        if (tab.dataset.tab === tabName) {
            tab.classList.add('hermes-tab-active');
        }
    });

    // 切换内容
    document.querySelectorAll('.hermes-tab-content').forEach(function(content) {
        content.classList.remove('hermes-tab-content-active');
    });

    var target = document.getElementById('hermes-tab-' + tabName);
    if (target) {
        target.classList.add('hermes-tab-content-active');
    }

    // 加载对应数据
    if (tabName === 'services') hermesRefreshServices();
    if (tabName === 'system') hermesLoadSystemInfo();
}

// =============================================================================
// 软件包管理
// =============================================================================

function hermesSearchPackages() {
    var input = document.getElementById('hermes-pkg-search');
    var query = input ? input.value.trim() : '';
    var list = document.getElementById('hermes-pkg-list');

    if (!list) return;
    list.innerHTML = '<div class="hermes-table-placeholder">⏳ 正在搜索...</div>';

    HermesAPI.getPackages(query)
        .then(function(data) {
            var pkgs = data.packages || [];

            if (pkgs.length === 0) {
                list.innerHTML = '<div class="hermes-table-placeholder">'
                    + (query ? '未找到匹配 "' + query + '" 的软件包' : '暂无已安装的软件包')
                    + '</div>';
                return;
            }

            var html = '<div style="margin-bottom:6px;color:var(--text-muted,#666);font-size:12px;">共 ' + pkgs.length + ' 个软件包</div>';
            html += '<table class="cbi-section-table">' +
                '<tr><th>软件包</th><th>版本</th><th>操作</th></tr>';

            pkgs.forEach(function(pkg) {
                html += '<tr>' +
                    '<td>' + hermesEscape(pkg.name) + '</td>' +
                    '<td style="font-size:12px;color:var(--text-muted,#666);">' + hermesEscape(pkg.version || '—') + '</td>' +
                    '<td style="white-space:nowrap;">' +
                    '<button class="cbi-button cbi-button-apply" style="font-size:12px;padding:2px 8px;margin-right:4px;" onclick="hermesInstallPackage(\'' + hermesEscape(pkg.name) + '\')">安装</button>' +
                    '<button class="cbi-button cbi-button-reset" style="font-size:12px;padding:2px 8px;" onclick="hermesRemovePackage(\'' + hermesEscape(pkg.name) + '\')">卸载</button>' +
                    '</td>' +
                    '</tr>';
            });

            html += '</table>';
            list.innerHTML = html;
        })
        .catch(function(err) {
            list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

function hermesInstallPackage(name) {
    if (!confirm('确定要安装 ' + name + ' 吗？')) return;

    var list = document.getElementById('hermes-pkg-list');
    list.innerHTML = '<div class="hermes-table-placeholder">⏳ 正在安装 ' + name + '...</div>';

    HermesAPI.installPackage(name)
        .then(function(data) {
            var msg = data.success ? '✅ ' + name + ' 安装成功' : '❌ 安装失败: ' + (data.output || '');
            list.innerHTML = '<div class="hermes-table-placeholder">' + msg + '</div>';
            // 刷新列表
            setTimeout(hermesSearchPackages, 1500);
        })
        .catch(function(err) {
            list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

function hermesRemovePackage(name) {
    if (!confirm('⚠️ 确定要卸载 ' + name + ' 吗？')) return;

    var list = document.getElementById('hermes-pkg-list');
    list.innerHTML = '<div class="hermes-table-placeholder">⏳ 正在卸载 ' + name + '...</div>';

    HermesAPI.removePackage(name)
        .then(function(data) {
            var msg = data.success ? '✅ ' + name + ' 已卸载' : '❌ 卸载失败: ' + (data.output || '');
            list.innerHTML = '<div class="hermes-table-placeholder">' + msg + '</div>';
            setTimeout(hermesSearchPackages, 1500);
        })
        .catch(function(err) {
            list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

function hermesUpdatePackages() {
    var list = document.getElementById('hermes-pkg-list');
    list.innerHTML = '<div class="hermes-table-placeholder">⏳ 正在更新软件包列表...</div>';

    HermesAPI.updatePackages()
        .then(function(data) {
            var msg = data.success ? '✅ 软件包列表已更新' : '❌ 更新失败: ' + (data.output || '');
            list.innerHTML = '<div class="hermes-table-placeholder">' + msg + '</div>';
            setTimeout(hermesSearchPackages, 1000);
        })
        .catch(function(err) {
            list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

// =============================================================================
// 服务管理
// =============================================================================

function hermesRefreshServices() {
    var list = document.getElementById('hermes-svc-list');
    if (!list) return;
    list.innerHTML = '<div class="hermes-table-placeholder">⏳ 正在加载服务列表...</div>';

    HermesAPI.getServices()
        .then(function(data) {
            var services = data.services || [];

            if (services.length === 0) {
                list.innerHTML = '<div class="hermes-table-placeholder">暂无服务</div>';
                return;
            }

            var html = '<div style="margin-bottom:6px;color:var(--text-muted,#666);font-size:12px;">共 ' + services.length + ' 个服务</div>';
            html += '<table class="cbi-section-table">' +
                '<tr><th>服务名</th><th>运行状态</th><th>开机自启</th><th>操作</th></tr>';

            services.forEach(function(svc) {
                var runningDot = svc.running ? 'hermes-status-ok' : 'hermes-status-error';
                var runningText = svc.running ? '运行中' : '已停止';
                var enabledDot = svc.enabled ? 'hermes-status-ok' : 'hermes-status-error';
                var enabledText = svc.enabled ? '已启用' : '已禁用';

                html += '<tr>' +
                    '<td>' + hermesEscape(svc.name) + '</td>' +
                    '<td><span class="hermes-status-dot ' + runningDot + '" style="width:8px;height:8px;display:inline-block;vertical-align:middle;"></span> ' + runningText + '</td>' +
                    '<td><span class="hermes-status-dot ' + enabledDot + '" style="width:8px;height:8px;display:inline-block;vertical-align:middle;"></span> ' + enabledText + '</td>' +
                    '<td style="white-space:nowrap;">' +
                    '<button class="cbi-button cbi-button-apply" style="font-size:11px;padding:2px 6px;margin-right:2px;" onclick="hermesServiceAction(\'start\', \'' + hermesEscape(svc.name) + '\')">启动</button>' +
                    '<button class="cbi-button cbi-button-reset" style="font-size:11px;padding:2px 6px;margin-right:2px;" onclick="hermesServiceAction(\'stop\', \'' + hermesEscape(svc.name) + '\')">停止</button>' +
                    '<button class="cbi-button cbi-button-apply" style="font-size:11px;padding:2px 6px;margin-right:2px;" onclick="hermesServiceAction(\'restart\', \'' + hermesEscape(svc.name) + '\')">重启</button>' +
                    '</td>' +
                    '</tr>';
            });

            html += '</table>';
            list.innerHTML = html;
        })
        .catch(function(err) {
            list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

function hermesServiceAction(action, name) {
    var actionNames = { start: '启动', stop: '停止', restart: '重启', enable: '启用', disable: '禁用' };
    var actionName = actionNames[action] || action;

    var list = document.getElementById('hermes-svc-list');
    list.innerHTML = '<div class="hermes-table-placeholder">⏳ ' + actionName + ' ' + name + '...</div>';

    HermesAPI.serviceAction(action, name)
        .then(function(data) {
            list.innerHTML = '<div class="hermes-table-placeholder">✅ ' + actionName + ' ' + name + ' 成功</div>';
            setTimeout(hermesRefreshServices, 1000);
        })
        .catch(function(err) {
            list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

function hermesSearchServices() {
    var input = document.getElementById('hermes-svc-search');
    var query = (input ? input.value.trim() : '').toLowerCase();

    HermesAPI.getServices()
        .then(function(data) {
            var services = data.services || [];
            var list = document.getElementById('hermes-svc-list');
            if (!list) return;

            if (query) {
                services = services.filter(function(s) {
                    return s.name.toLowerCase().indexOf(query) !== -1;
                });
            }

            if (services.length === 0) {
                list.innerHTML = '<div class="hermes-table-placeholder">未找到匹配的服务</div>';
                return;
            }

            var html = '<div style="margin-bottom:6px;color:var(--text-muted,#666);font-size:12px;">共 ' + services.length + ' 个服务</div>';
            html += '<table class="cbi-section-table">' +
                '<tr><th>服务名</th><th>运行状态</th><th>开机自启</th><th>操作</th></tr>';

            services.forEach(function(svc) {
                var runningDot = svc.running ? 'hermes-status-ok' : 'hermes-status-error';
                var runningText = svc.running ? '运行中' : '已停止';
                var enabledDot = svc.enabled ? 'hermes-status-ok' : 'hermes-status-error';
                var enabledText = svc.enabled ? '已启用' : '已禁用';

                html += '<tr>' +
                    '<td>' + hermesEscape(svc.name) + '</td>' +
                    '<td><span class="hermes-status-dot ' + runningDot + '" style="width:8px;height:8px;"></span> ' + runningText + '</td>' +
                    '<td><span class="hermes-status-dot ' + enabledDot + '" style="width:8px;height:8px;"></span> ' + enabledText + '</td>' +
                    '<td style="white-space:nowrap;">' +
                    '<button class="cbi-button cbi-button-apply" style="font-size:11px;padding:2px 6px;margin-right:2px;" onclick="hermesServiceAction(\'start\', \'' + hermesEscape(svc.name) + '\')">启动</button>' +
                    '<button class="cbi-button cbi-button-reset" style="font-size:11px;padding:2px 6px;margin-right:2px;" onclick="hermesServiceAction(\'stop\', \'' + hermesEscape(svc.name) + '\')">停止</button>' +
                    '<button class="cbi-button cbi-button-apply" style="font-size:11px;padding:2px 6px;margin-right:2px;" onclick="hermesServiceAction(\'restart\', \'' + hermesEscape(svc.name) + '\')">重启</button>' +
                    '</td>' +
                    '</tr>';
            });

            html += '</table>';
            list.innerHTML = html;
        })
        .catch(function(err) {
            var list = document.getElementById('hermes-svc-list');
            if (list) list.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

// =============================================================================
// 系统信息
// =============================================================================

function hermesLoadSystemInfo() {
    var container = document.getElementById('hermes-system-info');
    if (!container) return;
    container.innerHTML = '<div class="hermes-table-placeholder">⏳ 正在加载...</div>';

    HermesAPI.getRouterInfo()
        .then(function(info) {
            var html = '<table class="cbi-section-table">';

            html += '<tr><td><strong>主机名</strong></td><td>' + hermesEscape(info.hostname || '—') + '</td></tr>';
            html += '<tr><td><strong>系统</strong></td><td>' + hermesEscape(info.os || '—') + '</td></tr>';
            html += '<tr><td><strong>内核</strong></td><td style="font-size:12px;">' + hermesEscape(info.kernel || '—') + '</td></tr>';
            html += '<tr><td><strong>运行时间</strong></td><td>' + hermesEscape(info.uptime || '—') + '</td></tr>';

            if (info.cpu) {
                html += '<tr><td><strong>CPU</strong></td><td>' + hermesEscape(info.cpu.model || '—') + ' (' + (info.cpu.cores || '?') + ' 核)</td></tr>';
            }

            if (info.loadavg && info.loadavg.length) {
                html += '<tr><td><strong>系统负载</strong></td><td>' + hermesEscape(info.loadavg.join(' / ')) + '</td></tr>';
            }

            if (info.memory) {
                html += '<tr><td><strong>内存</strong></td><td>' + info.memory.used_mb + ' / ' + info.memory.total_mb + ' MB (' + info.memory.usage_pct + '%)</td></tr>';
            }

            if (info.disk && info.disk.partitions) {
                info.disk.partitions.forEach(function(part) {
                    html += '<tr><td><strong>存储 ' + hermesEscape(part.mount) + '</strong></td><td>' +
                        hermesEscape(part.used) + ' / ' + hermesEscape(part.size) + ' (' + hermesEscape(part.usage_pct) + ')</td></tr>';
                });
            }

            html += '</table>';
            container.innerHTML = html;
        })
        .catch(function(err) {
            container.innerHTML = '<div class="hermes-table-placeholder" style="color:#c00;">⚠️ ' + err.message + '</div>';
        });
}

// =============================================================================
// 命令终端
// =============================================================================

function hermesExecCommand() {
    var input = document.getElementById('hermes-term-input');
    var output = document.getElementById('hermes-term-output');
    var command = input ? input.value.trim() : '';

    if (!command) return;

    output.textContent = '$ ' + command + '\n⏳ 执行中...';

    HermesAPI.execCommand(command)
        .then(function(data) {
            var result = '$ ' + command + '\n';
            if (data.stdout) result += data.stdout + '\n';
            if (data.stderr && !data.success) result += '\n[错误]\n' + data.stderr + '\n';
            if (data.success) {
                result += '\n✅ 退出码: ' + data.returncode;
            } else {
                result += '\n❌ 退出码: ' + data.returncode;
            }
            output.textContent = result;
        })
        .catch(function(err) {
            output.textContent = '$ ' + command + '\n\n⚠️ ' + err.message;
        });
}

function hermesClearTerminal() {
    var output = document.getElementById('hermes-term-output');
    if (output) output.textContent = '等待命令...';
}

// =============================================================================
// 工具函数
// =============================================================================

function hermesEscape(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
