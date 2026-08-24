#!/usr/bin/env bash
# Восстанавливает окружение навыков на новой машине.
# Запуск:  bash ~/.claude/skills/bootstrap/bootstrap.sh
set -euo pipefail

CLAUDE_DIR="$HOME/.claude"
SKILLS="$CLAUDE_DIR/skills"
MP="$CLAUDE_DIR/mattpocock-skills"
HERE="$(cd "$(dirname "$0")" && pwd)"

[ -d "$SKILLS/.git" ] || { echo "error: запускать после клонирования репозитория в $SKILLS"; exit 1; }

echo "== 1/6 набор Matt Pocock (ось процесса) =="
if [ -d "$MP/.git" ]; then
  git -C "$MP" pull --ff-only && echo "  обновлён"
else
  git clone --depth 1 https://github.com/mattpocock/skills.git "$MP"
fi

echo "== 2/6 локальный патч: code-review -> review-two-axis =="
# Встроенный /code-review ищет баги корректности; этот проверяет стандарты и спеку.
# Имена не должны совпадать, иначе один затеняет другой.
CR="$MP/skills/engineering/code-review/SKILL.md"
if grep -q '^name: code-review$' "$CR"; then
  sed -i 's/^name: code-review$/name: review-two-axis/' "$CR"
  sed -i 's|/code-review|/review-two-axis|g' "$MP/skills/engineering/implement/SKILL.md"
  echo "  применён"
else
  echo "  уже применён"
fi

echo "== 3/6 симлинки на 25 навыков процесса =="
python3 - "$MP" "$SKILLS" <<'PY'
import json, os, sys
mp, dest = sys.argv[1], sys.argv[2]
RENAME = {"code-review": "review-two-axis"}
n = 0
for rel in json.load(open(f"{mp}/.claude-plugin/plugin.json"))["skills"]:
    src = os.path.normpath(os.path.join(mp, rel))
    name = RENAME.get(os.path.basename(src), os.path.basename(src))
    link = os.path.join(dest, name)
    if os.path.lexists(link):
        if not os.path.islink(link):
            print(f"  пропуск (реальный каталог, не трогаю): {name}"); continue
        os.remove(link)
    os.symlink(src, link); n += 1
print(f"  создано: {n}")
PY

echo "== 4/6 агенты =="
mkdir -p "$CLAUDE_DIR/agents"
cp -n "$SKILLS/agents/"*.md "$CLAUDE_DIR/agents/" 2>/dev/null || true
echo "  в $CLAUDE_DIR/agents: $(ls "$CLAUDE_DIR"/agents/*.md 2>/dev/null | wc -l) шт."

echo "== 5/6 глобальные правила =="
if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
  if cmp -s "$HERE/CLAUDE.global.md" "$CLAUDE_DIR/CLAUDE.md"; then
    echo "  уже на месте"
  else
    echo "  $CLAUDE_DIR/CLAUDE.md отличается, не перезаписываю."
    echo "  сверьте вручную: diff $HERE/CLAUDE.global.md $CLAUDE_DIR/CLAUDE.md"
  fi
else
  cp "$HERE/CLAUDE.global.md" "$CLAUDE_DIR/CLAUDE.md"
  echo "  установлен $CLAUDE_DIR/CLAUDE.md"
fi

echo "== 6/6 Python-окружение для документов (docx, pdf, pptx, xlsx, иврит) =="
if [ -d "$SKILLS/.venv-docs" ]; then
  echo "  уже есть"
else
  python3 -m venv "$SKILLS/.venv-docs"
  "$SKILLS/.venv-docs/bin/pip" install -q --upgrade pip
  "$SKILLS/.venv-docs/bin/pip" install -q -r "$HERE/requirements-docs.txt"
  echo "  создано (~395 МБ)"
fi

echo
echo "Готово. Дальше вручную, по необходимости:"
echo "  - системный Python для seo/: pip install -r $SKILLS/seo/requirements.txt"
echo "  - браузеры Playwright:        python3 -m playwright install chromium"
echo "  - GitHub как трекер задач:    sudo apt install gh && gh auth login"
echo "  - разрешения:                 сверьте $HERE/settings.reference.json"
echo "                                с $CLAUDE_DIR/settings.json (не копируйте поверх)"
