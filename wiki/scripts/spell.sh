npm run spellcheck
if [ $? -eq 0 ]; then
    echo YAY
else
    echo "."
    echo ".."
    echo "..."
    echo "....  Spelling errors found in your files, please see the report above."
    echo "...   Run npm run spellcheck:interactive for interactive correction."
    echo ".."
    echo "."
    exit 1
fi