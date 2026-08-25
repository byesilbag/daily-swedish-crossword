#!/bin/bash
set -uo pipefail

# 0. Resolve every path relative to this script's own location, not the
# caller's working directory. Cron invokes this as "./update-daily-crossword.sh"
# from whatever cwd is set in the crontab entry -- if that cwd ever drifts
# (or someone runs it manually from elsewhere), relative paths like
# "daily-swedish-crossword" or "templates" silently point at the wrong place,
# the script fails early, and daily.xml just stops updating with no obvious
# signal beyond a quiet gap in cron.log.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 1. Configuration
REPO_DIR="$SCRIPT_DIR/daily-swedish-crossword"
REPO_URL="https://github.com/byesilbag/daily-swedish-crossword.git"
COMMIT_MSG="Update daily crossword"
TEMPLATE_DIR="$SCRIPT_DIR/templates"
CLUES_FILE="$SCRIPT_DIR/posta_clues_upper.csv"

# Check if GITHUB_TOKEN is set
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set."
    echo "Usage: GITHUB_TOKEN=your_token_here ./update-daily-crossword.sh"
    exit 1
fi

if [ ! -f "$CLUES_FILE" ]; then
    echo "Error: Clues file not found at $CLUES_FILE"
    exit 1
fi

# 1b. Pick today's template deterministically from the pool.
# Same calendar day -> same template, even if this script runs more than
# once that day. The pool rotates so consecutive days don't repeat the
# same grid shape, instead of always using a single fixed layout.
TEMPLATES=("$TEMPLATE_DIR"/*.xml)
TEMPLATE_COUNT=${#TEMPLATES[@]}

if [ "$TEMPLATE_COUNT" -eq 0 ]; then
    echo "Error: No templates found in $TEMPLATE_DIR/."
    exit 1
fi

DAY_OF_YEAR=$(date -u +%j)   # 001-366
DAY_OF_YEAR=$((10#$DAY_OF_YEAR))  # strip leading zeros, force base-10
TEMPLATE_INDEX=$((DAY_OF_YEAR % TEMPLATE_COUNT))
TEMPLATE_FILE="${TEMPLATES[$TEMPLATE_INDEX]}"

echo "Selected template: $TEMPLATE_FILE (day $DAY_OF_YEAR of $TEMPLATE_COUNT templates)"

# 1c. Make sure we have a local clone to push through. Previously this was a
# hard requirement the operator had to set up by hand; if that clone was ever
# missing (fresh box, wrong path, accidentally deleted) the script just
# errored out on every run instead of recovering, so daily.xml silently
# stopped reaching the address old app versions still read
# (raw.githubusercontent.com/.../main/daily.xml).
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Repo not found at $REPO_DIR, cloning..."
    git clone "$REPO_URL" "$REPO_DIR" || { echo "Error: clone failed."; exit 1; }
fi

# 2. Run the Python Generator, writing straight into the repo clone so the
# committed file (repo root daily.xml) is exactly what old app versions fetch.
echo "Generating crossword..."
python3 "$SCRIPT_DIR/generate_crossword_optimized.py" -i "$TEMPLATE_FILE" -c "$CLUES_FILE" -o "$REPO_DIR/daily.xml"

# Check if Python script succeeded
if [ $? -ne 0 ]; then
    echo "Error: Python script failed. Aborting."
    exit 1
fi

# 3. Git Operations
cd "$REPO_DIR" || exit 1

# Configure remote with token for authentication
# This sets the origin to https://<TOKEN>@github.com/...
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/byesilbag/daily-swedish-crossword.git"

# Pull latest changes to avoid conflicts (optional but recommended)
git pull origin main  # Change 'main' to 'master' if that is your default branch

# Stage the file
git add daily.xml

# Check if there are changes to commit
if git diff-index --quiet HEAD --; then
    echo "No changes detected in daily.xml. Nothing to push."
else
    echo "Committing changes..."
    git commit -m "$COMMIT_MSG"

    echo "Pushing to GitHub..."
    if git push origin main; then # Change 'main' to 'master' if needed
        echo "Success! daily.xml updated at raw.githubusercontent.com/byesilbag/daily-swedish-crossword/main/daily.xml"
    else
        echo "Error: push failed. daily.xml was generated but NOT published."
        exit 1
    fi
fi
