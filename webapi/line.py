import os
from urllib import parse as urlparse
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    TemplateSendMessage,
    ButtonsTemplate,
    PostbackTemplateAction,
    PostbackEvent,
)
from werkzeug.contrib.cache import SimpleCache

from quizzler import users


store = SimpleCache(default_timeout=0)

line_bot_api = LineBotApi(os.environ.get("LINE_ACCESS_TOKEN"))
line_webhook_handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))

ACTION = "a"
SELECT_TICKET = "0"


@line_webhook_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id

    if '/login' == event.message.text.strip():
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(
                alt_text='Select ticket type',
                template=ButtonsTemplate(
                    title='請選擇票種',
                    text='請選擇您在 KKTIX 上註冊的票券的「活動名稱」：\n'
                         'PyCon Taiwan 2017 _____ / 活動報名',
                    actions=[
                        PostbackTemplateAction(
                            label=label,
                            text='KKTIX 活動：PyCon Taiwan 2017'
                                 f'{label} / 活動報名',
                            data=f'a=0&ticket={ticket}',
                        )
                        for ticket, label in [
                            ('REG', 'Registration'), ('INV', 'Invitation')
                        ]
                    ]
                )
            )
        )

    elif event.message.text.isdigit():
        ticket, serial = store.get_many(
            f'{user_id}.ticket',
            f'{user_id}.serial'
        )
        if ticket is not None and serial is False:
            serial = event.message.text
            try:
                users.get_user(im_type='LINE', im_id=user_id)
            except users.UserDoesNotExist:
                user = users.add_user_im(ticket=ticket, serial=serial,
                                         im_type='LINE', im_id=user_id)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text='您已經註冊過了')
                )
                return
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=user.serial)
            )
            store.delete_many(f'{user_id}.ticket', f'{user_id}.serial')


@line_webhook_handler.add(PostbackEvent)
def handle_postback_answer(event):
    user_id = event.source.user_id
    data = dict(urlparse.parse_qsl(event.postback.data))
    if data.get(ACTION) == SELECT_TICKET:
        store.set(f'{user_id}.ticket', data.get("ticket"))
        store.set(f'{user_id}.serial', False)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的 KKTIX 報名序號')
        )
