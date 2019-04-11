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

import io
with io.BytesIO(b'some content file') as f:
    f.name = 'kek.txt'

    # document can be file object or 'BQADBAADmQAD17aEUaCF8A1RHZMnAg'-like or 'http://example.com/some.doc.png'-like string
    message_with_doc = bot.send_document(chat=u.message.chat, document=f, 
                                         caption='hey see my _*document*_ here',
                                         parse_mode=Message.ParseMode.MARKDOWN,
                                         reply_to_message_id=u.message.id,
                                         )

print(message_with_doc)

```