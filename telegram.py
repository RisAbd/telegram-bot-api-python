#!/usr/bin/env python3

import sys, os
import requests
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
    SET_WEBHOOK = '/setWebhook'
    DELETE_WEBHOOK = '/deleteWebhook'
    SEND_MESSAGE = '/sendMessage'
    SEND_CHAT_ACTION = '/sendChatAction'
    SEND_DOCUMENT = '/sendDocument'
    GET_FILE = '/getFile'


    _api = lambda api: classmethod(lambda cls, token: cls.HOST + cls.BOT.format(token=token) + api)

    me = _api(ME)
    updates = _api(UPDATES)
    webhookinfo = _api(WEBHOOK_INFO)
    send_message = _api(SEND_MESSAGE)
    send_chat_action = _api(SEND_CHAT_ACTION)
    send_document = _api(SEND_DOCUMENT)

    set_webhook = _api(SET_WEBHOOK)
    delete_webhook = _api(DELETE_WEBHOOK)

    get_file = _api(GET_FILE)

    file_by_file_path = classmethod(lambda cls, file_path: lambda token: '{}/file{}{}'.format(cls.HOST, cls.BOT.format(token=token), '/'+file_path))


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
    allowed_updates = attr.ib(default=None, converter=attr.converters.optional(lambda x: list(map(Update.Type, x))))

    @property
    def is_set_up(self) -> bool:
        return bool(self.url)

    def __bool__(self):
        return self.is_set_up
    

@attr.s
class User(ConverterMixin):
    id = attr.ib(hash=True)
    is_bot = attr.ib(hash=True)
    first_name = attr.ib()
    last_name = attr.ib(default=None)
    username = attr.ib(default=None)
    language_code = attr.ib(default=None)


class _AsWebhookResponse(Exception):
    def __init__(self, data):
        self._data = data
    def data(self, with_method_name):
        d = self._data
        d['method'] = with_method_name
        return d


def webhook_responsible(method):
    method = method.lstrip('/')
    def wow(f):
        @FT.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except _AsWebhookResponse as e:
                return e.data(method)
        return wrapper
    return wow


@attr.s(frozen=True)
class Bot(User):
    _api_token = attr.ib(repr=False, kw_only=True)

    @classmethod
    def by(cls, token) -> 'Bot':
        r = requests.get(Api.me(token), ).json()['result']
        return Bot.from_(r, api_token=token)

    def request(self, method, url_builder, _verbose=False, _raw_return=False, **kwargs):
        url = url_builder(token=self._api_token)
        logger.debug('%s: %r', method, url)
        r = requests.request(method, url, **kwargs)
        logger.debug('%r', r)
        if _raw_return:
            return r
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
            transform_types_to_ids = {Update: 'id', Message: 'id', Chat: 'id', User: 'id', Bot: 'id', 
                                      Document: 'file_id', Audio: 'file_id', File: 'file_id',
                                      }

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

    def webhookinfo(self) -> 'WebhookInfo':
        res = self.get(Api.webhookinfo)
        return WebhookInfo.from_(res)

    def set_webhook(self, url: str, certificate=None, max_connections: int = None, allowed_updates: list = None) -> bool:   
        if allowed_updates in ('all', None):
            allowed_updates = []
        data = self._prepare_value(dict(url=url, max_connections=max_connections, allowed_updates=allowed_updates))
        if certificate is not None:
            files = dict(certificate=certificate)
        else:
            files = None
        return self.post(Api.set_webhook, data=data, files=files)

    def delete_webhook(self) -> bool:
        return self.post(Api.delete_webhook)

    def updates(self, after: 'Update' = None, 
                limit: int = None, 
                timeout: int = None, 
                allowed_updates: T.List[T.Union[str, 'Update.Type']] = None,
                offset: int = None,  # raw telegram offset see /getUpdates docs
                ) -> T.List['Update']:
        data = self._prepare_value(dict(offset=offset or after, limit=limit, timeout=timeout, allowed_updates=allowed_updates))

        res = self.get(Api.updates, json=data)
        return Update.from_(res, many=True)
    
    @webhook_responsible(Api.SEND_MESSAGE)
    def send_message(self, chat: T.Union['Chat', int], text, 
                     parse_mode=None, disable_web_page_preview=None,
                     disable_notification=None,
                     reply_to_message=None,
                     reply_markup=None,
                     as_webhook_response=False,
                     ) -> 'Message':

        data = self._prepare_value(dict(chat_id=chat, text=text, 
                                        parse_mode=parse_mode,
                                        disable_web_page_preview=disable_web_page_preview,
                                        disable_notification=disable_notification,
                                        reply_to_message_id=reply_to_message,
                                        reply_markup=reply_markup,
                                        ))
        if as_webhook_response:
            raise _AsWebhookResponse(data)

        res = self.post(Api.send_message, json=data)
        return Message.from_(res)

    @webhook_responsible(Api.SEND_CHAT_ACTION)
    def send_chat_action(self, chat: T.Union['Chat', int], action: 'Chat.Action', as_webhook_response=False) -> bool:
        data = json=self._prepare_value(dict(chat_id=chat, action=action))
        if as_webhook_response:
            raise _AsWebhookResponse(data)
        return self.post(Api.send_chat_action, json=data)

    @webhook_responsible(Api.SEND_DOCUMENT)
    def send_document(self, chat: T.Union['Chat', int], document, 
                      caption=None, thumb=None, 
                      parse_mode=None, disable_web_page_preview=None,
                      disable_notification=None,
                      reply_to_message=None,
                      reply_markup=None,
                      as_webhook_response=False, 
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
        
        if as_webhook_response:
            if files:
                raise RuntimeError('can not reply with file response')
            raise _AsWebhookResponse(data)

        res = self.post(Api.send_document, data=data, files=files)
        return Message.from_(res)

    def file(self, file_id):
        res = self.get(Api.get_file, params=dict(file_id=file_id))
        file = File.from_(res)
        return self.get(Api.file_by_file_path(file.file_path), _raw_return=True).content


@attr.s
class File(ConverterMixin):
    file_id = attr.ib()
    file_size = attr.ib(default=None)
    file_path = attr.ib(default=None)


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
class Audio(ConverterMixin):
    file_id = attr.ib()
    duration = attr.ib()
    performer = attr.ib(default=None)
    title = attr.ib(default=None)
    thumb = attr.ib(default=None, converter=attr.converters.optional(Thumb.converter))
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

    def text(self, message: T.Union[str, 'Message']) -> str:
        if isinstance(message, Message):
            return message.text[self.offset:self.offset+self.length]
        else:
            return message[self.offset:self.offset+self.length]


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

    audio = attr.ib(default=None, converter=attr.converters.optional(Audio.converter))

    class ParseMode(enum.Enum):
        MARKDOWN = 'Markdown'
        HTML = 'HTML'
    
    @property
    def bot_command(self) -> T.Optional[str]:
        for e in self.entities:
            if e.offset == 0 and e.type == 'bot_command':
                return e.text(self.text)


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
