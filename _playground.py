
from telegram import *
from decouple import config


def test(bot):

    assert bot._prepare_value(dict(allowed_updates=[Update.Type.MESSAGE, Update.Type.EDITED_MESSAGE],
                                   after=Update(id=1), chat=Chat(id=1, type='private'),
                                   reply_to_message=Message(id=1, date=0, chat=dict(id=1, type='private'), text='lel kek xd'),
                                   caption='lel kek xd', parse_mode=Message.ParseMode.MARKDOWN,
                                   action=Chat.Action.TYPING,
                                   some=None, another=None, kek=[1,2, None]
                                   )) == dict(allowed_updates=['message', 'edited_message'],
                                              after=2, chat=1,
                                              reply_to_message=1,
                                              caption='lel kek xd',
                                              parse_mode='Markdown',
                                              action='typing',
                                              kek=[1,2]
                                              )


def main():
    BOT_API_TOKEN = config('BOT_API_TOKEN', cast=str)
    LOGLEVEL = config('LOGLEVEL', cast=str, default='DEBUG')

    logger.level = getattr(logging, LOGLEVEL, logging.DEBUG)
    logging.basicConfig()

    from pprint import pprint

    # markup = ReplyKeyboardMarkup.from_rows_of(buttons=list('abcdef'), items_in_row=3)
    # pprint(markup.keyboard)

    # another_markup = ReplyKeyboardMarkup.construct(
    #     ReplyKeyboardMarkup.row(ReplyKeyboardMarkup.Button('lel'), ReplyKeyboardMarkup.Button('kek')),
    #     ReplyKeyboardMarkup.row(buttons=[ReplyKeyboardMarkup.Button('xd'), ReplyKeyboardMarkup.Button('lil')]),
    #     ReplyKeyboardMarkup.row(buttons=['kak', 'dela?', 'vashi']),
    # )
    # pprint(another_markup.keyboard)


    bot = Bot.by(BOT_API_TOKEN)

    # test prepare_value
    test(bot)

    # download file by file_id
    # with open('hicranda_gonlum.mp3', 'wb') as f:
    #     f.write(bot.file('CQADAgADvAMAArCqWEsSWuzVBRHRfRYE'))

    # get webhook info
    # print(bot.webhookinfo())

    # set webhook
    # print(bot.set_webhook('https://kekmek.tk/telegram/bot'))

    # delete webhook
    print(bot.delete_webhook())

    # get bot updates by long-polling
    updates = bot.updates()


    markup = InlineKeyboardMarkup.from_rows_of(
        buttons=list(map(lambda t: InlineKeyboardMarkup.Button(text=t, callback_data=t), 'abcdefghikl')), 
        items_in_row=3, 
    )
    pprint(markup.inline_keyboard)

    u = None
    while True:
        print('sleeping...')
        time.sleep(2)
        for u in bot.updates(after=u, timeout=5):
            print(u)
            print(u.type)
            chat = None
            if u.type == u.Type.MESSAGE:
                chat = u.message.chat
            elif u.type == u.Type.CALLBACK_QUERY:
                chat = u.callback_query.message.chat
            
            if chat is not None:
                bot.send_message(chat=chat, 
                                text='*lel* _kek_ `xd`', 
                                parse_mode=Message.ParseMode.MARKDOWN, 
                                reply_markup=markup,
                                )
            else:
                logger.warning('chat is None, update type is unhandled: %r', u.type)

    # updates = bot.updates(after=locals().get('u'))
    # assert updates == []

    # send chat action
    # action_sent = bot.send_chat_action(u.message.chat, Chat.Action.TYPING)
    # time.sleep(0.5)

    # send message
    # sent_message = bot.send_message(chat=u.message.chat, text='*lel* _kek_ `xd`', parse_mode=Message.ParseMode.MARKDOWN)
    # print(sent_message)

    # import io
    # with io.BytesIO(b'some content file') as f: 
    #     f.name = 'kek.txt'

    # send document, document can be file-like object, or file_id of existing file
    # message_with_doc = bot.send_document(chat=u.message.chat, document='BQADAgAD4QIAAobqmUmE8Yh3E-vvMgI', 
    #                                      caption='hey see my _*document*_ here',
    #                                      parse_mode=Message.ParseMode.MARKDOWN,
    #                                      reply_to_message=u.message,
    #                                      )
    # print(message_with_doc)


if __name__ == '__main__':
    main()
