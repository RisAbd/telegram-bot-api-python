#!/usr/bin/env python3

import requests
from decouple import config
import attr
import functools as FT, itertools as IT, typing as T, operator as OP
import enum
import time
from datetime import datetime

import logging

logger = logging.getLogger(__name__)


# UTILS

def _from(cls, result: T.Union[list, dict], many=False, **kwargs):
    converter_map = getattr(cls, 'converter_map', {})
    # logger.debug('cls=%r, many=%r: %r', cls, many, result)
    if many:
        return list(map(FT.partial(cls.from_, many=False), result))
    return cls(**{converter_map.get(k, k): v for k, v in result.items() if converter_map.get(k) is not False}, **kwargs)


def from_added(cls):
    cls.from_ = cls.converter = classmethod(_from)
    cls.list = classmethod(FT.partial(_from, many=True))
    return cls


@from_added
class ConverterMixin:
    pass


class Api:
    HOST = 'https://api.telegram.org'
    BOT = '/bot{token}'

    ME = '/getMe'
    UPDATES = '/getUpdates'
    WEBHOOK_INFO = '/getWebhookInfo'
    SEND_MESSAGE = '/sendMessage'
    SEND_CHAT_ACTION = '/sendChatAction'
    SEND_DOCUMENT = '/sendDocument'

    def _api(api):
        return classmethod(lambda cls, token: cls.HOST + cls.BOT.format(token=token) + api)

    me = _api(ME)
    updates = _api(UPDATES)
    webhookinfo = _api(WEBHOOK_INFO)
    send_message = _api(SEND_MESSAGE)
    send_chat_action = _api(SEND_CHAT_ACTION)
    send_document = _api(SEND_DOCUMENT)


class BaseAPIException(BaseException):
    pass


class APIException(BaseAPIException):
    pass


@attr.s
class Error(ConverterMixin):
    converter_map = dict(ok=False)

    description = attr.ib()
    error_code = attr.ib()
    parameters = attr.ib(default=None)

    def raise_(self):
        raise APIException(self)


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
        logger.debug('%r', r)
        j = r.json()
        logger.debug('%r', j)
        if not j['ok']:
            Error.from_(j).raise_()
        return j['result']

    def get(self, url_builder, **kwargs):
        return self.request('get', url_builder, **kwargs)
 
    def post(self, url_builder, **kwargs):
        return self.request('post', url_builder, **kwargs)

    def _prepare_value(self, value: T.Any, 
                       remove_none_values=True, 
                       transform_types_to_ids: T.Dict[type, str] = None,
                       values_instead_of_enums=True,
                       update_type_to_id_with_inc=True,
                       _depth=0,
                       _max_depth=None,
                       _raise_recursion_error=False,
                       ) -> dict:

        if transform_types_to_ids is None:
            transform_types_to_ids = {Update: 'id', Message: 'id', Chat: 'id', User: 'id', Bot: 'id', Document: 'file_id'}

        if _depth >= (_max_depth or float('inf')):
            if _raise_recursion_error:
                raise RecursionError()
            else:
                return value

        vtype = type(value)

        if isinstance(value, Update) and update_type_to_id_with_inc:
            return value.id + 1
        elif isinstance(value, enum.Enum) and values_instead_of_enums:
            return value.value
        elif vtype in transform_types_to_ids:
            return getattr(value, transform_types_to_ids[vtype])
        elif isinstance(value, (list, tuple)):
            return [
                self._prepare_value(v, remove_none_values=remove_none_values, 
                                    transform_types_to_ids=transform_types_to_ids,
                                    values_instead_of_enums=values_instead_of_enums,
                                    _depth=_depth+1,
                                    _max_depth=_max_depth,
                                    _raise_recursion_error=_raise_recursion_error,
                                    ) 
                for v in value if v is not None
            ]
        elif isinstance(value, dict):
            return {
                k: self._prepare_value(v, remove_none_values=remove_none_values, 
                                       transform_types_to_ids=transform_types_to_ids,
                                       values_instead_of_enums=values_instead_of_enums,
                                       _depth=_depth+1,
                                       _max_depth=_max_depth,
                                       _raise_recursion_error=_raise_recursion_error,
                                       )
                for k, v in value.items() if remove_none_values and v is not None
            }
        else:
            return value

    @FT.lru_cache(1)
    def webhookinfo(self) -> 'WebhookInfo':
        res = self.get(Api.webhookinfo)
        return WebhookInfo.from_(res)

    def updates(self, after: 'Update' = None, 
                limit: int = None, 
                timeout: int = None, 
                allowed_updates: T.List[T.Union[str, 'Update.Type']] = None,
                offset: int = None,  # raw telegram offset see /getUpdates docs
                ) -> T.List['Update']:
        data = self._prepare_value(dict(offset=offset or after, limit=limit, timeout=timeout, allowed_updates=allowed_updates))

        res = self.get(Api.updates, json=data)
        return Update.from_(res, many=True)
    
    def send_message(self, chat: T.Union['Chat', int], text, 
                     parse_mode=None, disable_web_page_preview=None,
                     disable_notification=None,
                     reply_to_message=None,
                     reply_markup=None,
                     ) -> 'Message':

        data = self._prepare_value(dict(chat_id=chat, text=text, 
                                        parse_mode=parse_mode,
                                        disable_web_page_preview=disable_web_page_preview,
                                        disable_notification=disable_notification,
                                        reply_to_message_id=reply_to_message,
                                        reply_markup=reply_markup,
                                        ))
        res = self.post(Api.send_message, json=data)
        return Message.from_(res)

    def send_chat_action(self, chat: T.Union['Chat', int], action: 'Chat.Action') -> bool:
        return self.post(Api.send_chat_action, json=self._prepare_value(dict(chat_id=chat, action=action)))

    def send_document(self, chat: T.Union['Chat', int], document, 
                      caption=None, thumb=None, 
                      parse_mode=None, disable_web_page_preview=None,
                      disable_notification=None,
                      reply_to_message=None,
                      reply_markup=None,
                      ) -> 'Message':

        data = self._prepare_value(dict(chat_id=chat, caption=caption,
                                        parse_mode=parse_mode and parse_mode.value,
                                        disable_web_page_preview=disable_web_page_preview,
                                        disable_notification=disable_notification,
                                        reply_to_message_id=reply_to_message,
                                        reply_markup=reply_markup,
                                        ))
        files = None
        if isinstance(document, str):
            data['document'] = document
        else:
            files = dict(document=document)

        res = self.post(Api.send_document, data=data, files=files)
        return Message.from_(res) 


@attr.s
class PhotoSize(ConverterMixin):
    file_id = attr.ib()
    width = attr.ib()
    height = attr.ib()
    file_size = attr.ib(default=None)

Thumb = PhotoSize


@attr.s
class Document(ConverterMixin):
    file_id = attr.ib()
    thumb = attr.ib(default=None, converter=attr.converters.optional(Thumb.converter))
    file_name = attr.ib(default=None)
    mime_type = attr.ib(default=None)
    file_size = attr.ib(default=None)


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
class Location(ConverterMixin):
    latitude = attr.ib()
    longitude = attr.ib()


class Message(ConverterMixin):
    converter_map = {'message_id': 'id', 'from': 'from_', }

    id = attr.ib()
    date = attr.ib(converter=datetime.fromtimestamp)
    chat = attr.ib(converter=Chat.converter)
    text = attr.ib(default=None)
    edit_date = attr.ib(default=None, converter=attr.converters.optional(datetime.fromtimestamp))
    from_ = attr.ib(default=None, converter=attr.converters.optional(User.converter))
    entities = attr.ib(factory=list, converter=MessageEntity.list)
    
    caption = attr.ib(default=None)
    caption_entities = attr.ib(factory=list, converter=MessageEntity.list)

    document = attr.ib(default=None, converter=attr.converters.optional(Document.converter))

    location = attr.ib(default=None, converter=attr.converters.optional(Location.converter))

    class ParseMode(enum.Enum):
        MARKDOWN = 'Markdown'
        HTML = 'HTML'

# workaround self referencing converter
# reply_to_message is Message
Message.reply_to_message = attr.ib(default=None, converter=attr.converters.optional(Message.converter))
Message = attr.s(Message)


@attr.s
class Update(ConverterMixin):
    converter_map = dict(update_id='id')

    id = attr.ib()
    message = attr.ib(default=None, converter=attr.converters.optional(Message.converter))
    edited_message = attr.ib(default=None, converter=attr.converters.optional(Message.converter))
    channel_post = attr.ib(default=None)
    edited_channel_post = attr.ib(default=None)
    inline_query = attr.ib(default=None)
    chosen_inline_result = attr.ib(default=None)
    callback_query = attr.ib(default=None)
    shipping_query = attr.ib(default=None)
    pre_checkout_query= attr.ib(default=None)

    class Type(enum.Enum):

        MESSAGE = 'message'
        EDITED_MESSAGE = 'edited_message'
        CHANNEL_POST = 'channel_post'
        EDITED_CHANNEL_POST = 'edited_channel_post'
        INLINE_QUERY = 'inline_query'
        CHOSEN_INLINE_RESULT = 'chosen_inline_result'
        CALLBACK_QUERY = 'callback_query'
        SHIPPING_QUERY = 'shipping_query'
        PRE_CHECKOUT_QUERY = 'pre_checkout_query'

    @property
    def type(self) -> Type:
        for t in self.Type:
            if getattr(self, t.value) is not None:
                return t
        assert False, 'kek'


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
    LOGLEVEL = config('LOGLEVEL', cast=str, default='INFO')

    logger.level = getattr(logging, LOGLEVEL, logging.INFO)
    logging.basicConfig()

    bot = Bot.by(BOT_API_TOKEN)

    test(bot)

    webhookinfo = bot.webhookinfo()

    updates = bot.updates()

    for u in updates:
        print(u)
        print(u.type)

    updates = bot.updates(after=locals().get('u'))
    assert updates == []

    # action_sent = bot.send_chat_action(u.message.chat, Chat.Action.TYPING)
    # time.sleep(0.5)

    # sent_message = bot.send_message(chat=u.message.chat, text='*lel* _kek_ `xd`', parse_mode=Message.ParseMode.MARKDOWN)
    # print(sent_message)

    # # import io
    # # with io.BytesIO(b'some content file') as f: 
    # #     f.name = 'kek.txt'

    # message_with_doc = bot.send_document(chat=u.message.chat, document='BQADAgAD4QIAAobqmUmE8Yh3E-vvMgI', 
    #                                      caption='hey see my _*document*_ here',
    #                                      parse_mode=Message.ParseMode.MARKDOWN,
    #                                      reply_to_message=u.message,
    #                                      )

    # print(message_with_doc)


if __name__ == '__main__':
    main()
