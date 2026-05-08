-- CBI 模型: Hermes Agent 连接配置
-- 配置本地 Hermes Router API 和 LLM 提供商

local m = Map("hermes", translate("Hermes Agent 设置"),
    translate("配置 AI 提供商、API 密钥和本地服务参数。所有服务运行在本路由器上。"))

-- ====== AI 提供商设置 ======
local s = m:section(NamedSection, "config", "config", translate("AI 提供商"))

local provider = s:option(ListValue, "llm_provider", translate("提供商"),
    translate("选择 AI 模型提供商"))
provider:value("openrouter", "OpenRouter（推荐，免费可用）")
provider:value("openai", "OpenAI")
provider:value("deepseek", "DeepSeek")
provider:value("custom", "自定义 API")
provider.default = "openrouter"
provider.rmempty = false

local model = s:option(Value, "llm_model", translate("模型"),
    translate("AI 模型名称（例如: google/gemini-2.0-flash-lite-preview-02-05）"))
model.default = "google/gemini-2.0-flash-lite-preview-02-05"
model.rmempty = false

local api_key = s:option(Value, "llm_api_key", translate("API 密钥"),
    translate("LLM API 的认证密钥（OpenRouter/OpenAI/DeepSeek 等）"))
api_key.password = true

local base_url = s:option(Value, "llm_base_url", translate("API 地址"),
    translate("API 基础 URL（默认可不填，自定义提供商时填写）"))
base_url.default = "https://openrouter.ai/api/v1"

-- ====== 本地服务设置 ======
local s2 = m:section(NamedSection, "config", "config", translate("本地服务"))

local api_key_local = s2:option(Value, "api_key", translate("本地 API 密钥"),
    translate("Hermes API 的认证密钥（可选，留空则不认证）"))
api_key_local.password = true
api_key_local.description = translate("设置后前端和外部访问需要携带 Authorization: Bearer <密钥>")

local port = s2:option(Value, "local_port", translate("本地端口"),
    translate("Hermes API 服务器监听端口（默认 9120）"))
port.default = "9120"
port.datatype = "port"
port.rmempty = false

-- ====== 连接测试 ======
local s3 = m:section(NamedSection, "config", "config", translate("连接测试"))

local test_btn = s3:option(Button, "_test", translate("测试连接"))
test_btn.inputstyle = "apply"
function test_btn.write(self, section, value)
    local port_val = m:get(section, "local_port") or "9120"
    
    local http = require("luci.http")
    http.prepare_content("text/plain; charset=utf-8")
    
    -- 1. 先测试本地 API 服务器
    local url = "http://127.0.0.1:" .. port_val .. "/api/health"
    local cmd = "wget -q -O - --timeout=5 '" .. url .. "' 2>/dev/null"
    
    local proc = io.popen(cmd, "r")
    if not proc then
        http.write("✗ 无法执行 wget\n")
        return
    end
    
    local output = proc:read("*a")
    proc:close()
    
    if not output or output == "" then
        http.write("✗ 本地 Hermes API 服务器未运行！\n")
        http:write("请先启动: python3 /usr/libexec/hermes-router-api/server.py &\n")
        http.write("或: /etc/init.d/hermes-router-api start\n")
        return
    end
    
    http.write("✓ 本地 Hermes API 服务器运行正常\n\n")
    
    -- 2. 测试 LLM API 连接
    local llm_api_key = m:get(section, "llm_api_key") or ""
    local llm_provider = m:get(section, "llm_provider") or "openrouter"
    local llm_model = m:get(section, "llm_model") or ""
    
    if llm_api_key ~= "" then
        http.write("测试 AI 提供商: " .. llm_provider .. "\n")
        http.write("模型: " .. llm_model .. "\n")
        
        local base_urls = {
            openrouter = "https://openrouter.ai/api/v1",
            openai = "https://api.openai.com/v1",
            deepseek = "https://api.deepseek.com/v1",
        }
        local api_base = base_urls[llm_provider] or m:get(section, "llm_base_url") or ""
        
        if api_base ~= "" then
            local model_url = api_base .. "/models"
            local model_cmd = "wget -q -O - --timeout=10 --header='Authorization: Bearer " .. llm_api_key .. "' '" .. model_url .. "' 2>/dev/null"
            local model_proc = io.popen(model_cmd, "r")
            if model_proc then
                local model_out = model_proc:read("*a")
                model_proc:close()
                if model_out and model_out ~= "" then
                    http.write("✓ AI 提供商连接成功\n")
                else
                    http.write("⚠ AI 提供商可能有问题，但密钥格式正确\n")
                end
            end
        end
    else
        http.write("⚠ LLM API 密钥未配置，AI 聊天功能不可用\n")
        http.write("请在上方「AI 提供商」区域填写 API 密钥\n")
    end
end

-- ====== 显示设置 ======
local s4 = m:section(NamedSection, "config", "config", translate("显示设置"))

local theme = s4:option(ListValue, "theme", translate("主题"),
    translate("插件 UI 主题"))
theme:value("auto", translate("自动（跟随系统）"))
theme:value("dark", translate("深色"))
theme:value("light", translate("浅色"))
theme.default = "dark"

local refresh = s4:option(Value, "refresh_interval", translate("自动刷新间隔（秒）"),
    translate("仪表盘自动刷新间隔，设为 0 禁用"))
refresh.default = "10"
refresh.datatype = "uinteger"

return m
