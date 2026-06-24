import re
import os

file_path = r'c:\Techproject\Agentyne\agentynebdr\agentyne_asoc\apps\dashboard\templates\dashboard\home.html'

print(f"Reading file: {file_path}")
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

original_length = len(content)

# 1. Fix duplicate "Metrics Cards Row" comment
# Matches the comment followed by optional whitespace and the comment again
content = re.sub(r'(<!-- Metrics Cards Row -->\s*)+<!-- Metrics Cards Row -->', '<!-- Metrics Cards Row -->', content)

# 2. Fix split template tags {{ ... }}
# Finds {{ followed by non-greedy content until }}, handling multiline via DOTALL
# Replaces internal whitespace sequences (including newlines) with a single space
def fix_tag(match):
    inner = match.group(1)
    # cleanup inner content: replace newlines/multiple spaces with single space
    clean_inner = ' '.join(inner.split())
    return f'{{{{ {clean_inner} }}}}'

# Pattern: {{ capturing_group }}
# We use non-greedy matching .*?
new_content = re.sub(r'\{\{(.*?)\}\}', fix_tag, content, flags=re.DOTALL)

if len(new_content) != original_length:
    print("Content changed.")
else:
    print("No changes in length, but content might have changed (whitespace).")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully wrote fixed content to home.html")
