#!/usr/bin/env bash
# PostToolUse hook: run tsc --noEmit after TypeScript file edits
# Only fires when the edited file is .ts or .tsx within a TypeScript project

source ~/.claude/wire-cutter.sh 2>/dev/null
[ -f ~/.claude/.wire-cut-all ] && exit 0
[ -f ~/.claude/.wire-cut-hooks ] && exit 0

# Read the tool result from stdin
input=$(cat)

# Extract the file path from the tool result
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.command // ""' 2>/dev/null)

# Only proceed for TypeScript files
case "$file_path" in
  *.ts|*.tsx) ;;
  *) exit 0 ;;
esac

# Find the nearest tsconfig.json by walking upward
dir=$(dirname "$file_path")
tsconfig=""
while [ "$dir" != "/" ]; do
  if [ -f "$dir/tsconfig.json" ]; then
    tsconfig="$dir/tsconfig.json"
    break
  fi
  dir=$(dirname "$dir")
done

# No tsconfig found — skip
[ -z "$tsconfig" ] && exit 0

project_dir=$(dirname "$tsconfig")

# Run tsc --noEmit from the project directory
cd "$project_dir" || exit 0
npx tsc --noEmit 2>&1 | head -30

# Report result
if [ ${PIPESTATUS[0]} -eq 0 ]; then
  echo "tsc: OK"
else
  echo "tsc: type errors detected (see above)"
  exit 1
fi
