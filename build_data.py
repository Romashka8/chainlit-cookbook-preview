#!/usr/bin/env python3
"""Rebuild data.js from the checked-in GitHub tree using only Python stdlib.

Run: python3 build_data.py. Raw files are pinned to tree.json's SHA.
Missing optional files are not errors; failed HTTP requests are retained on
both the file and recipe, so no recipe disappears on a network failure.
"""
import concurrent.futures
import json
from pathlib import Path
import ssl
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
TLS = ssl.create_default_context()
# python.org macOS builds can lack their own CA bundle; use the OS bundle.
if ssl.get_default_verify_paths().cafile is None and Path("/etc/ssl/cert.pem").exists():
    TLS.load_verify_locations("/etc/ssl/cert.pem")

# Curated from each recipe's README and representative source.
CHAT = "Чат и модели"
AGENT = "Агенты и инструменты"
DATA = "Данные и RAG"
UI = "Интерфейс"
INFRA = "Инфраструктура"
METADATA = {
    "ai-web-search-linkup": ("AI Web Search with Linkup", "Ассистент с веб-поиском Linkup и вызовом инструментов через LiteLLM.", AGENT, ["Linkup", "LiteLLM", "Claude", "web search"]),
    "anthropic-chat": ("Claude Chat", "Потоковый чат с Claude и историей сообщений в пользовательской сессии.", CHAT, ["Anthropic", "Claude", "streaming"]),
    "anthropic-functions-streaming": ("Claude Tool Calling", "Claude вызывает калькулятор и демонстрационный инструмент погоды с потоковым ответом.", AGENT, ["Anthropic", "tool calling", "streaming"]),
    "archive/agent-image-editing": ("Image Generation and Editing Agent", "Агент LangChain генерирует и редактирует изображения через Stability AI.", AGENT, ["LangChain", "Stability AI", "images"]),
    "archive/groq-llama3-llamaindex-hf": ("Groq Llama 3 RAG", "Чат по документам с LlamaIndex, Llama 3 на Groq и эмбеддингами Hugging Face.", DATA, ["Groq", "LlamaIndex", "Hugging Face", "RAG"]),
    "archive/haystack": ("Haystack Conversational Search", "Агент Haystack отвечает о семи чудесах света с поиском BM25 по документам.", DATA, ["Haystack", "BM25", "OpenAI", "RAG"]),
    "archive/langchain-ask-human": ("Ask Human Tool", "Инструмент агента запрашивает уточнение у пользователя через AskUserMessage.", AGENT, ["LangChain", "LangGraph", "human-in-the-loop"]),
    "archive/openai-functions": ("OpenAI Function Calling", "Вызов функций OpenAI на примере инструмента с фиксированными данными о погоде.", AGENT, ["OpenAI", "tool calling"]),
    "archive/openai-functions-codeinterpreter": ("Plugin-Based Code Interpreter", "Ассистент OpenAI загружает плагины для выполнения Python и работы с изображениями.", AGENT, ["OpenAI", "Python", "plugins", "code execution"]),
    "auth": ("Custom OAuth Providers", "Подключение собственного OAuth-провайдера на примере Azure AD B2C.", INFRA, ["OAuth", "authentication", "Azure AD B2C"]),
    "aws-ecs-deployment": ("Deploy to AWS ECS", "Развёртывание простого приложения Chainlit в контейнере на AWS ECS.", INFRA, ["AWS", "ECS", "Docker", "deployment"]),
    "azure-openai-pinecone-pdf-qa": ("Azure OpenAI PDF Q&A", "Индексация PDF в Pinecone и ответы по документам с помощью Azure OpenAI.", DATA, ["Azure OpenAI", "Pinecone", "PDF", "RAG"]),
    "baseten-llama-2-chat": ("Llama 2 Chat on Baseten", "Потоковый чат с моделью Llama 2, размещённой на Baseten.", CHAT, ["Baseten", "Llama 2", "streaming"]),
    "bigquery": ("BigQuery Data Assistant", "Генерация SQL из вопроса, выполнение запроса в BigQuery и объяснение результатов.", DATA, ["BigQuery", "SQL", "OpenAI"]),
    "chroma-qa-chat": ("Chroma PDF Q&A", "Индексация локальных PDF в Chroma и ответы с указанием источников.", DATA, ["Chroma", "PDF", "LangChain", "RAG"]),
    "confirm-action": ("Confirm with Actions", "Кнопки продолжения и отмены для запроса подтверждения у пользователя.", UI, ["actions", "confirmation"]),
    "copilot": ("Embedded Copilot Widget", "Встраивание виджета Chainlit на веб-страницу с простым ответом Hello World.", UI, ["copilot", "widget", "embedding"]),
    "custom-element": ("Custom PDF Selector", "Пользовательский элемент выбора PDF передаёт выбранные файлы в Python callback.", UI, ["CustomElement", "actions", "PDF"]),
    "custom-frontend": ("Custom React Frontend", "Собственный React-интерфейс с клиентом Chainlit и сервером FastAPI.", UI, ["React", "FastAPI", "react-client"]),
    "custom-logo": ("Custom Logo and Favicon", "Пример оформления Chainlit с собственными логотипом и favicon.", UI, ["branding", "logo", "favicon"]),
    "deepseek-r1": ("DeepSeek R1 Reasoning Chat", "Отображение потока рассуждений DeepSeek R1 отдельным шагом перед финальным ответом.", CHAT, ["DeepSeek", "reasoning", "streaming"]),
    "extended-thinking-in-the-ui": ("Extended Thinking in the UI", "Показ thinking-токенов Claude 3.7 Sonnet в отдельном раскрывающемся шаге интерфейса.", UI, ["Anthropic", "Claude", "reasoning", "steps"]),
    "fly-io-deployment": ("Deploy to Fly.io", "Инструкция по развёртыванию простого приложения Chainlit на Fly.io.", INFRA, ["Fly.io", "deployment"]),
    "humanlayer-openai": ("HumanLayer Approval Agent", "Агент OpenAI запрашивает одобрение человека через HumanLayer перед возвратом заказа.", AGENT, ["OpenAI", "HumanLayer", "human-in-the-loop"]),
    "langchain-azure-agent": ("Azure ReAct Agent", "ReAct-агент LangGraph с поиском по документам, обработкой файлов Azure и Python-песочницей.", AGENT, ["Azure", "LangGraph", "RAG", "Python"]),
    "langgraph-memory": ("LangGraph Conversation Memory", "Память LangGraph по идентификатору беседы с аутентификацией и возобновлением чата; checkpoints хранятся в памяти процесса.", CHAT, ["LangGraph", "memory", "authentication"]),
    "langgraph-tavily": ("LangGraph Tavily Agent", "Агент LangGraph вызывает веб-поиск Tavily и возвращает потоковый ответ OpenAI.", AGENT, ["LangGraph", "Tavily", "OpenAI", "web search"]),
    "llama-index": ("LlamaIndex Document Chat", "Индексация локальных документов в LlamaIndex и потоковые ответы по найденным фрагментам.", DATA, ["LlamaIndex", "OpenAI", "RAG"]),
    "llama-index-googledocs-qa": ("Google Docs Q&A with LlamaIndex", "Загрузка Google Docs в индекс LlamaIndex и ответы на вопросы по документам.", DATA, ["Google Docs", "LlamaIndex", "OpenAI", "RAG"]),
    "llava": ("LLaVA Multimodal Chat", "Чат с LLaVA, принимающий текст и изображения и передающий запросы серверу модели.", CHAT, ["LLaVA", "multimodal", "images"]),
    "loader-animation": ("Animated Waiting Indicator", "Анимированный индикатор ожидания и полоса прогресса во время асинхронной задачи.", UI, ["animation", "progress", "asyncio"]),
    "local-llm": ("Local LLM Integrations", "Примеры локального запуска моделей с Ollama, LlamaCpp и Hugging Face.", CHAT, ["Ollama", "LlamaCpp", "Hugging Face", "local LLM"]),
    "map-canvas": ("Interactive Map Canvas", "Claude управляет картой в боковой панели через инструмент и CopilotFunction.", UI, ["canvas", "map", "Anthropic", "CustomElement"]),
    "mcp": ("MCP Tool Connections", "Подключение MCP-серверов, передача инструментов Claude и отображение карточек задач.", AGENT, ["MCP", "Anthropic", "tool calling"]),
    "mcp-linear": ("Linear MCP Assistant", "Инструменты Linear через MCP и отображение данных задачи в пользовательской карточке.", AGENT, ["MCP", "Linear", "Anthropic", "CustomElement"]),
    "openai-concurrent-functions": ("Parallel OpenAI Function Calls", "Параллельное выполнение вызовов демонстрационного инструмента погоды от OpenAI.", AGENT, ["OpenAI", "tool calling", "asyncio"]),
    "openai-concurrent-streaming": ("Two Bots Streaming in Parallel", "Два персонажа одновременно отвечают потоками OpenAI на одно сообщение пользователя.", CHAT, ["OpenAI", "streaming", "asyncio"]),
    "openai-data-analyst": ("OpenAI Data Analyst", "Ассистент OpenAI для анализа файлов с Code Interpreter, поиском по файлам и голосовым вводом.", DATA, ["OpenAI Assistants", "Code Interpreter", "files", "audio"]),
    "openai-functions-streaming": ("Streaming OpenAI Function Calls", "Потоковый ответ OpenAI с вызовом функции, возвращающей демонстрационные данные о погоде.", AGENT, ["OpenAI", "tool calling", "streaming"]),
    "openai-responses-gpt5-functions-streaming": ("GPT-5 Responses and Tool Streaming", "Responses API с потоковыми вызовами инструментов, демонстрационным поиском и продолжением беседы по previous_response_id.", AGENT, ["OpenAI", "GPT-5", "Responses API", "tool calling"]),
    "openai-responses-gpt5-functions-streaming-multi-modal-reasoning-super-advanced": ("Multimodal Responses with Python Tools", "Мультимодальный ассистент Responses API с локальным выполнением Python, файлами, поиском и сводками рассуждений.", AGENT, ["OpenAI", "Responses API", "multimodal", "Python", "reasoning"]),
    "openai-whisper": ("Whisper Voice Chat", "Распознавание речи через Whisper, генерация ответа OpenAI и озвучивание ElevenLabs.", CHAT, ["OpenAI", "Whisper", "ElevenLabs", "audio"]),
    "pdf-qa": ("PDF Q&A with Pinecone", "Загрузка PDF, создание эмбеддингов в Pinecone и ответы с источниками.", DATA, ["PDF", "Pinecone", "LangChain", "RAG"]),
    "pinecone": ("Chat with a Pinecone Index", "Ответы по документам из существующего индекса Pinecone с показом источников.", DATA, ["Pinecone", "LangChain", "OpenAI", "RAG"]),
    "pyautogen": ("AutoGen Agents in Chainlit", "Агенты AutoGen выполняют код для построения графика и запрашивают обратную связь пользователя.", AGENT, ["AutoGen", "multi-agent", "code execution"]),
    "react-native-chat": ("React Native Chat Client", "Мобильный и веб-интерфейс на React Native с сервером Chainlit и FastAPI.", UI, ["React Native", "Expo", "FastAPI", "react-client"]),
    "realtime-assistant": ("OpenAI Realtime Assistant", "Голосовой и текстовый помощник на OpenAI Realtime API с вызовами инструментов.", CHAT, ["OpenAI", "Realtime API", "audio", "tool calling"]),
    "resume-chat": ("Resume a Conversation", "Восстановление истории беседы в памяти LangChain при возобновлении чата.", CHAT, ["LangChain", "memory", "chat resume"]),
    "reverse_proxy": ("Chainlit Behind a Reverse Proxy", "Размещение Chainlit под префиксом URL за Caddy через FastAPI.", INFRA, ["Caddy", "FastAPI", "reverse proxy"]),
    "suggestions": ("Follow-Up Suggestions", "Показ вариантов следующего сообщения с помощью пользовательского элемента.", UI, ["CustomElement", "suggestions"]),
    "window-message": ("Iframe Window Messages", "Обмен сообщениями между встроенным Chainlit и родительской веб-страницей.", UI, ["iframe", "window messages", "embedding"]),
}


def selected_files(recipe, blobs):
    paths = [p for p in blobs if p.startswith(recipe + "/")]
    def rank(path):
        return (path.count("/"), path.lower(), path)
    readmes = sorted((p for p in paths if Path(p).name.lower() in
                      {"readme", "readme.md", "readme.rst", "readme.txt"}), key=rank)
    sources = [p for p in paths if p.endswith(".py")]
    sources.sort(key=lambda p: (
        {"app.py": 0, "main.py": 1, "chainlit_app.py": 2}.get(Path(p).name, 3),
        *rank(p)))
    configs = sorted((p for p in paths if
                      (Path(p).name.lower().startswith("requirements") and p.endswith(".txt"))
                      or Path(p).name.lower() == ".env.example"), key=rank)
    return readmes[:1] + sources[:1] + configs


def fetch(sha, path):
    url = "https://raw.githubusercontent.com/Chainlit/cookbook/" + sha + "/" + urllib.parse.quote(path)
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "cookbook-preview-builder/1.0"})
            with urllib.request.urlopen(request, timeout=45, context=TLS) as response:
                return {"path": path, "content": response.read().decode("utf-8")}
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    return {"path": path, "content": "", "error": error}


def main():
    tree = json.loads((ROOT / "tree.json").read_text())
    if tree.get("truncated"):
        raise ValueError("tree.json is truncated; a complete tree is required")
    sha = tree["sha"]
    dirs = sorted(item["path"] for item in tree["tree"] if item["type"] == "tree"
                  and item["path"] != "archive" and
                  ("/" not in item["path"] or
                   (item["path"].startswith("archive/") and item["path"].count("/") == 1)))
    blobs = [item["path"] for item in tree["tree"] if item["type"] == "blob"]
    selections = {recipe: selected_files(recipe, blobs) for recipe in dirs}
    paths = sorted({path for selected in selections.values() for path in selected})
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        files = dict(zip(paths, pool.map(lambda path: fetch(sha, path), paths)))
    recipes = []
    for recipe in dirs:
        title, description, category, tags = METADATA.get(recipe, (
            recipe.split("/")[-1].replace("-", " ").title(),
            "Пример интеграции с Chainlit.", "Чат и модели", []))
        item = dict(id=recipe, title=title, description=description, category=category,
                    tags=tags, archived=recipe.startswith("archive/"),
                    files=[files[path] for path in selections[recipe]],
                    url=f"https://github.com/Chainlit/cookbook/tree/{sha}/{recipe}")
        errors = [{"path": f["path"], "error": f["error"]} for f in item["files"] if "error" in f]
        if errors:
            item["errors"] = errors
        recipes.append(item)
    data = {"sha": sha, "recipes": recipes}
    (ROOT / "data.js").write_text("window.COOKBOOK = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    failures = [f for f in files.values() if "error" in f]
    print(f"Coverage: {len(recipes)}/{len(dirs)} recipes; {sum(r['archived'] for r in recipes)} archived")
    print(f"Fetches: {len(files) - len(failures)}/{len(files)} succeeded; {len(failures)} failed")
    for failure in failures:
        print(f"  {failure['path']}: {failure['error']}")


if __name__ == "__main__":
    main()
