"""Paper Audit configuration template.

Copy this file to config.py and fill in your own credentials.
Never commit config.py.
"""

# OpenAI-compatible LLM API. Required for semantic review unless you only use cached/local steps.
LLM_API_KEY = "YOUR_OPENAI_COMPATIBLE_API_KEY"
LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-4o-mini"

# Optional request controls
LLM_TIMEOUT = 120
LLM_RETRIES = 2

# Optional MinerU token. Small files may work without this depending on selected mode/API.
MINERU_TOKEN = ""
MINERU_BASE = "https://mineru.net"

# Optional GLM multimodal API for image semantic understanding.
GLM_API_KEY = "YOUR_BIGMODEL_API_KEY"
GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_VISION_MODEL = "glm-4.6v-flash"
