import json
import requests

with open('config/massdm.json', 'r') as file:
    config = json.load(file)

tokens = config['tokens']
for token in tokens:
    headers = {
        'authorization': f'Bot {token}'
    }
    response = requests.get('https://discord.com/api/users/@me', headers=headers)
    bot_id = response.json()['id']
    if response.ok:
        print(
            f'https://discord.com/oauth2/authorize?client_id={bot_id}&scope=bot&permissions=0'
        )
    else:
        print(f'Failed: {token}')