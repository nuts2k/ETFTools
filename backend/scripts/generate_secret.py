#!/usr/bin/env python3
"""生成安全的 SECRET_KEY

使用方式:
    python scripts/generate_secret.py

输出示例:
    SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

将输出内容复制到 .env 文件中
"""

import secrets

if __name__ == "__main__":
    secret_key = secrets.token_urlsafe(32)
    print(f"SECRET_KEY={secret_key}")
    print(f"\n# 将上面的内容添加到 .env 文件中")
    print(f"# 密钥长度: {len(secret_key)} 字符")
