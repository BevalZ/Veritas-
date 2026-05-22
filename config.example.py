# 复制本文件为 config.py 并填写你的API Key
# 🔧 配置说明：支持所有OpenAI兼容LLM API（OpenAI/DeepSeek/通义千问/豆包等）

# MinerU API 配置：https://mineru.net/apiManage/docs
# 可选，仅处理>10MB/20页PDF时需要，小文件用内置Agent API自动处理无需token
MINERU_TOKEN = "你的MinerU Token（可选）"

# OpenAI兼容LLM API 配置
# 示例1: OpenAI官方
# LLM_API_KEY = "sk-xxxxxx"
# LLM_API_URL = "https://api.openai.com/v1/chat/completions"
# LLM_MODEL = "gpt-3.5-turbo"
# 示例2: DeepSeek
# LLM_API_KEY = "sk-xxxxxx"
# LLM_API_URL = "https://api.deepseek.com/v1/chat/completions"
# LLM_MODEL = "deepseek-chat"
# 示例3: 本地Ollama
# LLM_API_KEY = "ollama"
# LLM_API_URL = "http://localhost:11434/v1/chat/completions"
# LLM_MODEL = "qwen2:7b"
LLM_API_KEY = "你的LLM API Key"
LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"
