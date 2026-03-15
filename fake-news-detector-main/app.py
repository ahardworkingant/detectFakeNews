import streamlit as st
from datetime import datetime
import streamlit.components.v1 as components

# ==========================================
# 1. 页面级配置
# ==========================================
st.set_page_config(
    page_title="较真 - Jiaozhen News Observer",
    page_icon="🕵️‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 全局样式注入 (核心布局与暗黑模式)
# ==========================================
# 解析：隐藏原生组件，使用 position: fixed 绘制侧边栏，推移主内容区
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
    /* AI 思考状态器 (st.status) */
    [data-testid="stStatusWidget"] {
        background-color: #F3F4F6 !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 0.75rem !important;
    }
    [data-testid="stStatusWidget"] summary { color: #1F2937 !important; font-weight: 500; }
    [data-testid="stStatusWidget"] [data-testid="stMarkdownContainer"] p { color: #4B5563 !important; }

    /* 折叠面板 (st.expander) */
    [data-testid="stExpander"] {
        background-color: #F3F4F6 !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 0.5rem !important;
    }
    [data-testid="stExpander"] summary p { color: #1F2937 !important; font-weight: 500; }

    /* 底部聊天输入框 (st.chat_input) */
    [data-testid="stChatInput"] { 
        background-color: #FFFFFF !important; 
        border: none !important;
    }
    
    /* 输入框容器定位 - 使用多个选择器确保覆盖 */
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
    
    /* 确保输入框本身也有正确的定位 */
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
    
    /* 滚动条浅色化 */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #F3F4F6; }
    ::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #9CA3AF; }
</style>
"""
st.markdown(tailwind_and_custom_css, unsafe_allow_html=True)

# ==========================================
# 2.5 报告内容渲染函数
# ==========================================
def render_verification_report(verdict_data, content_verification, propagation_timeline):
    """
    渲染核查报告的核心内容
    
    参数:
        verdict_data: dict - 包含 verdict (True/False/Partially True), verdict_cn, reasoning
        content_verification: dict - 包含 objective_facts, misleading, subjective_opinion
        propagation_timeline: list - 包含时间线事件列表，每个事件包含 date, source, description
    """
    # 根据 verdict 确定样式
    verdict_styles = {
        "TRUE": {
            "bg": "bg-[#1A2A1A]",
            "border": "border-green-900/60",
            "text": "text-green-500",
            "text_light": "text-green-200/80",
            "emoji": "✅"
        },
        "FALSE": {
            "bg": "bg-[#2A1818]",
            "border": "border-red-900/60",
            "text": "text-red-500",
            "text_light": "text-red-200/80",
            "emoji": "❌"
        },
        "PARTIALLY_TRUE": {
            "bg": "bg-[#2A2518]",
            "border": "border-yellow-900/60",
            "text": "text-yellow-500",
            "text_light": "text-yellow-200/80",
            "emoji": "⚠️"
        }
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
    
    # 客观事实
    if content_verification.get("objective_facts"):
        fact = content_verification["objective_facts"]
        html += f"""
            <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden h-full">
                <div class="bg-green-900/30 text-green-400 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-green-900/40">
                    <span>✅</span> Objective Facts
                </div>
                <div class="p-4 text-sm text-gray-300 leading-relaxed">
                    <p class="mb-2">Excerpt: "{fact.get('excerpt', '')}"</p>
                    <p class="text-gray-400">Verification: {fact.get('verification', '')} <a href="{fact.get('source_link', '#')}" class="text-[#2A8BF5] hover:underline">Link to source</a></p>
                </div>
            </div>
"""
    
    # 误导/夸大
    if content_verification.get("misleading"):
        misleading = content_verification["misleading"]
        html += f"""
            <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden h-full">
                <div class="bg-red-900/30 text-red-400 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-red-900/40">
                    <span>🚨</span> Misleading / Exaggerated
                </div>
                <div class="p-4 text-sm text-gray-300 leading-relaxed">
                    <p class="mb-2">Excerpt: "{misleading.get('excerpt', '')}"</p>
                    <p class="text-gray-400">Verification: {misleading.get('verification', '')} <a href="{misleading.get('source_link', '#')}" class="text-[#2A8BF5] hover:underline">Link to source</a></p>
                </div>
            </div>
"""
    
    html += """
        </div>
"""
    
    # 主观观点
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
    
    # 时间线
    for i, event in enumerate(propagation_timeline):
        is_first = i == 0
        dot_class = "bg-[#2A8BF5] shadow-[0_0_8px_rgba(42,139,245,0.8)]" if is_first else "bg-gray-500"
        html += f"""
            <div class="relative">
                <div class="absolute w-2 h-2 {dot_class} rounded-full -left-[28.5px] top-1.5"></div>
                <div class="text-xs text-gray-400 mb-1">{event.get('date', '')} | Source: {event.get('source', '')}</div>
                <div class="text-sm text-gray-300">{event.get('description', '')}</div>
            </div>
"""
    
    html += """
        </div>
    </div>
"""
    
    return html

# ==========================================
# 3. 渲染左侧固定导航栏 (HTML Mock)
# ==========================================
# 使用 st.markdown 渲染，全局 CSS 中已定义 #custom-sidebar 的固定定位样式
sidebar_html = """
<div id="custom-sidebar">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
<h2 style="font-size: 1.25rem; font-weight: bold; color: #1F2937; display: flex; align-items: center; gap: 0.5rem; margin: 0;">较真 + 🕵️‍♂️</h2>
<span style="color: #6B7280; cursor: pointer;">«</span>
</div>
<div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 1.5rem;">Jiaozhen News Observer</div>
<button style="background-color: #2A8BF5; color: white; font-weight: 600; padding: 0.5rem 1rem; border-radius: 0.5rem; width: 100%; margin-bottom: 2rem; transition: background-color 0.2s; border: none; cursor: pointer;" onmouseover="this.style.backgroundColor='#2563EB'" onmouseout="this.style.backgroundColor='#2A8BF5'">New Verification</button>
<div style="display: flex; flex-direction: column; gap: 1rem; font-size: 0.875rem; color: #6B7280; margin-bottom: 2rem;">
<div style="display: flex; align-items: center; gap: 0.75rem; cursor: pointer; transition: color 0.2s;" onmouseover="this.style.color='#1F2937'" onmouseout="this.style.color='#6B7280'"><span style="width: 1rem;">🕒</span> Verification History</div>
<div style="display: flex; align-items: center; gap: 0.75rem; cursor: pointer; color: #1F2937;"><span style="width: 1rem;">⚙️</span> Model Config</div>
</div>
<div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 0.5rem;">Search provider</div>
<div style="background-color: #FFFFFF; color: #1F2937; font-size: 0.875rem; padding: 0.5rem 0.75rem; border-radius: 0.25rem; border: 1px solid #D1D5DB; margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: center; cursor: pointer;"><span>Bocha API</span> <span style="font-size: 0.75rem;">▼</span></div>
<div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 0.5rem;">Model</div>
<div style="background-color: #FFFFFF; color: #1F2937; font-size: 0.875rem; padding: 0.5rem 0.75rem; border-radius: 0.25rem; border: 1px solid #D1D5DB; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; cursor: pointer;"><span>gpt-4o</span> <span style="font-size: 0.75rem;">▼</span></div>
<div style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #6B7280; cursor: pointer; transition: color 0.2s;" onmouseover="this.style.color='#1F2937'" onmouseout="this.style.color='#6B7280'"><span style="width: 1rem;">🔧</span> Settings</div>
<div style="margin-top: auto; border-top: 1px solid #E5E7EB; padding-top: 1.25rem; display: flex; flex-direction: column; gap: 1rem;">
<div style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #1F2937; cursor: pointer; transition: color 0.2s;" onmouseover="this.style.color='#111827'" onmouseout="this.style.color='#1F2937'"><span style="width: 1.5rem; height: 1.5rem; border-radius: 50%; background-color: #E5E7EB; display: flex; align-items: center; justify-content: center; font-size: 0.75rem;">👤</span> Observer 001</div>
<div style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #6B7280; cursor: pointer; transition: color 0.2s;" onmouseover="this.style.color='#1F2937'" onmouseout="this.style.color='#6B7280'"><span style="width: 1rem;">ⓘ</span> About</div>
</div>
</div>
"""
st.markdown(sidebar_html, unsafe_allow_html=True)

# ==========================================
# 4. 渲染右侧主内容区 (User Chat & AI Result)
# ==========================================

# 4.1 用户输入气泡 (靠右对齐)
user_msg_html = """
<div class="flex justify-end mb-6 animate-fade-in-up">
    <div class="bg-[#2A8BF5] text-white px-5 py-3.5 rounded-2xl rounded-tr-sm max-w-[75%] text-sm leading-relaxed shadow-sm">
        网传：A公司裁员80%，高管携款潜逃境外，这是真的吗？
    </div>
</div>
"""
st.markdown(user_msg_html, unsafe_allow_html=True)

# 4.2 AI 思考状态器 (原生 Streamlit Component)
with st.status("🕵️‍♂️ Agents are working on it...", expanded=True, state="complete") as status:
    st.write("🔍 Extracting core claims...")
    st.write("🌐 Tracing evidence across the web...")
    st.write("🧠 Reranking semantics & cross-checking...")
    status.update(label="✅ Verification Complete", state="complete", expanded=False)

# 4.3 核心核查报告卡片 (使用 components.html 确保 Tailwind 正确加载)
report_html_full = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { margin: 0; padding: 1rem; background: transparent; }
    </style>
</head>
<body>
    <div class="mt-4 mb-6">
        <div class="flex justify-between items-center mb-4 text-xs text-gray-600 border-b border-gray-300 pb-3">
            <span>Verification Report ID: VRI-20231026-001 | 2023-10-26 18:30</span>
            <div class="flex gap-2">
                <button class="px-3 py-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 transition">Download PDF</button>
                <button class="px-3 py-1.5 bg-[#2A8BF5] rounded text-white hover:bg-blue-600 transition">Cite Sources</button>
            </div>
        </div>

        <div class="bg-red-50 border border-red-200 p-5 rounded-lg mb-6 shadow-sm">
            <h2 class="text-[17px] font-bold text-red-600 m-0 flex items-center gap-2">
                <span>❌</span> Overall Verdict: False (错误)
            </h2>
            <p class="mt-2 text-[14px] text-red-700 leading-relaxed">
                Based on multiple sources, the core claim about high-level executives absconding with funds is false.
            </p>
        </div>

        <div class="bg-gray-50 border border-gray-200 rounded-lg p-5 mb-6">
            <h3 class="text-gray-800 font-semibold mb-4 flex items-center gap-2 text-sm">
                <span class="w-1.5 h-1.5 rounded-full bg-gray-600"></span> Content Verification
            </h3>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-white border border-gray-200 rounded-lg overflow-hidden h-full">
                    <div class="bg-green-50 text-green-700 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-green-200">
                        <span>✅</span> Objective Facts
                    </div>
                    <div class="p-4 text-sm text-gray-700 leading-relaxed">
                        <p class="mb-2">Excerpt: "员工已被警方拘留"</p>
                        <p class="text-gray-600">Verification: Confirmed. Police report issued today (10/26). <a href="#" class="text-[#2A8BF5] hover:underline">Link to source</a></p>
                    </div>
                </div>
                
                <div class="bg-white border border-gray-200 rounded-lg overflow-hidden h-full">
                    <div class="bg-red-50 text-red-700 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-red-200">
                        <span>🚨</span> Misleading / Exaggerated
                    </div>
                    <div class="p-4 text-sm text-gray-700 leading-relaxed">
                        <p class="mb-2">Excerpt: "携款潜逃"</p>
                        <p class="text-gray-600">Verification: Disproven. Source 1 (financial report) shows attendance at meeting. <a href="#" class="text-[#2A8BF5] hover:underline">Link to source</a></p>
                    </div>
                </div>
            </div>

            <div class="bg-white border border-gray-200 rounded-lg overflow-hidden mt-4">
                <div class="bg-blue-50 text-blue-700 text-xs font-bold px-3 py-2 flex items-center gap-1.5 border-b border-blue-200">
                    <span>💬</span> Subjective Opinion
                </div>
                <div class="p-4 text-sm text-gray-700 leading-relaxed flex flex-col md:flex-row md:gap-8">
                    <p>Excerpt: "建议避雷"</p>
                    <p class="text-gray-600">Verification: Subjective judgment, non-verifiable.</p>
                </div>
            </div>
        </div>

        <div class="bg-gray-50 border border-gray-200 rounded-lg p-5 mb-6">
            <h3 class="text-gray-800 font-semibold mb-5 flex items-center gap-2 text-sm">
                <span class="w-1.5 h-1.5 rounded-full bg-[#2A8BF5]"></span> Propagation Timeline
            </h3>
            
            <div class="relative border-l border-gray-300 ml-2 pl-6 py-1 space-y-6">
                <div class="relative">
                    <div class="absolute w-2 h-2 bg-[#2A8BF5] rounded-full -left-[28.5px] top-1.5 shadow-[0_0_8px_rgba(42,139,245,0.8)]"></div>
                    <div class="text-xs text-gray-600 mb-1">2023年10月24日 14:30 | Source: 小红书/Anonymous</div>
                    <div class="text-sm text-gray-700">Initial leak: Anonymous leak with single screenshot.</div>
                </div>
                <div class="relative">
                    <div class="absolute w-2 h-2 bg-gray-400 rounded-full -left-[28.5px] top-1.5"></div>
                    <div class="text-xs text-gray-600 mb-1">2023年10月25日 09:15 | Source: 微博/Marketing</div>
                    <div class="text-sm text-gray-700">Source: 微博/Marketing: Re-shared with emotional context.</div>
                </div>
                <div class="relative">
                    <div class="absolute w-2 h-2 bg-gray-400 rounded-full -left-[28.5px] top-1.5"></div>
                    <div class="text-xs text-gray-600 mb-1">2023年10月26日 18:00 | Source: 官方/Media</div>
                    <div class="text-sm text-gray-700">Source: Police and Media: Official police and media clarification.</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
components.html(report_html_full, height=1000, scrolling=False)

# 4.4 原始证据面板 (原生 st.expander)
with st.expander("🔗 Raw Evidence"):
    st.markdown("""
    <div class="text-sm text-gray-600 leading-loose">
        1. 东方财富网 (Conference call)<br>
        2. 平安朝阳 (Police Report)<br>
        3. 澎湃新闻
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 5. 底部悬浮输入框 (原生 st.chat_input)
# ==========================================
st.chat_input("Type a message...", key="mock_input")