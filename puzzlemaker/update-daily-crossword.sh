#!/bin/bash

# 1. Configuration
# We use an environment variable for the token to keep it secure.
REPO_DIR="daily-swedish-crossword"
REPO_URL="https://github.com/byesilbag/daily-swedish-crossword.git"
COMMIT_MSG="Update daily crossword"
TEMPLATE_DIR="templates"

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set."
    echo "Usage: GITHUB_TOKEN=your_token_here ./update_crossword.sh"
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

# 2. Run the Python Generator
echo "Generating crossword..."
python3 generate_crossword_optimized.py -i "$TEMPLATE_FILE" -c posta_clues_upper.csv -o "$REPO_DIR/daily.xml"

# Check if Python script succeeded
if [ $? -ne 0 ]; then
    echo "Error: Python script failed. Aborting."
    exit 1
fi

# 3. Git Operations
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR" || exit

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
        git push origin main # Change 'main' to 'master' if needed
        echo "Success!"
    fi
else
    echo "Error: Directory $REPO_DIR does not exist. Please clone the repository first."
    exit 1
fi

