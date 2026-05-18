content = open('storyboard_engine.py', encoding='utf-8').read()
old = '   错误：A["hello \\"world\\\""]、B["BuildTable()"]、C["\\#quot;quoted\\#quot;"]'
new = '   错误：A["hello \\"world\\\""]、B["BuildTable()"]、C["反斜杠+#quot;quoted反斜杠+#quot;"]'
if old in content:
    content = content.replace(old, new)
    open('storyboard_engine.py', 'w', encoding='utf-8').write(content)
    print('Fixed line 336')
else:
    print('Old string not found')
    # debug: find lines with #quot
    for i, line in enumerate(content.splitlines(), 1):
        if '#quot' in line:
            print(f'Line {i}: {repr(line)}')
