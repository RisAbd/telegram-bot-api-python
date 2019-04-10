# Library for Telegram Bot API on python

```python
from main import *

bot = Bot.by(TOKEN)
print(bot.webhookinfo())
print(bot.updates())

bot.send_chat_action(chat_id, Chat.ACTION.TYPING)
bot.send_message(chat=chat_id, text='_lel_ *kek* `xd`', parse_mode=Message.ParseMode.MARKDOWN)
```