using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

namespace AiSwAddin
{
    /// <summary>
    /// 本地 Python HTTP 服务的客户端封装。
    ///
    /// 所有业务逻辑都在 Python 侧(service/http_service.py)，本类只负责：
    /// - 组织请求 JSON、发起 HTTP 调用、返回原始响应字符串。
    /// - 解析交由 UI 层做最小化处理，避免在插件里引入重型 JSON 依赖。
    ///
    /// 默认服务地址 http://127.0.0.1:8765，与 Python 服务默认端口一致。
    /// </summary>
    public class ServiceClient
    {
        private readonly HttpClient _http;
        private readonly string _baseUrl;

        public ServiceClient(string baseUrl = "http://127.0.0.1:8765")
        {
            _baseUrl = baseUrl.TrimEnd('/');
            _http = new HttpClient
            {
                // 真实建模可能较慢，给足超时时间
                Timeout = TimeSpan.FromMinutes(5)
            };
        }

        /// <summary>健康检查：确认 Python 服务是否已启动。</summary>
        public async Task<bool> HealthCheckAsync()
        {
            try
            {
                HttpResponseMessage resp = await _http.GetAsync(_baseUrl + "/api/health");
                return resp.IsSuccessStatusCode;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>创建一个新会话，返回服务端响应(含 session_id)。</summary>
        public Task<string> CreateSessionAsync()
        {
            return PostAsync("/api/sessions/create", "{}");
        }

        /// <summary>自然语言 → FeaturePlan(JSON 字符串原样返回)。
        /// 传入非空 sessionId 时，服务端会把该会话历史拼进 prompt 实现上下文连续，
        /// 并把本轮用户需求/助手结果追加到该会话。</summary>
        public Task<string> GeneratePlanAsync(string naturalLanguage, string provider, string sessionId = "")
        {
            string body = "{"
                + "\"natural_language\":" + JsonString(naturalLanguage) + ","
                + "\"provider\":" + JsonString(provider);
            if (!string.IsNullOrEmpty(sessionId))
                body += ",\"session_id\":" + JsonString(sessionId);
            body += "}";
            return PostAsync("/api/generate_plan", body);
        }

        /// <summary>校验 FeaturePlan(传入 plan 的 JSON 字符串)。</summary>
        public Task<string> ValidateAsync(string planJson)
        {
            return PostAsync("/api/validate", "{\"plan\":" + planJson + "}");
        }

        /// <summary>预演(不连接 SolidWorks)。</summary>
        public Task<string> DryRunAsync(string planJson)
        {
            return PostAsync("/api/dry_run", "{\"plan\":" + planJson + "}");
        }

        /// <summary>真实建模(Python 侧通过 pywin32 连接当前打开的 SolidWorks)。
        /// useActiveDoc=true 时优先在当前活动文档建模；prompt 为用户原始自然语言需求，
        /// 当活动文档已有零件时供服务端判断"修改当前"还是"新增零件"。</summary>
        public Task<string> ExecuteAsync(string planJson, bool useActiveDoc, string prompt = "", string sessionId = null)
        {
            string flag = useActiveDoc ? "true" : "false";
            string promptField = "\"" + JsonEscape(prompt ?? "") + "\"";
            string body = "{\"plan\":" + planJson + ",\"use_active_doc\":" + flag
                + ",\"prompt\":" + promptField;
            // 带上会话标识：服务端据此把 3D 零件路径记入 last_outputs，
            // 使用户即便不转 2D 也能直接上传该 3D 文件到云平台。
            if (!string.IsNullOrEmpty(sessionId))
                body += ",\"session_id\":" + JsonString(sessionId);
            body += "}";
            return PostAsync("/api/execute", body);
        }

        /// <summary>把任意字符串转义为可安全嵌入 JSON 双引号内的形式。</summary>
        private static string JsonEscape(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var sb = new StringBuilder(s.Length + 8);
            foreach (char c in s)
            {
                switch (c)
                {
                    case '\"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < ' ')
                            sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else
                            sb.Append(c);
                        break;
                }
            }
            return sb.ToString();
        }

        /// <summary>获取 FeaturePlan 的软性诊断清单(规则合规与几何质量, 不阻断执行)。</summary>
        public Task<string> DiagnoseAsync(string planJson)
        {
            return PostAsync("/api/diagnose", "{\"plan\":" + planJson + "}");
        }

        /// <summary>3D 转 2D 出图：把当前 SolidWorks 活动零件转成三视图工程图并保存。
        /// 必须带上 sessionId，后端会把出图产物(part_path/drawing_path)写入 session.context.last_outputs，
        /// 供后续「上传企业云平台」按钮读取。sessionId 为空时后端不会记录产物，会导致上传失败。</summary>
        public Task<string> CreateDrawingAsync(string sessionId)
        {
            string body = "{\"session_id\":" + JsonString(sessionId ?? "") + "}";
            return PostAsync("/api/create_drawing", body);
        }

        /// <summary>把指定会话的出图产物打包上传到企业云平台。
        /// 后端根据 session_id 从 session.context.last_outputs 自动读取待上传文件清单。
        /// projectName 为用户选择的所属项目名称(公狼项目/分播墙项目/智狼项目)，
        /// 作为云平台项目图纸卡片的项目名称。</summary>
        public Task<string> UploadToCloudAsync(string sessionId, string projectName = null)
        {
            string body = "{\"session_id\":" + JsonString(sessionId ?? "");
            if (!string.IsNullOrEmpty(projectName))
                body += ",\"project_name\":" + JsonString(projectName);
            body += "}";
            return PostAsync("/api/upload_to_cloud", body);
        }

        /// <summary>获取最近会话列表(纯读, GET)。返回响应体字符串。</summary>
        public async Task<string> GetRecentSessionsAsync(int n = 20)
        {
            try
            {
                HttpResponseMessage resp = await _http.GetAsync(_baseUrl + "/api/sessions/recent?n=" + n);
                return await resp.Content.ReadAsStringAsync();
            }
            catch (Exception ex)
            {
                throw new Exception(
                    "无法连接本地 AI 服务(" + _baseUrl + ")。请先运行 service/start_service.bat 启动服务。详情: "
                    + ex.Message);
            }
        }

        /// <summary>按会话 ID 加载完整会话(含 messages), 用于点击历史会话后恢复对话。返回响应体字符串。</summary>
        public async Task<string> LoadSessionAsync(string sessionId)
        {
            try
            {
                HttpResponseMessage resp = await _http.GetAsync(_baseUrl + "/api/sessions/" + Uri.EscapeDataString(sessionId ?? ""));
                return await resp.Content.ReadAsStringAsync();
            }
            catch (Exception ex)
            {
                throw new Exception(
                    "无法连接本地 AI 服务(" + _baseUrl + ")。请先运行 service/start_service.bat 启动服务。详情: "
                    + ex.Message);
            }
        }

        /// <summary>统一的 POST 请求，返回响应体字符串；失败抛出可读异常。</summary>
        private async Task<string> PostAsync(string path, string jsonBody)
        {
            try
            {
                var content = new StringContent(jsonBody, Encoding.UTF8, "application/json");
                HttpResponseMessage resp = await _http.PostAsync(_baseUrl + path, content);
                string text = await resp.Content.ReadAsStringAsync();
                return text;
            }
            catch (Exception ex)
            {
                throw new Exception(
                    "无法连接本地 AI 服务(" + _baseUrl + ")。请先运行 service/start_service.bat 启动服务。详情: "
                    + ex.Message);
            }
        }

        /// <summary>把普通字符串转义为合法的 JSON 字符串字面量(含首尾引号)。</summary>
        private static string JsonString(string value)
        {
            if (value == null) return "\"\"";
            var sb = new StringBuilder();
            sb.Append('"');
            foreach (char c in value)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default: sb.Append(c); break;
                }
            }
            sb.Append('"');
            return sb.ToString();
        }
    }
}