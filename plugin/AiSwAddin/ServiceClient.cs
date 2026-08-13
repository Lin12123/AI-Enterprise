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

        /// <summary>自然语言 → FeaturePlan(JSON 字符串原样返回)。</summary>
        public Task<string> GeneratePlanAsync(string naturalLanguage, string provider)
        {
            string body = "{"
                + "\"natural_language\":" + JsonString(naturalLanguage) + ","
                + "\"provider\":" + JsonString(provider)
                + "}";
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
        /// useActiveDoc=true 时在当前活动文档建模，否则新建零件文档。</summary>
        public Task<string> ExecuteAsync(string planJson, bool useActiveDoc)
        {
            string flag = useActiveDoc ? "true" : "false";
            return PostAsync("/api/execute",
                "{\"plan\":" + planJson + ",\"use_active_doc\":" + flag + "}");
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