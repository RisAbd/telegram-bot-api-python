#!/usr/bin/env python3

import requests
from decouple import config
import attr
import functools as FT, itertools as IT, typing as T
import enum
import time


# UTILS

def _from(cls, result: T.Union[list, dict], many=False, **kwargs):
    converter_map = getattr(cls, 'converter_map', {})
    if many:
        return list(map(FT.partial(cls.from_, many=False), result))
    return cls(**{converter_map.get(k, k): v for k, v in result.items()}, **kwargs)


def from_added(cls):
    cls.from_ = cls.converter = classmethod(_from)
    cls.list = classmethod(FT.partial(_from, many=True))
    return cls


@from_added
class ConverterMixin:
    pass


BOT_API_TOKEN = config('BOT_API_TOKEN', cast=str)


class Api:
    HOST = 'https://api.telegram.org'
    BOT = '/bot{token}'

    ME = '/getme'
    UPDATES = '/getupdates'
    WEBHOOK_INFO = '/getwebhookinfo'
    SEND_MESSAGE = '/sendmessage'
    SEND_CHAT_ACTION = '/sendChatAction'

    def _api(api):
        return classmethod(lambda cls, token: cls.HOST + cls.BOT.format(token=token) + api)

    me = _api(ME)
    updates = _api(UPDATES)
    webhookinfo = _api(WEBHOOK_INFO)
    send_message = _api(SEND_MESSAGE)
    send_chat_action = _api(SEND_CHAT_ACTION)


@attr.s
class WebhookInfo(ConverterMixin):
    url = attr.ib()
    has_custom_certificate = attr.ib()
    pending_update_count = attr.ib()
    last_error_date = attr.ib(default=None)
    last_error_message = attr.ib(default=None)
    max_connections = attr.ib(default=None)
    allowed_updates = attr.ib(default=None)


@attr.s
class User(ConverterMixin):
    id = attr.ib(hash=True)
    is_bot = attr.ib(hash=True)
    first_name = attr.ib()
    last_name = attr.ib(default=None)
    username = attr.ib(default=None)
    language_code = attr.ib(default=None)


@attr.s(frozen=True)
class Bot(User):
    _api_token = attr.ib(repr=False, kw_only=True)

    @classmethod
    def by(cls, token):
        r = requests.get(Api.me(token), ).json()['result']
        return Bot.from_(r, api_token=token)

    def request(self, method, url_builder, _verbose=False, **kwargs):
        r = requests.request(method, url_builder(token=self._api_token), **kwargs)
        if _verbose: print(r)
        j = r.json()
        if _verbose: print(j)
        return j['result']

    def get(self, url_builder, **kwargs):
        return self.request('get', url_builder, **kwargs)
 
    def post(self, url_builder, **kwargs):
        return self.request('post', url_builder, **kwargs)

    @FT.lru_cache(1)
    def webhookinfo(self):
        res = self.get(Api.webhookinfo)
        return WebhookInfo.from_(res)

    def updates(self):
        res = self.get(Api.updates)
        return Update.from_(res, many=True)

    def _chat_id(self, chat):
        assert isinstance(chat, (Chat, int))
        return chat.id if isinstance(chat, Chat) else chat

    def _remove_nones(self, data: dict = (), **kwargs):
        return {k: v for k, v in dict(data, **kwargs).items() if v is not None}

    def send_message(self, chat, text, 
                     parse_mode=None, disable_web_page_preview=None,
                     disable_notification=None,
                     reply_to_message_id=None,
                     reply_markup=None,
                     ):

        data = self._remove_nones(chat_id=self._chat_id(chat), text=text, 
                                  parse_mode=parse_mode and parse_mode.value,
                                  disable_web_page_preview=disable_web_page_preview,
                                  disable_notification=disable_notification,
                                  reply_to_message_id=reply_to_message_id,
                                  reply_markup=reply_markup,
                                  )
        res = self.post(Api.send_message, json=data)
        return Message.from_(res)

    def send_chat_action(self, chat: 'Chat', action: 'Chat.Action'):
        res = self.post(Api.send_chat_action, json=dict(chat_id=self._chat_id(chat), action=action.value))
        return res


@attr.s
class Chat(ConverterMixin):
    id = attr.ib()
    type = attr.ib()
    title = attr.ib(default=None)
    username = attr.ib(default=None)
    first_name = attr.ib(default=None)
    last_name = attr.ib(default=None)
    description = attr.ib(default=None)
    all_members_are_administrators = attr.ib(default=None)

    class Action(enum.Enum):
        TYPING = 'typing'  # typing for text messages
        UPLOAD_PHOTO = 'upload_photo'  # for photos
        RECORD_VIDEO = 'record_video'  # or 
        UPLOAD_VIDEO = 'upload_video'  # for videos
        RECORD_AUDIO = 'record_audio'  # or 
        UPLOAD_AUDIO = 'upload_audio'  # for audio files, 
        UPLOAD_DOCUMENT = 'upload_document'  # for general files, 
        FIND_LOCATION = 'find_location'  # for location data, 
        RECORD_VIDEO_NOTE = 'record_video_note'  # or 
        UPLOAD_VIDEO_NOTE = 'upload_video_note'  # for video notes.


@attr.s
class MessageEntity(ConverterMixin):
    type = attr.ib()
    offset = attr.ib()
    length = attr.ib()
    url = attr.ib(default=None)
    user = attr.ib(default=None)


@attr.s
class Message(ConverterMixin):
    converter_map = {'message_id': 'id', 'from': 'from_', }

    id = attr.ib()
    date = attr.ib()
    chat = attr.ib(converter=Chat.converter)
    text = attr.ib(default=None)
    from_ = attr.ib(default=None, converter=User.converter)
    entities = attr.ib(factory=list, converter=MessageEntity.list)

    class ParseMode(enum.Enum):
        MARKDOWN = 'Markdown'
        HTML = 'HTML'


@attr.s
class Update(ConverterMixin):
    converter_map = dict(update_id='id')

    id = attr.ib()
    message = attr.ib(default=None, converter=Message.converter)
    edited_message = attr.ib(default=None)
    channel_post = attr.ib(default=None)
    edited_channel_post = attr.ib(default=None)
    inline_query = attr.ib(default=None)
    chosen_inline_result = attr.ib(default=None)
    callback_query = attr.ib(default=None)
    shipping_query = attr.ib(default=None)
    pre_checkout_query= attr.ib(default=None)


def main():
    bot = Bot.by(BOT_API_TOKEN)

    webhookinfo = bot.webhookinfo()

    updates = bot.updates()

    u = updates[0]

    action_sent = bot.send_chat_action(u.message.chat, Chat.Action.TYPING)
    time.sleep(0.5)
    sent_message = bot.send_message(chat=u.message.chat, text='*lel* _kek_ `xd`', parse_mode=Message.ParseMode.MARKDOWN)
    print(sent_message


if __name__ == '__main__':
    main()
