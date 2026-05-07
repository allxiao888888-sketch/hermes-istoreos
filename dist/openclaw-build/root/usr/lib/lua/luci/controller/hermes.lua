module("luci.controller.hermes", package.seeall)

function index()
    -- 主菜单: 服务 > Hermes Agent
    entry({"admin", "services", "hermes"}, alias("admin", "services", "hermes", "dashboard"), _("Hermes Agent"), 80)
    
    -- 仪表盘
    entry({"admin", "services", "hermes", "dashboard"}, template("hermes/dashboard"), _("仪表盘"), 10)
    
    -- 聊天界面
    entry({"admin", "services", "hermes", "chat"}, template("hermes/chat"), _("聊天"), 20)
    
    -- 设置页面
    entry({"admin", "services", "hermes", "config"}, cbi("hermes"), _("设置"), 30)
    
    -- 关于
    entry({"admin", "services", "hermes", "about"}, template("hermes/about"), _("关于"), 40)
    
    -- API 代理端点（被前端 JS 调用）
    entry({"admin", "services", "hermes", "api"}, call("handle_api"))
end

function handle_api()
    local http = require("luci.http")
    local json = require("luci.jsonc")
    local uci = require("luci.model.uci").cursor()
    
    -- 读取配置
    local server_host = uci:get("hermes", "config", "server_host") or "192.168.1.100"
    local server_port = uci:get("hermes", "config", "server_port") or "9120"
    local api_key = uci:get("hermes", "config", "api_key") or ""
    local api_base = "http://" .. server_host .. ":" .. server_port
    
    -- 解析请求路径和方法
    local path = http.formvalue("path") or ""
    local method = http.formvalue("_method") or "GET"
    
    -- 构建目标 URL
    local target_url = api_base .. "/api/" .. path
    
    -- 发送 HTTP 请求
    local result, err = http_request(target_url, method, api_key)
    
    if not result then
        http.prepare_content("application/json")
        http.write(json.stringify({
            error = "无法连接到 OpenClaw 服务器: " .. (err or "未知错误"),
            code = 503
        }))
        return
    end
    
    http.prepare_content("application/json")
    http.write(result)
end

function http_request(url, method, api_key)
    local wget = require("luci.http").curl or "wget"
    
    local cmd = {
        "wget", "-q", "-O", "-",
        "--timeout=10",
        "--header=Content-Type: application/json",
    }
    
    if api_key and api_key ~= "" then
        table.insert(cmd, "--header=Authorization: Bearer " .. api_key)
    end
    
    if method == "POST" then
        local body = luci.http.formvalue("body")
        local tmpfile = "/tmp/hermes_request_body.json"
        if body then
            local f = io.open(tmpfile, "w")
            if f then
                f:write(body)
                f:close()
                table.insert(cmd, "--post-file=" .. tmpfile)
            end
        end
    end
    
    table.insert(cmd, url)
    
    local proc = io.popen(table.concat(cmd, " "), "r")
    if not proc then
        return nil, "无法执行 wget"
    end
    
    local output = proc:read("*a")
    proc:close()
    
    if output and output ~= "" then
        return output, nil
    end
    
    return nil, "服务器返回空响应"
end
