#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 首次安装：没有 config.yaml 时按示例生成一份（含占位凭证，按需修改）
if [ ! -f config.yaml ]; then
  cp config.yaml.example config.yaml
  echo "已生成 config.yaml（来自 config.yaml.example），如需余额/提醒请填写后重启服务"
fi
