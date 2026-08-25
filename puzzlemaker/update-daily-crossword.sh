#!/bin/bash
set -uo pipefail

# 0. This script lives INSIDE the daily-swedish-crossword repo (it's
# puzzlemaker/update-daily-crossword.sh in that same checkout). There is no
# need for a separate nested clone to push through -- the repo root, one
# level up from this script, already IS the thing we need to commit and
# push. An earlier version of this script assumed it lived somewhere else
# and needed its own "daily-swedish-crossword" clone alongside it; that
# clone ended up nested at puzzlemaker/daily-swedish-crossword/ and got
# written to and pushed instead of the real repo root daily.xml -- the file
# 1.0.8-and-earlier app builds actually read
# (raw.githubusercontent.com/.../main/daily.xml). That nested clone is
# unrelated to this file's output and should be deleted on the server.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel)"

TEMPLATE_DIR="$SCRIPT_DIR/templates"
CLUES_FILE="$SCRIPT_DIR/posta_clues_upper.csv"
COMMIT_MSG="Update daily crossword"

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

# 1. Pick today's template deterministically from the pool.
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

# 2. Make sure the repo checkout is up to date and clean before we write
# into it, so a stray local commit never silently blocks the push below.
cd "$REPO_DIR" || exit 1
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/byesilbag/daily-swedish-crossword.git"
git pull origin main

# 3. Run the Python Generator, writing straight into the repo root -- the
# exact path old app versions fetch via raw.githubusercontent.com.
echo "Generating crossword..."
python3 "$SCRIPT_DIR/generate_crossword_optimized.py" -i "$TEMPLATE_FILE" -c "$CLUES_FILE" -o "$REPO_DIR/daily.xml"

if [ $? -ne 0 ]; then
    echo "Error: Python script failed. Aborting."
    exit 1
fi

# 4. Git Operations
git add daily.xml

if git diff-index --quiet HEAD --; then
    echo "No changes detected in daily.xml. Nothing to push."
else
    echo "Committing changes..."
    git commit -m "$COMMIT_MSG"

    echo "Pushing to GitHub..."
    if git push origin main; then
        echo "Success! daily.xml updated at raw.githubusercontent.com/byesilbag/daily-swedish-crossword/main/daily.xml"
    else
        echo "Error: push failed. daily.xml was generated but NOT published."
        exit 1
    fi
fi
