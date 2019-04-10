# Library for Telegram Bot API on python

```python
from main import *

bot = Bot.by(BOT_API_TOKEN)
print(bot)

webhookinfo = bot.webhookinfo()
print(webhookinfo)

updates = bot.updates()
u = updates[0]
print(u)

action_sent = bot.send_chat_action(u.message.chat, Chat.Action.TYPING)
time.sleep(0.5)

sent_message = bot.send_message(chat=u.message.chat, text='*lel* _kek_ `xd`', parse_mode=Message.ParseMode.MARKDOWN)
print(sent_message)

```