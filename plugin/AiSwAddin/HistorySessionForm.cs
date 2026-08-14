using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;

namespace AiSwAddin
{
    /// <summary>历史会话选择窗口：以卡片列表展示最近会话，点击某张卡片即回调其 sessionId，
    /// 由调用方负责加载该会话并渲染到会话流。非模态(Show)，不阻塞主界面。</summary>
    internal class HistorySessionForm : Form
    {
        /// <summary>单条会话的解析结果。</summary>
        internal class SessionItem
        {
            public string Id;
            public string Title;
            public string Status;
            public string UpdatedAt;
        }

        private readonly Action<string> _onPick;

        /// <param name="sessions">已解析的会话列表(最新在前)。</param>
        /// <param name="onPick">点击某条会话时回调，参数为该会话 id。</param>
        public HistorySessionForm(List<SessionItem> sessions, Action<string> onPick)
        {
            _onPick = onPick;

            Text = "历史会话";
            StartPosition = FormStartPosition.CenterParent;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;
            ClientSize = new Size(420, 480);
            BackColor = Theme.PageBg;
            Font = Theme.Body(9, FontStyle.Regular);

            var header = new Label
            {
                Text = "点击任意会话可加载并继续对话",
                Dock = DockStyle.Top,
                Height = 40,
                ForeColor = Theme.TextSub,
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(16, 0, 0, 0),
                Font = Theme.Body(9, FontStyle.Regular)
            };

            var list = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(12, 4, 12, 12),
                BackColor = Theme.PageBg
            };

            if (sessions == null || sessions.Count == 0)
            {
                list.Controls.Add(new Label
                {
                    Text = "暂无历史会话。",
                    Dock = DockStyle.Top,
                    Height = 60,
                    ForeColor = Theme.TextSub,
                    TextAlign = ContentAlignment.MiddleCenter
                });
            }
            else
            {
                // Dock=Top 逆序添加：最先添加的排最上。为保持“最新在前”，按传入顺序倒序 Add。
                for (int i = sessions.Count - 1; i >= 0; i--)
                {
                    list.Controls.Add(BuildCard(sessions[i]));
                }
            }

            Controls.Add(list);
            Controls.Add(header);
        }

        /// <summary>为一条会话构建可点击卡片。</summary>
        private Control BuildCard(SessionItem item)
        {
            var card = new Panel
            {
                Dock = DockStyle.Top,
                Height = 76,
                Margin = new Padding(0, 0, 0, 8),
                Padding = new Padding(12, 8, 12, 8),
                BackColor = Color.White,
                Cursor = Cursors.Hand
            };
            // Dock=Top 卡片之间的间距用底部空白 Panel 模拟
            card.Height = 72;

            string title = string.IsNullOrEmpty(item.Title) ? "未命名会话" : item.Title;
            string status = string.IsNullOrEmpty(item.Status) ? "" : "  [" + item.Status + "]";

            var titleLbl = new Label
            {
                Text = title + status,
                Dock = DockStyle.Top,
                Height = 26,
                ForeColor = Theme.TextMain,
                Font = Theme.Body(10, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleLeft,
                AutoEllipsis = true,
                BackColor = Color.Transparent
            };

            var metaText = "";
            if (!string.IsNullOrEmpty(item.UpdatedAt)) metaText += "更新: " + item.UpdatedAt;
            if (!string.IsNullOrEmpty(item.Id))
            {
                if (metaText.Length > 0) metaText += "   ";
                metaText += "ID: " + item.Id;
            }
            var metaLbl = new Label
            {
                Text = metaText,
                Dock = DockStyle.Top,
                Height = 22,
                ForeColor = Theme.TextSub,
                Font = Theme.Body(8, FontStyle.Regular),
                TextAlign = ContentAlignment.MiddleLeft,
                AutoEllipsis = true,
                BackColor = Color.Transparent
            };

            // 点击卡片或其中任意子控件都触发选择
            EventHandler pick = (s, e) =>
            {
                if (string.IsNullOrEmpty(item.Id)) return;
                var cb = _onPick;
                Close();
                if (cb != null) cb(item.Id);
            };
            card.Click += pick;
            titleLbl.Click += pick;
            metaLbl.Click += pick;

            // 悬停高亮
            EventHandler enter = (s, e) => card.BackColor = Color.FromArgb(238, 242, 252);
            EventHandler leave = (s, e) => card.BackColor = Color.White;
            card.MouseEnter += enter;
            card.MouseLeave += leave;

            card.Controls.Add(metaLbl);
            card.Controls.Add(titleLbl);

            // 外层包一层带底部间距的容器
            var wrap = new Panel
            {
                Dock = DockStyle.Top,
                Height = 80,
                Padding = new Padding(0, 0, 0, 8),
                BackColor = Theme.PageBg
            };
            wrap.Controls.Add(card);
            return wrap;
        }

        /// <summary>解析 /api/sessions/recent 响应体为会话列表(按响应中出现顺序)。</summary>
        public static List<SessionItem> ParseSessions(string resp)
        {
            var result = new List<SessionItem>();
            if (string.IsNullOrEmpty(resp)) return result;
            int arrStart = resp.IndexOf("\"sessions\"", StringComparison.Ordinal);
            if (arrStart < 0) return result;
            int lb = resp.IndexOf('[', arrStart);
            int rb = (lb >= 0) ? resp.IndexOf(']', lb) : -1;
            if (lb < 0 || rb < 0 || rb <= lb) return result;
            string inner = resp.Substring(lb + 1, rb - lb - 1);

            int p = 0;
            while (p < inner.Length)
            {
                int objStart = inner.IndexOf('{', p);
                if (objStart < 0) break;
                int objEnd = inner.IndexOf('}', objStart);
                if (objEnd < 0) break;
                string obj = inner.Substring(objStart, objEnd - objStart + 1);
                result.Add(new SessionItem
                {
                    Id = Field(obj, "id"),
                    Title = Field(obj, "title"),
                    Status = Field(obj, "status"),
                    UpdatedAt = Field(obj, "updated_at")
                });
                p = objEnd + 1;
            }
            return result;
        }

        /// <summary>轻量 JSON 字符串字段提取(与主控件 ExtractStringField 同逻辑)。</summary>
        private static string Field(string json, string key)
        {
            if (string.IsNullOrEmpty(json) || string.IsNullOrEmpty(key)) return null;
            string needle = "\"" + key + "\"";
            int i = json.IndexOf(needle, StringComparison.Ordinal);
            if (i < 0) return null;
            i = json.IndexOf(':', i);
            if (i < 0) return null;
            while (++i < json.Length && (json[i] == ' ' || json[i] == '\t')) { }
            if (i >= json.Length || json[i] != '"') return null;
            int start = i + 1;
            int end = json.IndexOf('"', start);
            if (end < 0) return null;
            return json.Substring(start, end - start);
        }
    }
}