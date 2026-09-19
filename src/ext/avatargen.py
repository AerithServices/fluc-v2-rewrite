emojis = [
    '1f921',
    '1f480',
    '26a1',
    '1f479',
    '1f44f',
    '1f47a',
    '1faa6',
    '1f4a5',
    '1f4e2',
    '1f5a4',
    '1f525',
    '1f3af',
    '1f300',
    '1f32a'
]
for emoji in emojis:
    url = 'https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{}.png'
    print(url.format(emoji))