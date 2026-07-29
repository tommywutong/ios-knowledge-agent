#!/bin/zsh
# 双击启动 iOS 知识库网页版（浏览器会自动打开）
cd "${0:A:h}"
export PATH="$HOME/.local/bin:$PATH"
exec uv run ioskb web
