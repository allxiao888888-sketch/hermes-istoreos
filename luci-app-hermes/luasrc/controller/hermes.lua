module("luci.controller.hermes", package.seeall)

function index()
    -- 主菜单: 服务 > Hermes Agent
    entry({"admin", "services", "hermes"}, alias("admin", "services", "hermes", "dashboard"), _("Hermes Agent"), 80)
    
    -- 仪表盘（路由器状态概览）
    entry({"admin", "services", "hermes", "dashboard"}, template("hermes/dashboard"), _("仪表盘"), 10)
    
    -- AI 聊天界面
    entry({"admin", "services", "hermes", "chat"}, template("hermes/chat"), _("AI 聊天"), 20)
    
    -- 路由器管理
    entry({"admin", "services", "hermes", "control"}, template("hermes/control"), _("路由器管理"), 25)
    
    -- 设置页面
    entry({"admin", "services", "hermes", "config"}, cbi("hermes"), _("设置"), 30)
    
    -- 关于
    entry({"admin", "services", "hermes", "about"}, template("hermes/about"), _("关于"), 40)
    
    -- API 代理端点（被前端 JS 调用，转发到本地 Python API 服务器）
    entry({"admin", "services", "hermes", "api"}, call("handle_api"))
end

function handle_api()
    local http = require("luci.http")
    local json = require("luci.jsonc")
    local uci = require("luci.model.uci").cursor()
    
    -- 本地 API 地址（运行在同一台路由器上）
    local api_base = "http://127.0.0.1:9120"
    
    -- 解析请求路径和方法
    local path = http.formvalue("path") or ""
    local method = http.formvalue("_method") or "GET"
    local body = http.formvalue("body") or ""
    
    -- 构建目标 URL
    local target_url = api_base .. "/api/" .. path
    
    -- 发送 HTTP 请求
    local result, err = http_request(target_url, method, body)
    
    if not result then
        http.prepare_content("application/json")
        http.write(json.stringify({
            error = "无法连接到本地 Hermes API 服务器: " .. (err or "未知错误"),
            code = 503,
            detail = "请确保 Hermes Router API 服务正在运行 (python3 server.py)"
        }))
        return
    end
    
    http.prepare_content("application/json")
    http.write(result)
end

function http_request(url, method, body)
    local tmpfile = "/tmp/hermes_api_request_body.json"
    local cmd = {"wget", "-q", "-O", "-", "--timeout=60"}
    
    -- Content-Type
    table.insert(cmd, "--header=Content-Type: application/json")
    table.insert(cmd, "--header=Accept: application/json")
    
    if method == "POST" and body and body ~= "" then
        local f = io.open(tmpfile, "w")
        if f then
            f:write(body)
            f:close()
            table.insert(cmd, "--post-file=" .. tmpfile)
        end
    end
    
    table.insert(cmd, url)
    
    local cmd_str = table.concat(cmd, " ")
    local proc = io.popen(cmd_str .. " 2>/dev/null", "r")
    if not proc then
        return nil, "无法执行 wget"
    end
    
    local output = proc:read("*a")
    local exit_ok, exit_code = proc:close()
    
    -- 清理临时文件
    if method == "POST" then
        os.remove(tmpfile)
    end
    
    if output and output ~= "" then
        return output, nil
    end
    
    if output then
        return nil, "服务器返回空响应 (wget exit code: " .. tostring(exit_code) .. ")"
    end
    
    return nil, "请求失败"
end
