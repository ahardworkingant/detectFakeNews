import streamlit as st
import os
import re
from datetime import datetime
import time
import base64
from fact_checker import FactChecker
import auth
import db_utils
from pdf_export import generate_fact_check_pdf
from model_manager import model_manager

from reportlab.pdfgen import canvas
from io import BytesIO


def generate_test_pdf():
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "这是一个测试PDF")
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# 初始化数据库
db_utils.init_db()

# 页面配置
st.set_page_config(
    page_title="AI虚假新闻检测器",
    page_icon="🔍",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)


def check_user_config_status():
    """检查用户配置状态，判断是否需要显示配置向导"""
    from user_config import get_user_config_manager
    
    config_manager = get_user_config_manager()
    if not config_manager:
        return False  # 未登录，不需要检查配置
    
    user_config = config_manager.get_user_config()
    
    # 检查是否有基本配置
    has_model_config = bool(user_config.get("model_config", {}))
    has_working_config = "config_completed" in user_config
    
    return has_model_config and has_working_config

def show_initial_config_wizard():
    """显示初始配置向导"""
    st.title("🚀 欢迎使用AI虚假新闻检测器")
    st.markdown("""
    在开始使用前，请先进行一次性配置。
    配置完成后，您就可以直接使用系统了。
    """)
    
    st.divider()
    
    # 自动检测配置
    st.subheader("🔍 步骤1: 检测本地环境")
    
    auto_config = detect_available_services()
    if auto_config:
        st.success(f"✅ 检测到可用服务: {auto_config['name']}")
        st.info(f"📍 服务地址: {auto_config['url']}")
        st.info(f"🤖 可用模型: {len(auto_config['available_models'])}个")
        
        # 显示模型选择
        st.subheader("🤖 选择模型")
        
        # 分类模型
        chat_models, embedding_models = categorize_models(auto_config['available_models'])
        
        col1, col2 = st.columns(2)
        with col1:
            if chat_models:
                selected_chat_model = st.selectbox(
                    "💬 聊天模型",
                    options=chat_models,
                    help=f"共{len(chat_models)}个聊天模型可用"
                )
            else:
                st.warning("未找到聊天模型")
                selected_chat_model = None
        
        with col2:
            if embedding_models:
                selected_embedding_model = st.selectbox(
                    "🧠 嵌入模型",
                    options=embedding_models,
                    help=f"共{len(embedding_models)}个嵌入模型可用"
                )
            else:
                # 如果没有嵌入模型，从聊天模型中选择一个
                if chat_models:
                    selected_embedding_model = st.selectbox(
                        "🧠 嵌入模型",
                        options=chat_models,
                        help="未找到专用嵌入模型，使用聊天模型代替"
                    )
                else:
                    st.warning("未找到可用模型")
                    selected_embedding_model = None
        
        if selected_chat_model and selected_embedding_model:
            # 添加搜索引擎选择
            st.subheader("🔍 选择搜索引擎")
            search_options = {
                    "🦆 DuckDuckGo (推荐)": "duckduckgo",
                    "🔍 SearXNG (本地)": "searxng",
                    "🌐 Bocha (API)": "bocha"
                }
            
            selected_search = st.radio(
                "搜索引擎",
                options=list(search_options.keys()),
                help="DuckDuckGo 无需配置，SearXNG 需要本地部署",
                horizontal=True
            )
            
            search_provider = search_options[selected_search]
            searxng_url = None
            
            # 如果选择了 SearXNG，让用户配置地址
            if search_provider == "searxng":
                searxng_url = st.text_input(
                    "🌐 SearXNG 服务地址",
                    value="http://localhost:8090",
                    help="请输入您的 SearXNG 实例地址",
                    placeholder="http://localhost:8090"
                )
            
            elif search_provider == "bocha":
                bocha_api_key = st.text_input(
                    "🔑 Bocha API Key",
                    type="password",
                    help="请输入您的 Bocha API 密钥",
                    placeholder="sk-..."
                )
                if searxng_url:
                    # 测试 SearXNG 连接
                    searxng_available = test_searxng_connection(searxng_url)
                    if searxng_available:
                        st.success("✅ SearXNG 服务可用")
                    else:
                        st.warning("⚠️ SearXNG 服务不可用，请检查地址或服务状态")
            
            if st.button("✨ 使用此配置", type="primary", use_container_width=True):
                auto_config['chat_model'] = selected_chat_model
                auto_config['embedding_model'] = selected_embedding_model
                auto_config['search_provider'] = search_provider
                if searxng_url:
                    auto_config['searxng_url'] = searxng_url
                save_auto_config(auto_config)
                st.success("✅ 配置完成！正在进入主界面...")
                time.sleep(1)
                st.rerun()
                return
    else:
        st.warning("⚠️ 未检测到本地AI服务，请手动配置")
    
    st.divider()
    
    # 手动配置
    st.subheader("⚙️ 步骤2: 手动配置")
    
    # 简化的配置选项
    config_option = st.radio(
        "选择AI服务类型",
        options=[
            "🚀 Ollama (本地推荐)",
            "💻 LM Studio (本地图形界面)", 
            "☁️ OpenAI (云端服务)",
            "🔧 自定义配置"
        ],
        help="选择您要使用的AI服务类型"
    )
    
    manual_config = None
    
    if "🚀 Ollama" in config_option:
        st.subheader("🚀 Ollama 配置")
        models = get_models_for_provider("ollama", "http://localhost:11434")
        if models:
            chat_models, embedding_models = categorize_models(models)
            
            col1, col2 = st.columns(2)
            with col1:
                chat_model = st.selectbox("💬 聊天模型", options=chat_models if chat_models else models)
            with col2:
                embedding_model = st.selectbox("🧠 嵌入模型", options=embedding_models if embedding_models else models)
            
            if chat_model and embedding_model:
                # 添加搜索引擎选择
                st.subheader("🔍 选择搜索引擎")
                search_options = {
                    "🦆 DuckDuckGo (推荐)": "duckduckgo",
                    "🔍 SearXNG (本地)": "searxng",
                    "🌐 Bocha (API)": "bocha"
                }
                
                selected_search = st.radio(
                    "搜索引擎",
                    options=list(search_options.keys()),
                    help="DuckDuckGo 无需配置，SearXNG 需要本地部署",
                    horizontal=True,
                    key="ollama_search"
                )
                
                search_provider = search_options[selected_search]
                searxng_url = None
                
                # 如果选择了 SearXNG，让用户配置地址
                if search_provider == "searxng":
                    searxng_url = st.text_input(
                        "🌐 SearXNG 服务地址",
                        value="http://localhost:8090",
                        help="请输入您的 SearXNG 实例地址",
                        placeholder="http://localhost:8090",
                        key="ollama_searxng_url"
                    )

                elif search_provider == "bocha":
                    bocha_api_key = st.text_input(
                        "🔑 Bocha API Key",
                        type="password",
                        help="请输入您的 Bocha API 密钥",
                        placeholder="sk-..."
                    )
                manual_config = {
                    "name": "Ollama",
                    "provider": "ollama",
                    "url": "http://localhost:11434/v1",
                    "chat_model": chat_model,
                    "embedding_model": embedding_model,
                    "search_provider": search_provider
                }
                
                if searxng_url:
                    manual_config["searxng_url"] = searxng_url
        else:
            st.warning("⚠️ 无法连接到 Ollama 服务，请确保 Ollama 已启动")
    
    elif "💻 LM Studio" in config_option:
        st.subheader("💻 LM Studio 配置")
        models = get_models_for_provider("lmstudio", "http://localhost:1234")
        if models:
            chat_models, embedding_models = categorize_models(models)
            
            col1, col2 = st.columns(2)
            with col1:
                chat_model = st.selectbox("💬 聊天模型", options=chat_models if chat_models else models)
            with col2:
                embedding_model = st.selectbox("🧠 嵌入模型", options=embedding_models if embedding_models else models)
            
            if chat_model and embedding_model:
                # 添加搜索引擎选择
                st.subheader("🔍 选择搜索引擎")
                search_options = {
                    "🦆 DuckDuckGo (推荐)": "duckduckgo",
                    "🔍 SearXNG (本地)": "searxng",
                    "🌐 Bocha (API)": "bocha"
                }
                
                selected_search = st.radio(
                    "搜索引擎",
                    options=list(search_options.keys()),
                    help="DuckDuckGo 无需配置，SearXNG 需要本地部署",
                    horizontal=True,
                    key="lmstudio_search"
                )
                
                search_provider = search_options[selected_search]
                searxng_url = None
                
                # 如果选择了 SearXNG，让用户配置地址
                if search_provider == "searxng":
                    searxng_url = st.text_input(
                        "🌐 SearXNG 服务地址",
                        value="http://localhost:8090",
                        help="请输入您的 SearXNG 实例地址",
                        placeholder="http://localhost:8090",
                        key="lmstudio_searxng_url"
                    )
                # 新增 Bocha 的输入框
                elif search_provider == "bocha":
                    bocha_api_key = st.text_input(
                        "🔑 Bocha API Key",
                        type="password",
                        help="请输入您的 Bocha API 密钥",
                        placeholder="sk-..."
                    )
                
                manual_config = {
                    "name": "LM Studio", 
                    "provider": "lmstudio",
                    "url": "http://localhost:1234/v1",
                    "chat_model": chat_model,
                    "embedding_model": embedding_model,
                    "search_provider": search_provider
                }
                
                if searxng_url:
                    manual_config["searxng_url"] = searxng_url
        else:
            st.warning("⚠️ 无法连接到 LM Studio 服务，请确保 LM Studio 已启动")
    
    elif "☁️ OpenAI" in config_option:
        st.subheader("☁️ OpenAI 配置")
        api_key = st.text_input("🔑 OpenAI API Key", type="password", help="请输入您的OpenAI API密钥")
        if api_key:
            # 预定义 OpenAI 模型（因为需要 API Key 才能获取）
            openai_models = {
                "💬 聊天模型": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
                "🧠 嵌入模型": ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"]
            }
            
            col1, col2 = st.columns(2)
            with col1:
                chat_model = st.selectbox("💬 聊天模型", options=openai_models["💬 聊天模型"])
            with col2:
                embedding_model = st.selectbox("🧠 嵌入模型", options=openai_models["🧠 嵌入模型"])
            
            # 添加搜索引擎选择
            st.subheader("🔍 选择搜索引擎")
            search_options = {
                    "🦆 DuckDuckGo (推荐)": "duckduckgo",
                    "🔍 SearXNG (本地)": "searxng",
                    "🌐 Bocha (API)": "bocha"
                }
            
            selected_search = st.radio(
                "搜索引擎",
                options=list(search_options.keys()),
                help="DuckDuckGo 无需配置，SearXNG 需要本地部署",
                horizontal=True,
                key="openai_search"
            )
            
            search_provider = search_options[selected_search]
            searxng_url = None
            
            # 如果选择了 SearXNG，让用户配置地址
            if search_provider == "searxng":
                searxng_url = st.text_input(
                    "🌐 SearXNG 服务地址",
                    value="http://localhost:8090",
                    help="请输入您的 SearXNG 实例地址",
                    placeholder="http://localhost:8090",
                    key="openai_searxng_url"
                )
            # 新增 Bocha 的输入框
            elif search_provider == "bocha":
                bocha_api_key = st.text_input(
                    "🔑 Bocha API Key",
                    type="password",
                    help="请输入您的 Bocha API 密钥",
                    placeholder="sk-..."
                )
            
            manual_config = {
                "name": "OpenAI",
                "provider": "openai", 
                "url": "https://api.openai.com/v1",
                "api_key": api_key,
                "chat_model": chat_model,
                "embedding_model": embedding_model,
                "search_provider": search_provider
            }
            
            if searxng_url:
                manual_config["searxng_url"] = searxng_url
    
    elif "🔧 自定义" in config_option:
        with st.expander("🚀 自定义配置", expanded=True):
            url = st.text_input("🌐 API地址", placeholder="http://localhost:8000/v1")
            
            if url:
                # 尝试获取模型列表
                models = get_models_for_provider("custom", url.rstrip('/v1'))
                
                if models:
                    st.success(f"✅ 检测到 {len(models)} 个可用模型")
                    chat_models, embedding_models = categorize_models(models)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        chat_model = st.selectbox("💬 聊天模型", options=chat_models if chat_models else models)
                    with col2:
                        embedding_model = st.selectbox("🧠 嵌入模型", options=embedding_models if embedding_models else models)
                    
                    if chat_model and embedding_model:
                        # 添加搜索引擎选择
                        st.subheader("🔍 选择搜索引擎")
                        search_options = {
                            "🦆 DuckDuckGo (推荐)": "duckduckgo",
                            "🔍 SearXNG (本地)": "searxng",
                            "🌐 Bocha (API)": "bocha"
                        }
                        
                        selected_search = st.radio(
                            "搜索引擎",
                            options=list(search_options.keys()),
                            help="DuckDuckGo 无需配置，SearXNG 需要本地部署",
                            horizontal=True,
                            key="custom_search_1"
                        )
                        
                        search_provider = search_options[selected_search]
                        searxng_url = None
                        
                        # 如果选择了 SearXNG，让用户配置地址
                        if search_provider == "searxng":
                            searxng_url = st.text_input(
                                "🌐 SearXNG 服务地址",
                                value="http://localhost:8090",
                                help="请输入您的 SearXNG 实例地址",
                                placeholder="http://localhost:8090",
                                key="custom_searxng_url_1"
                            )
                        elif search_provider == "bocha":
                            bocha_api_key = st.text_input(
                                "🔑 Bocha API Key",
                                type="password",
                                help="请输入您的 Bocha API 密钥",
                                placeholder="sk-..."
                            )
                        
                        manual_config = {
                            "name": "自定义配置",
                            "provider": "custom",
                            "url": url,
                            "chat_model": chat_model,
                            "embedding_model": embedding_model,
                            "search_provider": search_provider
                        }
                        
                        if searxng_url:
                            manual_config["searxng_url"] = searxng_url
                else:
                    st.warning("⚠️ 无法从此地址获取模型列表，请检查地址是否正确")
                    # 手动输入模型名
                    st.info("📝 请手动输入模型名称")
                    col1, col2 = st.columns(2)
                    with col1:
                        chat_model = st.text_input("💬 聊天模型", placeholder="例如: llama2")
                    with col2:
                        embedding_model = st.text_input("🧠 嵌入模型", placeholder="例如: nomic-embed-text")
                    
                    if chat_model and embedding_model:
                        # 添加搜索引擎选择
                        st.subheader("🔍 选择搜索引擎")
                        search_options = {
                            "🦆 DuckDuckGo (推荐)": "duckduckgo",
                            "🔍 SearXNG (本地)": "searxng",
                            "🌐 Bocha (API)": "bocha"
                        }
                        
                        selected_search = st.radio(
                            "搜索引擎",
                            options=list(search_options.keys()),
                            help="DuckDuckGo 无需配置，SearXNG 需要本地部署",
                            horizontal=True,
                            key="custom_search_2"
                        )
                        
                        search_provider = search_options[selected_search]
                        searxng_url = None
                        
                        # 如果选择了 SearXNG，让用户配置地址
                        if search_provider == "searxng":
                            searxng_url = st.text_input(
                                "🌐 SearXNG 服务地址",
                                value="http://localhost:8090",
                                help="请输入您的 SearXNG 实例地址",
                                placeholder="http://localhost:8090",
                                key="custom_searxng_url_2"
                            )
                        elif search_provider == "bocha":
                            bocha_api_key = st.text_input(
                                "🔑 Bocha API Key",
                                type="password",
                                help="请输入您的 Bocha API 密钥",
                                placeholder="sk-..."
                            )

                        
                        manual_config = {
                            "name": "自定义配置",
                            "provider": "custom",
                            "url": url,
                            "chat_model": chat_model,
                            "embedding_model": embedding_model,
                            "search_provider": search_provider
                        }
                        
                        if searxng_url:
                            manual_config["searxng_url"] = searxng_url
    
    # 测试配置
    if manual_config:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔗 测试连接", use_container_width=True):
                with st.spinner("正在测试连接..."):
                    if test_config_connection(manual_config):
                        st.success("✅ 连接成功！")
                    else:
                        st.error("❌ 连接失败，请检查配置")
        
        with col2:
            if st.button("✨ 保存配置", type="primary", use_container_width=True):
                save_manual_config(manual_config)
                st.success("✅ 配置完成！正在进入主界面...")
                time.sleep(1)
                st.rerun()

def detect_available_services():
    """检测可用的本地服务并获取模型列表"""
    import requests
    
    services = [
        ("http://localhost:11434", "Ollama", "ollama"),
        ("http://localhost:1234", "LM Studio", "lmstudio"),
        ("http://localhost:8000", "本地API", "local_api")
    ]
    
    for url, name, provider in services:
        try:
            # 先测试基本连接
            response = requests.get(f"{url}/v1/models", timeout=3)
            if response.status_code == 200:
                # 获取模型列表
                models_data = response.json()
                available_models = []
                
                if "data" in models_data:
                    # OpenAI格式: {"data": [{"id": "model_name"}, ...]}
                    available_models = [model["id"] for model in models_data["data"]]
                elif "models" in models_data:
                    # Ollama格式: {"models": [{"name": "model_name"}, ...]}
                    available_models = [model["name"] for model in models_data["models"]]
                elif isinstance(models_data, list):
                    # 简单格式: ["model1", "model2", ...]
                    available_models = models_data
                
                if available_models:
                    return {
                        "name": name,
                        "provider": provider,
                        "url": f"{url}/v1",
                        "available_models": available_models
                    }
        except:
            continue
    return None

def categorize_models(models):
    """将模型分类为聊天模型和嵌入模型"""
    chat_models = []
    embedding_models = []
    
    for model in models:
        model_lower = model.lower()
        # 判断是否为嵌入模型
        if any(keyword in model_lower for keyword in ['embed', 'embedding', 'nomic', 'bge', 'gte']):
            embedding_models.append(model)
        else:
            chat_models.append(model)
    
    return chat_models, embedding_models

def get_models_for_provider(provider_type, url):
    """为指定提供商获取模型列表"""
    import requests
    
    try:
        response = requests.get(f"{url}/models", timeout=5)
        if response.status_code == 200:
            models_data = response.json()
            
            if "data" in models_data:
                return [model["id"] for model in models_data["data"]]
            elif "models" in models_data:
                return [model["name"] for model in models_data["models"]]
            elif isinstance(models_data, list):
                return models_data
        return []
    except:
        return []

def test_searxng_connection(searxng_url="http://localhost:8090"):
    """测试 SearXNG 连接"""
    try:
        import requests
        # 确保 URL格式正确
        if not searxng_url.startswith('http'):
            searxng_url = f"http://{searxng_url}"
        
        # 测试搜索接口
        response = requests.get(f"{searxng_url}/search", 
                               params={"q": "test", "format": "json"}, 
                               timeout=3)
        return response.status_code == 200
    except:
        return False

def test_config_connection(config):
    """测试配置连接"""
    try:
        import requests
        response = requests.get(f"{config['url']}/models", timeout=3)
        return response.status_code == 200
    except:
        return False

def save_auto_config(config):
    """保存自动检测的配置"""
    from user_config import get_user_config_manager
    
    config_manager = get_user_config_manager()
    if config_manager:
        user_config = {
            "model_config": {
                "providers": {
                    config["provider"]: {
                        "base_url": config["url"]
                    }
                },
                "defaults": {
                    "llm_provider": config["provider"],
                    "llm_model": config["chat_model"],
                    "embedding_model": config["embedding_model"],
                    "search_provider": config.get("search_provider", "duckduckgo"),
                    "output_language": "zh"
                }
            },
            "config_completed": True,
            "config_source": "auto"
        }
        
        # 初始化 search_config（如果不存在）
        if "search_config" not in user_config:
            user_config["search_config"] = {"search_providers": {}}
            
        # 如果有自定义 SearXNG 地址，保存到搜索配置中
        if config.get("searxng_url"):
            user_config["search_config"]["search_providers"]["searxng"] = {
                "base_url": config["searxng_url"]
            }
            
        # 如果有 Bocha API Key，保存到搜索配置中
        if config.get("bocha_api_key"):
            user_config["search_config"]["search_providers"]["bocha"] = {
                "api_key": config["bocha_api_key"]
            }
        
        config_manager.save_user_config(user_config)

def save_manual_config(config):
    """保存手动配置"""
    from user_config import get_user_config_manager
    
    config_manager = get_user_config_manager()
    if config_manager:
        user_config = {
            "model_config": {
                "providers": {
                    config["provider"]: {
                        "base_url": config["url"]
                    }
                },
                "defaults": {
                    "llm_provider": config["provider"],
                    "llm_model": config["chat_model"], 
                    "embedding_model": config["embedding_model"],
                    "search_provider": config.get("search_provider", "duckduckgo"),
                    "output_language": "zh"
                }
            },
            "config_completed": True,
            "config_source": "manual"
        }
        
        if "api_key" in config:
            user_config["model_config"]["providers"][config["provider"]]["api_key"] = config["api_key"]
        
        # 初始化 search_config（如果不存在）
        if "search_config" not in user_config:
            user_config["search_config"] = {"search_providers": {}}
            
        # 如果有自定义 SearXNG 地址，保存到搜索配置中
        if config.get("searxng_url"):
            user_config["search_config"]["search_providers"]["searxng"] = {
                "base_url": config["searxng_url"]
            }
            
        # 如果有 Bocha API Key，保存到搜索配置中
        if config.get("bocha_api_key"):
            user_config["search_config"]["search_providers"]["bocha"] = {
                "api_key": config["bocha_api_key"]
            }
        
        config_manager.save_user_config(user_config)

def get_saved_config_info():
    """获取已保存的配置信息用于显示"""
    from user_config import get_user_config_manager
    
    config_manager = get_user_config_manager()
    if not config_manager:
        return None
    
    user_config = config_manager.get_user_config()
    model_config = user_config.get("model_config", {})
    defaults = model_config.get("defaults", {})
    
    return {
        "model_name": defaults.get("llm_model", "未配置"),
        "search_name": get_search_display_name(defaults.get("search_provider", "duckduckgo"))
    }

def get_search_display_name(search_provider):
    """获取搜索引擎显示名称"""
    search_names = {
        "duckduckgo": "DuckDuckGo",
        "searxng": "SearXNG"
    }
    return search_names.get(search_provider, search_provider)

def get_config_parameters():
    """从已保存的配置获取参数"""
    from user_config import get_user_config_manager
    
    config_manager = get_user_config_manager()
    if not config_manager:
        return None
    
    user_config = config_manager.get_user_config()
    model_config = user_config.get("model_config", {})
    
    if not model_config:
        return None
    
    providers = model_config.get("providers", {})
    defaults = model_config.get("defaults", {})
    
    provider_key = defaults.get("llm_provider")
    if not provider_key or provider_key not in providers:
        return None
    
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

def reset_user_config():
    """重置用户配置"""
    from user_config import get_user_config_manager
    
    config_manager = get_user_config_manager()
    if config_manager:
        config_manager.reset_config()

def markdown_to_html(text):
    """升级版 Markdown 转 HTML：适配深色模式的样式，并支持无序列表"""
    if not text:
        return ""
    # 替换粗体，在深色模式下让强调的文字亮白
    text = re.sub(r'\*\*(.*?)\*\*', r'<b class="text-gray-100 font-semibold">\1</b>', text)
    # 替换列表项
    text = re.sub(r'(?m)^[-*]\s+(.*)$', r'<li class="ml-4 mb-1 list-disc">\1</li>', text)
    # 替换换行
    text = text.replace('\n', '<br>')
    # 清理多余换行
    text = text.replace('</li><br>', '</li>')
    return text

def show_simplified_fact_check_page():
    """沉浸式深色模式事实核查页面 (Stepfun 风格完全复刻)"""
    
    # 1. 注入 Tailwind CSS 和强制覆盖 Streamlit 原生布局的 CSS
    # 使用 Flex 布局使高度占满全屏
    # 隐藏默认 Header、Footer 和 Sidebar
    tailwind_css = """
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* 彻底隐藏 Streamlit 原生元素 */
        #MainMenu, footer, header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="collapsedControl"] {
            display: none !important;
        }

        /* 强制覆盖全局底色和去除默认 padding */
        .stApp {
            background-color: #0B0E14 !important;
            color: #D1D5DB !important;
        }
        
        .block-container {
            padding: 0 !important;
            max-width: 100% !important;
        }

        /* 构建左右两栏全屏 Flex 布局 */
        .custom-layout {
            display: flex;
            min-height: 100vh;
            width: 100vw;
            overflow: hidden;
        }

        /* 自定义侧边栏样式 */
        .custom-sidebar {
            width: 280px;
            background-color: #111827;
            border-right: 1px solid #1F2937;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            overflow-y: auto;
        }

        /* 右侧主内容区 */
        .custom-main {
            flex-grow: 1;
            padding: 2.5rem 4rem;
            overflow-y: auto;
            max-height: 100vh;
        }

        /* ---------------- 以下是 Streamlit 输入组件的穿透修改 ---------------- */
        /* 隐藏 Text Area 的 Label */
        .stTextArea label {
            display: none !important;
        }
        
        /* 修改 Text Area 样式 */
        .stTextArea textarea {
            background-color: #1F2937 !important;
            color: #F3F4F6 !important;
            border: 1px solid #374151 !important;
            border-radius: 0.5rem !important;
            padding: 1rem !important;
        }
        .stTextArea textarea:focus {
            border-color: #2A8BF5 !important;
            box-shadow: 0 0 0 1px #2A8BF5 !important;
        }

        /* 主操作按钮样式 (New Verification & Start Verification) */
        .stButton>button, button[kind="primary"] {
            background-color: #2A8BF5 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 0.5rem !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            width: 100% !important;
            transition: background-color 0.2s;
        }
        .stButton>button:hover, button[kind="primary"]:hover {
            background-color: #1D73D3 !important;
        }

        /* 修改 status widget */
        [data-testid="stStatusWidget"] {
            background-color: #1F2937 !important;
            border: 1px solid #374151 !important;
            border-radius: 0.75rem !important;
            margin-top: 1rem;
        }

        /* 自定义滚动条美化 */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #4B5563; }
    </style>
    """
    st.markdown(tailwind_css, unsafe_allow_html=True)

    # 获取系统配置
    config_params = get_config_parameters()
    if not config_params:
        st.error("Configuration not found.")
        return

    config_info = get_saved_config_info()
    model_name_disp = config_info['model_name'] if config_info else "Unknown"
    search_name_disp = config_info['search_name'] if config_info else "Unknown"

    # ==================== 页面骨架：使用 HTML/CSS 构建左右分栏 ====================
    # 我们用三个大的 st.container() 来模拟布局（但实质靠上方的 CSS `.custom-layout` 撑起）
    
    # 开启 Flex 父容器
    st.markdown('<div class="custom-layout">', unsafe_allow_html=True)

    # ---------------- 1. 左侧自定义 Sidebar ----------------
    st.markdown(f"""
    <div class="custom-sidebar">
        <div class="flex justify-between items-center mb-8">
            <h2 class='text-xl font-bold text-white m-0 flex items-center gap-2'>
                较真 <span class="text-sm">+ 🕵️‍♂️</span><br>
            </h2>
            <span class="text-gray-500 cursor-pointer">«</span>
        </div>
        <div class="text-xs text-gray-500 mb-6">Jiaozhen News Observer</div>
        
        """, unsafe_allow_html=True)
    
    # 在左侧栏放入 Streamlit 真实的按钮（利用空列占位）
    sidebar_col1, _ = st.columns([1, 0.01]) 
    with sidebar_col1:
        if st.button("New Verification"):
            st.rerun()
            
    st.markdown("""
        <div class="mt-6 flex flex-col gap-4 text-sm text-gray-400">
            <div class="flex items-center gap-2 hover:text-white cursor-pointer transition"><span class="w-4">🕘</span> Verification History</div>
            <div class="flex items-center gap-2 hover:text-white cursor-pointer transition"><span class="w-4">⚙️</span> Model Config</div>
        </div>

        <div class="mt-8 mb-2 text-xs text-gray-500">Search provider</div>
        <div class='text-sm text-gray-300 bg-gray-800 py-2 px-3 rounded border border-gray-700 mb-4'>{search_name_disp}</div>
        
        <div class="mb-2 text-xs text-gray-500">Model</div>
        <div class='text-sm text-gray-300 bg-gray-800 py-2 px-3 rounded border border-gray-700 mb-6'>{model_name_disp}</div>
        
        <div class="flex items-center gap-2 text-sm text-gray-400 hover:text-white cursor-pointer transition"><span class="w-4">🔧</span> Settings</div>

        <div class="mt-auto pt-6 border-t border-gray-800 flex flex-col gap-3">
            <div class="flex items-center gap-2 text-sm text-gray-400"><span class="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center text-xs">👤</span> Observer 001</div>
            <div class="flex items-center gap-2 text-sm text-gray-500"><span class="w-4">ⓘ</span> About</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---------------- 2. 右侧 Main Content ----------------
    st.markdown('<div class="custom-main">', unsafe_allow_html=True)
    
    # 标题区
    st.markdown("""
    <div class="mb-6 max-w-3xl mx-auto">
        <h1 class="text-3xl font-extrabold text-gray-100 tracking-tight mb-2">Input for Verification</h1>
        <p class="text-gray-500 text-sm">Paste a news article, controversial claim, or URL below to trace its origin and verify facts.</p>
    </div>
    """, unsafe_allow_html=True)

    # 真正的输入框和按钮
    main_col1, _ = st.columns([8, 1])
    with main_col1:
        user_input = st.text_area("HiddenLabel", height=120, placeholder="e.g., Reports say Company A is laying off 80% of staff...")
        start_btn = st.button("Start Verification", type="primary", key="start_verif")

    # 执行核查逻辑
    if start_btn and user_input:
        api_base, chat_model = config_params["api_base"], config_params["chat_model"]
        embedding_model, search_provider = config_params["embedding_model"], config_params["search_provider"]
        selected_language, provider_config = config_params["selected_language"], config_params["provider_config"]
        
        search_config = model_manager.get_search_provider_config(search_provider)
        fact_checker = FactChecker(
            api_base=api_base, model=chat_model, temperature=0.0, max_tokens=1000,
            embedding_base_url=api_base, embedding_model=embedding_model, embedding_api_key=provider_config.get("api_key", "lm-studio"),
            search_engine=search_provider, searxng_url=search_config.get("base_url", "http://localhost:8090"), output_language=selected_language,
            search_config=search_config,
        )

        with main_col1:
            with st.status("🕵️‍♂️ Agents are working on it...", expanded=True) as status:
                st.write("🔍 Extracting core claims...")
                claim = fact_checker.extract_claim(user_input).split("claim:")[-1].strip() if "claim:" in fact_checker.extract_claim(user_input).lower() else fact_checker.extract_claim(user_input)
                
                st.write("🌐 Tracing evidence across the web...")
                evidence_docs = fact_checker.search_evidence(claim, search_config.get("max_results", 5))
                
                st.write("🧠 Reranking semantics & cross-checking...")
                max_evidence_display = int(search_config.get("max_results", 5) * 3 * model_manager.get_current_config().get("defaults", {}).get("evidence_display_multiplier", 2.0))
                evidence_chunks = fact_checker.get_evidence_chunks(evidence_docs, claim, top_k=max_evidence_display)
                evaluation_evidence = evidence_chunks[:-1] if len(evidence_chunks) > 1 else evidence_chunks

                evaluation = fact_checker.evaluate_claim(claim, evaluation_evidence, original_text=user_input)
                status.update(label="✅ Verification Complete", state="complete", expanded=False)

            # ---------------- 解析模型输出并渲染 UI ----------------
            reasoning = evaluation.get('reasoning', '')
            
            content_text = (re.search(r'### 📊 内容核查.*?\n(.*?)(?=### 🔄|### ⚖️|$)', reasoning, re.DOTALL) or re.search('', '')).group(1) or ""
            timeline_text = (re.search(r'### 🔄 事件溯源.*?\n(.*?)(?=### 📊|### ⚖️|$)', reasoning, re.DOTALL) or re.search('', '')).group(1) or "暂无明确溯源路径。"
            summary_text = (re.search(r'总结[：:]\s*(.*)', reasoning) or re.search('', '')).group(1) or "基于多源交叉比对与信息溯源，得出以上结论。"
            
            fact_match = re.search(r'- \*\*客观事实\*\*[：:]\s*(.*?)(?=- \*\*|- 疑似|###|$)', content_text, re.DOTALL)
            opinion_match = re.search(r'- \*\*主观观点\*\*[：:]\s*(.*?)(?=- \*\*|- 疑似|###|$)', content_text, re.DOTALL)
            error_match = re.search(r'- \*\*疑似错误/不实\*\*[：:]\s*(.*?)(?=- \*\*|###|$)', content_text, re.DOTALL)

            verdict = evaluation["verdict"].upper()
            if verdict == "TRUE":
                verdict_cn, v_bg, v_border, v_text = "正确 (True)", "bg-[#14291E]", "border-green-900", "text-green-500"
                icon = "✅"
            elif verdict == "FALSE":
                verdict_cn, v_bg, v_border, v_text = "错误 (False)", "bg-[#2A1818]", "border-red-900", "text-red-500"
                icon = "❌"
            elif verdict == "PARTIALLY TRUE":
                verdict_cn, v_bg, v_border, v_text = "部分正确 (Partially True)", "bg-[#2D2A15]", "border-yellow-900", "text-yellow-500"
                icon = "⚠️"
            else:
                verdict_cn, v_bg, v_border, v_text = "无法验证 (Unverifiable)", "bg-[#1F2937]", "border-gray-700", "text-gray-400"
                icon = "❓"

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            report_html = f"""
            <div class="mt-8 animate-fade-in max-w-4xl">
                <div class="flex justify-between items-center mb-4 text-xs text-gray-500 border-b border-gray-800 pb-3">
                    <span>Verification Report ID: VRI-{datetime.now().strftime("%Y%m%d")}-001 | {current_time}</span>
                    <div class="flex gap-2">
                        <button class="px-3 py-1.5 border border-gray-700 rounded text-gray-300 hover:bg-gray-800 transition">Download PDF</button>
                        <button class="px-3 py-1.5 bg-[#2A8BF5] rounded text-white hover:bg-blue-600 transition">Cite Sources</button>
                    </div>
                </div>

                <div class="{v_bg} border {v_border} p-5 rounded-lg mb-6 shadow-sm">
                    <h2 class="text-lg font-bold {v_text} m-0 flex items-center gap-2">
                        <span>{icon}</span> Overall Verdict: {verdict_cn}
                    </h2>
                    <p class="mt-2 text-sm text-gray-300 leading-relaxed">{markdown_to_html(summary_text)}</p>
                </div>

                <div class="bg-[#1F2937] border border-gray-800 rounded-lg p-5 mb-6">
                    <h3 class="text-gray-300 font-semibold mb-4 flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-gray-400"></span> Content Verification
                    </h3>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden h-full">
                            <div class="bg-green-900/40 text-green-400 text-xs font-bold px-3 py-2 flex items-center gap-1 border-b border-green-900/50">
                                ✅ Objective Facts
                            </div>
                            <div class="p-4 text-sm text-gray-300 leading-relaxed">
                                {markdown_to_html(fact_match.group(1).strip()) if fact_match else "<span class='text-gray-600'>未提取到客观事实。</span>"}
                            </div>
                        </div>
                        
                        <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden h-full">
                            <div class="bg-red-900/40 text-red-400 text-xs font-bold px-3 py-2 flex items-center gap-1 border-b border-red-900/50">
                                🚨 Misleading / Exaggerated
                            </div>
                            <div class="p-4 text-sm text-gray-300 leading-relaxed">
                                {markdown_to_html(error_match.group(1).strip()) if error_match else "<span class='text-gray-600'>未提取到不实谬误。</span>"}
                            </div>
                        </div>
                    </div>

                    {f'''
                    <div class="bg-[#111827] border border-gray-800 rounded-lg overflow-hidden mt-4">
                        <div class="bg-blue-900/30 text-blue-400 text-xs font-bold px-3 py-2 flex items-center gap-1 border-b border-blue-900/40">
                            💬 Subjective Opinion
                        </div>
                        <div class="p-4 text-sm text-gray-400 leading-relaxed">
                            {markdown_to_html(opinion_match.group(1).strip())}
                        </div>
                    </div>
                    ''' if opinion_match and opinion_match.group(1).strip() else ""}
                </div>

                <div class="bg-[#1F2937] border border-gray-800 rounded-lg p-5 mb-6">
                    <h3 class="text-gray-300 font-semibold mb-5 flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-[#2A8BF5]"></span> Propagation Timeline
                    </h3>
                    <div class="relative border-l border-gray-700 ml-2 pl-6 py-2">
                        <div class="absolute w-2.5 h-2.5 bg-[#2A8BF5] rounded-full -left-[5.5px] top-4 shadow-[0_0_8px_rgba(42,139,245,0.8)]"></div>
                        <div class="text-sm text-gray-300 leading-relaxed">
                            {markdown_to_html(timeline_text)}
                        </div>
                    </div>
                </div>
            </div>
            """
            st.markdown(report_html, unsafe_allow_html=True)

            with st.expander("🔗 Raw Evidence Sources"):
                st.markdown(f"<div class='text-gray-400 text-sm'><b>Target Claim:</b> <i>{claim}</i></div><hr class='border-gray-800 my-2'>", unsafe_allow_html=True)
                for j, chunk in enumerate(evaluation_evidence):
                    title = chunk.get('title', '🔗')
                    st.markdown(f"<div class='mb-4 text-sm text-gray-300'><b>[{j+1}] <a href='{chunk['source']}' class='text-[#2A8BF5] hover:underline' target='_blank'>{title}</a></b><br><span class='text-gray-500 mt-1 block'>{chunk['text']}</span></div>", unsafe_allow_html=True)

            db_utils.save_fact_check(st.session_state.user_id, user_input, claim, verdict, evaluation["reasoning"], evaluation_evidence)

    # 关闭 right div
    st.markdown('</div>', unsafe_allow_html=True)
    # 关闭 layout div
    st.markdown('</div>', unsafe_allow_html=True)
    
def show_history_page():
    """显示历史记录页面"""
    st.header("历史记录")
    st.write("以下是您过去进行的事实核查记录")

    # 分页控制
    items_per_page = 5
    total_items = db_utils.count_user_history(st.session_state.user_id)

    if "history_page" not in st.session_state:
        st.session_state.history_page = 0

    total_pages = (total_items + items_per_page - 1) // items_per_page

    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("上一页", disabled=(st.session_state.history_page == 0)):
                st.session_state.history_page -= 1
                st.rerun()
        with col2:
            st.write(f"第 {st.session_state.history_page + 1} 页，共 {total_pages} 页")
        with col3:
            if st.button(
                "下一页",
                disabled=(
                    st.session_state.history_page == total_pages - 1 or total_pages == 0
                ),
            ):
                st.session_state.history_page += 1
                st.rerun()

    # 获取用户历史记录
    history_items = db_utils.get_user_history(
        st.session_state.user_id,
        limit=items_per_page,
        offset=st.session_state.history_page * items_per_page,
    )

    if not history_items:
        st.info("您还没有任何历史记录")
        return

    # 显示历史记录
    for item in history_items:
        with st.container():
            cols = st.columns([4, 1, 1])
            with cols[0]:
                st.subheader(
                    f"{item['claim'][:100]}..."
                    if len(item["claim"]) > 100
                    else item["claim"]
                )

                # 添加判断结果和时间
                verdict = item["verdict"].upper()
                if verdict == "TRUE":
                    emoji = "✅"
                    verdict_cn = "正确"
                elif verdict == "FALSE":
                    emoji = "❌"
                    verdict_cn = "错误"
                elif verdict == "PARTIALLY TRUE":
                    emoji = "⚠️"
                    verdict_cn = "部分正确"
                else:
                    emoji = "❓"
                    verdict_cn = "无法验证"

                st.write(f"结论: {emoji} {verdict_cn}")
                st.write(f"时间: {item['created_at']}")

            with cols[1]:
                if st.button("查看详情", key=f"view_{item['id']}"):
                    st.session_state.current_history_id = item["id"]
                    st.session_state.page = "details"
                    st.rerun()

            st.divider()


def show_history_detail_page():
    """显示历史记录详情页面"""
    if st.session_state.current_history_id is None:
        st.error("未找到历史记录")
        if st.button("返回历史列表"):
            st.session_state.page = "history"
            st.rerun()
        return

    # 获取历史记录详情
    history_item = db_utils.get_history_by_id(st.session_state.current_history_id)

    if not history_item:
        st.error("未找到历史记录")
        if st.button("返回历史列表"):
            st.session_state.page = "history"
            st.rerun()
        return

    # 显示返回按钮
    if st.button("返回历史列表"):
        st.session_state.page = "history"
        st.rerun()

    # 显示历史记录详情
    st.header("核查详情")

    st.subheader("原始文本")
    st.write(history_item["original_text"])

    st.subheader("🔍 提取的核心声明")
    st.write(history_item["claim"])

    # 显示证据
    st.subheader("🔗 证据来源")
    for j, chunk in enumerate(history_item["evidence"]):
        st.markdown(f"**[{j+1}]:**")
        st.markdown(f"{chunk['text']}")
        st.markdown(f"来源: {chunk['source']}")
        if "similarity" in chunk and chunk["similarity"] is not None:
            st.markdown(f"相关性: {chunk['similarity']:.2f}")
        st.markdown("---")

    # 显示判断结果
    verdict = history_item["verdict"].upper()
    if verdict == "TRUE":
        emoji = "✅"
        verdict_cn = "正确"
    elif verdict == "FALSE":
        emoji = "❌"
        verdict_cn = "错误"
    elif verdict == "PARTIALLY TRUE":
        emoji = "⚠️"
        verdict_cn = "部分正确"
    else:
        emoji = "❓"
        verdict_cn = "无法验证"

    st.subheader(f"{emoji} 结论: {verdict_cn}")

    st.subheader("推理过程")
    st.write(history_item["reasoning"])

    # 显示导出选项
    st.divider()
    st.subheader("导出报告")

    # 创建PDF导出按钮
    try:
        pdf_data = generate_fact_check_pdf(history_item)

        # 生成文件名
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"事实核查报告_{current_time}.pdf"

        # 使用HTML强制下载
        pdf_b64 = base64.b64encode(pdf_data).decode()
        href = f"""
        <a href="data:application/pdf;base64,{pdf_b64}" 
        download="{filename}" 
        target="_blank"
        style="display: inline-block; padding: 0.25em 0.5em; 
        background-color: #4CAF50; color: white; 
        text-decoration: none; border-radius: 4px;">
        导出为PDF
        </a>
        """
        st.markdown(href, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"PDF生成错误: {str(e)}")
        st.info("请确保已安装ReportLab库: pip install reportlab")


# 全局状态初始化
if "page" not in st.session_state:
    st.session_state.page = "home"  # 可能的值: 'home', 'history', 'details'

if "current_history_id" not in st.session_state:
    st.session_state.current_history_id = None

# 早期检查持久登录状态 - 在任何UI显示之前
if "user_id" not in st.session_state or st.session_state.user_id is None:
    saved_login = auth.check_saved_login()
    if saved_login:
        st.session_state.user_id = saved_login["user_id"]
        st.session_state.username = saved_login["username"]
        st.session_state.persisted_login = saved_login

# 检查是否已登录，否则显示登录界面
is_authenticated = auth.show_auth_ui()

if is_authenticated:
    # 用户已登录，检查是否需要配置
    
    # 检查用户配置状态
    if not check_user_config_status():
        # 显示配置向导
        show_initial_config_wizard()
    else:
        # 配置完成，显示主应用程序
        # 在右上角显示登录信息
        user_col1, user_col2 = st.columns([1, 0.1])
        with user_col1:
            st.write("")  # 占位符
        with user_col2:
            st.markdown(
                f"""
                <div style="text-align: right; padding: 0.5rem 1rem; 
                            background-color: #f0f2f6; border-radius: 0.5rem;
                            margin-bottom: 1rem; font-size: 0.875rem;">
                    👤 <strong>{st.session_state.username}</strong>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        # 显示顶部导航栏
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            st.title("")
        with col2:
            if st.button("首页", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()
        with col3:
            if st.button("历史记录", use_container_width=True):
                st.session_state.page = "history"
                st.rerun()
        with col4:
            if st.button("登出", use_container_width=True):
                auth.logout()
                st.rerun()

        # 根据当前页面显示不同的内容
        if st.session_state.page == "home":
            # 主页 - 使用简化的事实核查界面
            show_simplified_fact_check_page()
        elif st.session_state.page == "history":
            # 历史记录页面
            show_history_page()
        elif st.session_state.page == "details":
            # 历史详情页面
            show_history_detail_page()