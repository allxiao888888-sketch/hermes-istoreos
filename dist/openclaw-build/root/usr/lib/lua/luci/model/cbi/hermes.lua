-- CBI 模型: Hermes Agent 连接配置
-- 这个模型定义了 iStoreOS 设置页面中的表单字段

local m = Map("hermes", translate("Hermes Agent 连接设置"),
    translate("配置 OpenClaw / Hermes Agent 服务器的连接参数。服务器运行在你的 macOS 主机上。"))

-- ====== 服务器连接设置 ======
local s = m:section(NamedSection, "config", "config", translate("服务器连接"))

local host = s:option(Value, "server_host", translate("服务器地址"),
    translate("运行 Hermes Agent 的 macOS 主机的 IP 地址"))
host.default = "192.168.1.100"
host.datatype = "host"
host.rmempty = false

local port = s:option(Value, "server_port", translate("端口"),
    translate("OpenClaw API 网关的端口（默认 9120）"))
port.default = "9120"
port.datatype = "port"
port.rmempty = false

local api_key = s:option(Value, "api_key", translate("API 密钥"),
    translate("API 认证密钥（如果服务器配置了认证）"))
api_key.password = true  -- 密码输入框

local timeout = s:option(Value, "timeout", translate("超时时间（秒）"),
    translate("API 请求超时时间"))
timeout.default = "30"
timeout.datatype = "uinteger"

-- ====== 连接测试 ======
local s2 = m:section(NamedSection, "config", "config", translate("连接测试"))

local test_btn = s2:option(Button, "_test", translate("测试连接"))
test_btn.inputstyle = "apply"
function test_btn.write(self, section, value)
    local host_val = m:get(section, "server_host") or "192.168.1.100"
    local port_val = m:get(section, "server_port") or "9120"
    local key_val = m:get(section, "api_key") or ""
    
    local http = require("luci.http")
    http.prepare_content("text/plain")
    
    local url = "http://" .. host_val .. ":" .. port_val .. "/api/health"
    local cmd = {"wget", "-q", "-O", "-", "--timeout=5", url}
    if key_val ~= "" then
        table.insert(cmd, "--header=Authorization: Bearer " .. key_val)
    end
    
    local proc = io.popen(table.concat(cmd, " "), "r")
    if not proc then
        http.write("错误: 无法执行 wget")
        return
    end
    
    local output = proc:read("*a")
    local exit_code = proc:close()
    
    if output and output ~= "" then
        http.write("✓ 连接成功!\n服务器响应: " .. output)
    else
        http.write("✗ 连接失败!\n请检查:\n")
        http.write("  1. macOS 上 openclaw-api 是否正在运行 (python3 server.py)\n")
        http.write("  2. 服务器地址和端口是否正确\n")
        http.write("  3. 路由器是否能访问该地址（网络连通性）\n")
        http.write("  4. 防火墙是否放行该端口\n")
        if exit_code then
            http.write("\nwget 退出码: " .. tostring(exit_code))
        end
    end
end

-- ====== 显示设置 ======
local s3 = m:section(NamedSection, "config", "config", translate("显示设置"))

local theme = s3:option(ListValue, "theme", translate("主题"),
    translate("插件 UI 主题"))
theme:value("auto", translate("自动（跟随系统）"))
theme:value("dark", translate("深色"))
theme:value("light", translate("浅色"))
theme.default = "dark"

local refresh = s3:option(Value, "refresh_interval", translate("自动刷新间隔（秒）"),
    translate("仪表盘自动刷新间隔，设为 0 禁用"))
refresh.default = "10"
refresh.datatype = "uinteger"

return m
