"""本地大模型配置模板。

使用方法：
1. 复制本文件为 `local_llm_config.py`。
2. 把 API_KEY 填成你自己的密钥。
3. `local_llm_config.py` 已经被 .gitignore 忽略，不要提交真实密钥。
"""

API_KEY = "在这里填你的 API key"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-ai/DeepSeek-V4-Pro"
TIMEOUT = 30
TEMPERATURE = 0.0
MAX_TOKENS = 400
