import streamlit as st
import os
import re
from datetime import datetime
import time
import base64
import streamlit.components.v1 as components

from fact_checker import FactChecker
import auth
import db_utils
from pdf_export import generate_fact_check_pdf
from model_manager import model_manager
from reportlab.pdfgen import canvas
from io import BytesIO

# ==========================================
# 1. 页面级配置 & 数据库初始化
# ==========================================
st.set_page_config(
    page_title="较真 - Jiaozhen News Observer",
    page_icon="🕵️‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"Get Help": None, "Report a bug": None, "About": None}
)

db_utils.init_db()

# ==========================================
# 2. 全局样式注入 (核心布局与浅色模式)
# ==========================================
tailwind_and_custom_css = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    /* 彻底隐藏 Streamlit 原生外壳干扰 */
    [data-testid="collapsedControl"], [data-testid="stSidebar"], header[data-testid="stHeader"], footer { 
        display: none !important; 
    }
    
    /* 强制全局浅色背景 */
    .stApp {
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
    }

    /* 优化主内容区宽度和边距，为左侧自定义栏腾出空间 */
    .block-container {
        margin-left: 280px !important;
        max-width: 900px !important;
        padding-top: 2rem !important;
        padding-bottom: 6rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* 确保所有主内容区的元素都遵循左边距 */
    .main .block-container {
        margin-left: 280px !important;
    }
    
    /* 修复输入框容器的定位 */
    [data-testid="stChatInputContainer"] {
        margin-left: 280px !important;
        max-width: calc(100vw - 280px) !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* ---------------- 自定义左侧边栏 ---------------- */
    #custom-sidebar {
        position: fixed;
        top: 0; left: 0; bottom: 0;
        width: 280px;
        background-color: #F9FAFB;
        border-right: 1px solid #E5E7EB;
        padding: 1.5rem;
        display: flex;
        flex-direction: column;
        z-index: 999999;
    }

    /* ---------------- 原生组件深度美化 ---------------- */
    [data-testid="stStatusWidget"] {
        background-color: #F3F4F6 !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 0.75rem !important;
    }
    [data-testid="stStatusWidget"] summary { color: #1F2937 !important; font-weight: 500; }
    [data-testid="stStatusWidget"] [data-testid="stMarkdownContainer"] p { color: #4B5563 !important; }

    [data-testid="stExpander"] {
        background-color: #F3F4F6 !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 0.5rem !important;
    }
    [data-testid="stExpander"] summary p { color: #1F2937 !important; font-weight: 500; }

    [data-testid="stChatInput"] { 
        background-color: #FFFFFF !important; 
        border: none !important;
    }
    
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInputContainer"],
    form[data-testid="stChatInputForm"],
    section[data-testid="stChatInputContainer"],
    div[data-testid="stChatInputContainer"] {
        margin-left: 280px !important;
        max-width: calc(100vw - 300px) !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    [data-testid="stChatInput"] {
        margin-left: 280px !important;
        max-width: calc(100vw - 300px) !important;
    }
    
    [data-testid="stChatInput"] textarea {
        background-color: #FFFFFF !important;
        color: #1F2937 !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 1rem !important;
        padding: 1rem !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #2A8BF5 !important;
        box-shadow: 0 0 0 1px #2A8BF5 !important;
    }
    
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #F3F4F6; }
    ::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #9CA3AF; }
</style>
"""
st.markdown(tailwind_and_custom_css, unsafe_allow_html=True)

# ==========================================
# 3. 核心工具与业务辅助函数
# ==========================================
def markdown_to_html(text):
    if not text:
        return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'<b class="text-gray-900 font-semibold">\1</b>', text)
    text = re.sub(r'(?m)^[-*]\s+(.*)$', r'<li class="ml-4 mb-1 list-disc">\1</li>', text)
    text = text.replace('\n', '<br>')
    text = text.replace('</li><br>', '</li>')
    return text

def check_user_config_status():
    from user_config import get_user_config_manager
    config_manager = get_user_config_manager()
    if not config_manager:
        return False
    user_config = config_manager.get_user_config()
    return bool(user_config.get("model_config", {})) and "config_completed" in user_config

def get_saved_config_info():
    from user_config import get_user_config_manager
    config_manager = get_user_config_manager()
    if not config_manager:
        return None
    user_config = config_manager.get_user_config()
    defaults = user_config.get("model_config", {}).get("defaults", {})
    search_names = {"duckduckgo": "DuckDuckGo", "searxng": "SearXNG", "bocha": "Bocha API"}
    return {
        "model_name": defaults.get("llm_model", "未配置"),
        "search_name": search_names.get(defaults.get("search_provider", "duckduckgo"), "DuckDuckGo")
    }

def get_config_parameters():
    from user_config import get_user_config_manager
    config_manager = get_user_config_manager()
    if not config_manager: return None
    user_config = config_manager.get_user_config()
    model_config = user_config.get("model_config", {})
    if not model_config: return None
    
    providers = model_config.get("providers", {})
    defaults = model_config.get("defaults", {})
    provider_key = defaults.get("llm_provider")
    
    if not provider_key or provider_key not in providers: return None
    provider_config = providers[provider_key]
    
    return {
        "provider_key": provider_key,
        "api_base": provider_config.get("base_url"),
        "chat_model": defaults.get("llm_model"),
        "embedding_model": defaults.get("embedding_model"),
        "search_provider": defaults.get("search_provider", "duckduckgo"),
        "selected_language": defaults.get("output_language", "zh"),
        "provider_config": provider_config
    }

# ==========================================
# 4. 报告内容动态渲染器 (Tailwind 浅色系)
# ==========================================
def render_verification_report(verdict_data, content_verification, propagation_timeline):
    verdict_styles = {
        "TRUE": {"bg": "bg-[#1A2A1A]", "border": "border-green-900/60", "text": "text-green-500", "text_light": "text-green-200/80", "emoji": "✅"},
        "FALSE": {"bg": "bg-[#2A1818]", "border": "border-red-900/60", "text": "text-red-500", "text_light": "text-red-200/80", "emoji": "❌"},
        "PARTIALLY TRUE": {"bg": "bg-[#2A2518]", "border": "border-yellow-900/60", "text": "text-yellow-500", "text_light": "text-yellow-200/80", "emoji": "⚠️"}
    }
    
    verdict = verdict_data.get("verdict", "FALSE").upper()
    style = verdict_styles.get(verdict, verdict_styles["FALSE"])
    
    html = f"""
    <div class="{style['bg']} border {style['border']} p-5 rounded-lg mb-6 shadow-sm">
        <h2 class="text-[17px] font-bold {style['text']} m-0 flex items-center gap-2">
            <span>{style['emoji']}</span> Overall Verdict: {verdict_data.get('verdict_en', verdict)} ({verdict_data.get('verdict_cn', '未知')})
        </h2>
        <p class="mt-2 text-[14px] {style['text_light']} leading-relaxed">
            {verdict_data.get('reasoning', 'No reasoning provided.')}
        </p>
    </div>

    <div class="bg-[#1F2937] border border-gray-800 rounded-lg p-5 mb-6">
        <h3 class="text-gray-300 font-semibold mb-4 flex items-center gap-2 text-sm">
            <span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span> Content Verification
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    """
    
    if content_verification.get("objective_facts"):
        fact = content_verification["objective_facts"]
        html += f"""
            <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden h-full">
                <div class="bg-green-900/30 text-green-400 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-green-900/40">
                    <span>✅</span> Objective Facts
                </div>
                <div class="p-4 text-sm text-gray-300 leading-relaxed">
                    <p class="mb-2">Excerpt: "{fact.get('excerpt', '')}"</p>
                    <p class="text-gray-400">Verification: {fact.get('verification', '')}</p>
                </div>
            </div>
        """
    
    if content_verification.get("misleading"):
        misleading = content_verification["misleading"]
        html += f"""
            <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden h-full">
                <div class="bg-red-900/30 text-red-400 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-red-900/40">
                    <span>🚨</span> Misleading / Exaggerated
                </div>
                <div class="p-4 text-sm text-gray-300 leading-relaxed">
                    <p class="mb-2">Excerpt: "{misleading.get('excerpt', '')}"</p>
                    <p class="text-gray-400">Verification: {misleading.get('verification', '')}</p>
                </div>
            </div>
        """
    
    html += "</div>"
    
    if content_verification.get("subjective_opinion"):
        opinion = content_verification["subjective_opinion"]
        html += f"""
        <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden mt-4">
            <div class="bg-blue-900/20 text-blue-400 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-blue-900/30">
                <span>💬</span> Subjective Opinion
            </div>
            <div class="p-4 text-sm text-gray-300 leading-relaxed flex flex-col md:flex-row md:gap-8">
                <p>Excerpt: "{opinion.get('excerpt', '')}"</p>
                <p class="text-gray-400">Verification: {opinion.get('verification', 'Subjective judgment, non-verifiable.')}</p>
            </div>
        </div>
        """
    
    html += """
    </div>
    <div class="bg-[#1F2937] border border-gray-800 rounded-lg p-5 mb-6">
        <h3 class="text-gray-300 font-semibold mb-5 flex items-center gap-2 text-sm">
            <span class="w-1.5 h-1.5 rounded-full bg-[#2A8BF5]"></span> Propagation Timeline
        </h3>
        <div class="relative border-l border-gray-700 ml-2 pl-6 py-1 space-y-6">
    """
    
    for i, event in enumerate(propagation_timeline):
        is_first = (i == 0)
        dot_class = "bg-[#2A8BF5] shadow-[0_0_8px_rgba(42,139,245,0.8)]" if is_first else "bg-gray-500"
        html += f"""
            <div class="relative">
                <div class="absolute w-2 h-2 {dot_class} rounded-full -left-[28.5px] top-1.5"></div>
                <div class="text-xs text-gray-400 mb-1">{event.get('date', '')} | Source: {event.get('source', '')}</div>
                <div class="text-sm text-gray-300">{event.get('description', '')}</div>
            </div>
        """
    
    html += "</div></div>"
    return html

# ==========================================
# 5. 主核查界面 (完美融合逻辑与 UI)
# ==========================================
def show_simplified_fact_check_page():
    # 5.1 获取配置以渲染侧边栏
    config_info = get_saved_config_info()
    model_disp = config_info['model_name'] if config_info else "未配置"
    search_disp = config_info['search_name'] if config_info else "未配置"
    username = st.session_state.get("username", "Observer 001")

    # 5.2 渲染静态侧边栏
    sidebar_html = f"""
    <div id="custom-sidebar">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <h2 style="font-size: 1.25rem; font-weight: bold; color: #1F2937; display: flex; align-items: center; gap: 0.5rem; margin: 0;">较真 + 🕵️‍♂️</h2>
            <span style="color: #6B7280; cursor: pointer;">«</span>
        </div>
        <div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 1.5rem;">Jiaozhen News Observer</div>
        <button style="background-color: #2A8BF5; color: white; font-weight: 600; padding: 0.5rem 1rem; border-radius: 0.5rem; width: 100%; margin-bottom: 2rem; border: none;">New Verification</button>
        <div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 0.5rem;">Search provider</div>
        <div style="background-color: #FFFFFF; color: #1F2937; font-size: 0.875rem; padding: 0.5rem 0.75rem; border-radius: 0.25rem; border: 1px solid #D1D5DB; margin-bottom: 1.25rem;">{search_disp}</div>
        <div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 0.5rem;">Model</div>
        <div style="background-color: #FFFFFF; color: #1F2937; font-size: 0.875rem; padding: 0.5rem 0.75rem; border-radius: 0.25rem; border: 1px solid #D1D5DB; margin-bottom: 2rem;">{model_disp}</div>
        <div style="margin-top: auto; border-top: 1px solid #E5E7EB; padding-top: 1.25rem; display: flex; flex-direction: column; gap: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #1F2937;"><span style="width: 1.5rem; height: 1.5rem; border-radius: 50%; background-color: #E5E7EB; display: flex; align-items: center; justify-content: center; font-size: 0.75rem;">👤</span> {username}</div>
        </div>
    </div>
    """
    st.markdown(sidebar_html, unsafe_allow_html=True)

    # 5.3 接收用户输入
    user_input = st.chat_input("粘贴需要核查的新闻或链接...", key="fact_input")

    # 5.4 大模型核心工作流逻辑
    if user_input:
        # 显示用户发送气泡
        user_msg_html = f"""
        <div class="flex justify-end mb-6 animate-fade-in-up">
            <div class="bg-[#2A8BF5] text-white px-5 py-3.5 rounded-2xl rounded-tr-sm max-w-[75%] text-sm leading-relaxed shadow-sm">
                {user_input}
            </div>
        </div>
        """
        st.markdown(user_msg_html, unsafe_allow_html=True)

        config_params = get_config_parameters()
        if not config_params:
            st.error("⚠️ 配置不完整，请返回配置向导。")
            return

        try:
            # 实例化 FactChecker
            search_config = model_manager.get_search_provider_config(config_params["search_provider"])
            fact_checker = FactChecker(
                api_base=config_params["api_base"], model=config_params["chat_model"], temperature=0.0, max_tokens=1500,
                embedding_base_url=config_params["api_base"], embedding_model=config_params["embedding_model"], 
                embedding_api_key=config_params["provider_config"].get("api_key", ""),
                search_engine=config_params["search_provider"], searxng_url=search_config.get("base_url", "http://localhost:8090"), 
                output_language=config_params["selected_language"], search_config=search_config
            )

            with st.status("🕵️‍♂️ Agents are working on it...", expanded=True) as status:
                st.write("🔍 Extracting core claims...")
                claim = fact_checker.extract_claim(user_input).replace("claim:", "").strip()
                
                st.write("🌐 Tracing evidence across the web...")
                evidence_docs = fact_checker.search_evidence(claim, search_config.get("max_results", 5))
                
                st.write("🧠 Reranking semantics & cross-checking...")
                max_ev = int(search_config.get("max_results", 5) * 3 * model_manager.get_current_config().get("defaults", {}).get("evidence_display_multiplier", 2.0))
                evidence_chunks = fact_checker.get_evidence_chunks(evidence_docs, claim, top_k=max_ev)
                evaluation_evidence = evidence_chunks[:-1] if len(evidence_chunks) > 1 else evidence_chunks

                # 执行最终推理分析
                evaluation = fact_checker.evaluate_claim(claim, evaluation_evidence, original_text=user_input)
                status.update(label="✅ Verification Complete", state="complete", expanded=False)

            # 解析 reasoning
            reasoning = evaluation.get('reasoning', '')
            content_match = re.search(r'### 📊 内容核查.*?\n(.*?)(?=### 🔄|### ⚖️|$)', reasoning, re.DOTALL)
            timeline_match = re.search(r'### 🔄 事件溯源.*?\n(.*?)(?=### 📊|### ⚖️|$)', reasoning, re.DOTALL)
            summary_match = re.search(r'总结[：:]\s*(.*)', reasoning)

            content_text = content_match.group(1).strip() if content_match else ""
            timeline_text = timeline_match.group(1).strip() if timeline_match else "暂无明确溯源路径。"
            summary_text = summary_match.group(1).strip() if summary_match else "基于多源交叉比对与信息溯源，得出结论。"

            fact_match = re.search(r'- \*\*客观事实\*\*[：:]\s*(.*?)(?=- \*\*|- 疑似|###|$)', content_text, re.DOTALL)
            opinion_match = re.search(r'- \*\*主观观点\*\*[：:]\s*(.*?)(?=- \*\*|- 疑似|###|$)', content_text, re.DOTALL)
            error_match = re.search(r'- \*\*疑似错误/不实\*\*[：:]\s*(.*?)(?=- \*\*|###|$)', content_text, re.DOTALL)

            verdict = evaluation.get("verdict", "FALSE").upper()
            verdict_cn_map = {"TRUE": "正确", "FALSE": "错误", "PARTIALLY TRUE": "部分正确"}
            
            # 数据组装
            verdict_data = {
                "verdict": verdict,
                "verdict_en": verdict.title(),
                "verdict_cn": verdict_cn_map.get(verdict, "无法验证"),
                "reasoning": markdown_to_html(summary_text)
            }

            content_verification = {}
            if fact_match and fact_match.group(1).strip() and fact_match.group(1).strip() != "无":
                content_verification["objective_facts"] = {
                    "excerpt": "已证实的客观事实", "verification": markdown_to_html(fact_match.group(1).strip()), "source_link": "#"
                }
            if error_match and error_match.group(1).strip() and error_match.group(1).strip() != "无":
                content_verification["misleading"] = {
                    "excerpt": "夸大或错误的信息", "verification": markdown_to_html(error_match.group(1).strip()), "source_link": "#"
                }
            if opinion_match and opinion_match.group(1).strip() and opinion_match.group(1).strip() != "无":
                content_verification["subjective_opinion"] = {
                    "excerpt": "强烈主观情绪表达", "verification": markdown_to_html(opinion_match.group(1).strip())
                }
                
            propagation_timeline = []
            lines = [line.strip() for line in timeline_text.split('\n') if line.strip()]
            for line in lines:
                clean_line = re.sub(r'^[-*]\s*', '', line)
                propagation_timeline.append({"date": "AI 分析节点", "source": "综合网络证据", "description": markdown_to_html(clean_line)})
            
            if not propagation_timeline:
                 propagation_timeline.append({"date": "AI 分析节点", "source": "综合网络证据", "description": markdown_to_html(timeline_text)})

            # 动态渲染卡片组件
            inner_html = render_verification_report(verdict_data, content_verification, propagation_timeline)
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            report_id = datetime.now().strftime('%Y%m%d')
            report_html_full = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <script src="https://cdn.tailwindcss.com"></script>
                <style>
                    body {{ margin: 0; padding: 1rem; background: transparent; }}
                    a {{ color: #2A8BF5; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <div class="mt-4 mb-6">
                    <div class="flex justify-between items-center mb-4 text-xs text-gray-600 border-b border-gray-300 pb-3">
                        <span>Verification Report ID: VRI-{report_id}-001 | {current_time}</span>
                        <div class="flex gap-2">
                            <button class="px-3 py-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 transition">Download PDF</button>
                            <button class="px-3 py-1.5 bg-[#2A8BF5] rounded text-white hover:bg-blue-600 transition">Cite Sources</button>
                        </div>
                    </div>
                    {inner_html}
                </div>
            </body>
            </html>
            """
            components.html(report_html_full, height=850, scrolling=True)

            # 渲染底层证据折叠面板
            with st.expander("🔗 Raw Evidence Sources"):
                ev_html = f"<div class='text-sm text-gray-600 leading-relaxed'><b>Target Claim:</b> <i>{claim}</i><hr class='my-2'>"
                for j, chunk in enumerate(evaluation_evidence):
                    title = chunk.get('title', '🔗')
                    ev_html += f"<b>[{j+1}] <a href='{chunk['source']}' class='text-[#2A8BF5]' target='_blank'>{title}</a></b><br><span class='mb-4 block'>{chunk['text']}</span>"
                ev_html += "</div>"
                st.markdown(ev_html, unsafe_allow_html=True)
            
            # 保存到数据库
            db_utils.save_fact_check(st.session_state.user_id, user_input, claim, evaluation["verdict"], reasoning, evaluation_evidence)

        except Exception as e:
            st.error(f"⚠️ 在核查过程中发生错误：{str(e)}")

# ==========================================
# 6. 其他辅助页面 (历史记录)
# ==========================================
def show_history_page():
    st.header("历史记录")
    items_per_page = 5
    total_items = db_utils.count_user_history(st.session_state.user_id)

    if "history_page" not in st.session_state: st.session_state.history_page = 0
    total_pages = (total_items + items_per_page - 1) // items_per_page

    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("上一页", disabled=(st.session_state.history_page == 0)):
                st.session_state.history_page -= 1; st.rerun()
        with col2: st.write(f"第 {st.session_state.history_page + 1} 页，共 {total_pages} 页")
        with col3:
            if st.button("下一页", disabled=(st.session_state.history_page == total_pages - 1)):
                st.session_state.history_page += 1; st.rerun()

    history_items = db_utils.get_user_history(st.session_state.user_id, limit=items_per_page, offset=st.session_state.history_page * items_per_page)
    if not history_items: st.info("您还没有任何历史记录"); return

    for item in history_items:
        with st.container():
            cols = st.columns([4, 1, 1])
            with cols[0]:
                st.subheader(f"{item['claim'][:100]}...")
                st.write(f"结论: {item['verdict'].upper()} | 时间: {item['created_at']}")
            with cols[1]:
                if st.button("查看详情", key=f"view_{item['id']}"):
                    st.session_state.current_history_id = item["id"]
                    st.session_state.page = "details"; st.rerun()
            st.divider()

def show_history_detail_page():
    if not st.session_state.current_history_id: st.session_state.page = "history"; st.rerun()
    history_item = db_utils.get_history_by_id(st.session_state.current_history_id)
    if st.button("返回历史列表"): st.session_state.page = "history"; st.rerun()

    st.header("核查详情")
    st.subheader("原始文本")
    st.write(history_item["original_text"])
    
    st.divider()
    try:
        pdf_data = generate_fact_check_pdf(history_item)
        filename = f"事实核查报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_b64 = base64.b64encode(pdf_data).decode()
        st.markdown(f'<a href="data:application/pdf;base64,{pdf_b64}" download="{filename}" style="padding: 0.5em 1em; background-color: #2A8BF5; color: white; border-radius: 4px; text-decoration: none;">导出为PDF</a>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"PDF生成错误: {str(e)}")

# ==========================================
# 7. 全局路由与认证拦截 (入口)
# ==========================================
if "page" not in st.session_state: st.session_state.page = "home"
if "current_history_id" not in st.session_state: st.session_state.current_history_id = None

if "user_id" not in st.session_state or st.session_state.user_id is None:
    if saved_login := auth.check_saved_login():
        st.session_state.user_id = saved_login["user_id"]
        st.session_state.username = saved_login["username"]

if auth.show_auth_ui():
    if not check_user_config_status():
        st.warning("⚠️ 请先在环境配置页面完成设定，以调用正确的大模型接口。您可能需要先运行原本带有引导页的脚本以完成 config.json 生成。")
    else:
        # 顶层简易导航栏
        nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([6, 1, 1, 1])
        with nav_col2:
            if st.button("🏠 核查主页", use_container_width=True): st.session_state.page = "home"; st.rerun()
        with nav_col3:
            if st.button("🕒 历史记录", use_container_width=True): st.session_state.page = "history"; st.rerun()
        with nav_col4:
            if st.button("🚪 退出登录", use_container_width=True): auth.logout(); st.rerun()

        # 路由分发
        if st.session_state.page == "home":
            show_simplified_fact_check_page()
        elif st.session_state.page == "history":
            show_history_page()
        elif st.session_state.page == "details":
            show_history_detail_page()