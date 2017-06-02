import os
import re
import random
from urllib import parse as urlparse
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    TemplateSendMessage,
    ButtonsTemplate,
    PostbackTemplateAction,
    MessageTemplateAction,
    PostbackEvent,
)
from werkzeug.contrib.cache import SimpleCache

from quizzler import users
from quizzler import questions
from quizzler import im


store = SimpleCache(default_timeout=0)

line_bot_api = LineBotApi(os.environ.get('LINE_ACCESS_TOKEN'))
line_webhook_handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

ACTION = 'a'
QUESTION = 'q'
SELECT_TICKET = '0'
DO_ANSWER = '1'
CORRECTNESS = 'c'
TRUE = '1'
FALSE = '0'


def get_quizzler_user(user_id):
    try:
        return users.get_user(im_type='LINE', im_id=user_id)
    except users.UserDoesNotExist:
        return None


def get_message_for_next_question(user, event):
    question = user.get_next_question()
    users.set_current_question(
        question=question,
        im_type='LINE',
        im_id=event.source.user_id
    )

    buttons = [
        MessageTemplateAction(label=choice, text=f'您選擇了：{choice}')
        for choice in [question.answer, *question.wrong_choices]
    ]
    buttons.shuffle()

    return TemplateSendMessage(
        alt_text='Question',
        template=ButtonsTemplate(
            title='問題：',
            text=question.message,
            actions=buttons
        )
    )


@line_webhook_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user = get_quizzler_user(user_id)

    if '/login' == event.message.text.strip():
        if user is not None:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='無效：您已經註冊過了')
            )
            return
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(
                alt_text='Select ticket type',
                template=ButtonsTemplate(
                    title='請選擇票種',
                    text='請選擇您在 KKTIX 上註冊的票券的「活動名稱」：\n'
                         '「PyCon Taiwan 2017 _____ / 活動報名」',
                    actions=[
                        PostbackTemplateAction(
                            label=label,
                            text='KKTIX 活動：「PyCon Taiwan 2017 '
                                 f'{label} / 活動報名」',
                            data=f'{ACTION}={SELECT_TICKET}&ticket={ticket}',
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
            if user is not None:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text='無效：您已經註冊過了')
                )
                return
            else:
                user = users.add_user_im(ticket=ticket, serial=serial,
                                         im_type='LINE', im_id=user_id)
            store.delete_many(f'{user_id}.ticket', f'{user_id}.serial')
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text=f'註冊完成，開始遊戲！'),
                    get_message_for_next_question(user, event),
                ]
            )

        elif event.message.text.startswith('您選擇了：'):
            try:
                question = im.get_current_question(
                    im_type='LINE',
                    im_id=user_id
                )
            except im.CurrentQuestionDoesNotExist:
                return
            user_answer = event.message.text[len('您選擇了：'):]
            if user_answer not in [question.answer, *question.wrong_choices]:
                return
            is_correct = user_answer == question.answer
            user.save_answer(question, is_correct)
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text=f'答錯了 :('),
                    get_message_for_next_question(user, event),
                ]
            )


@line_webhook_handler.add(PostbackEvent)
def handle_postback_answer(event):
    user_id = event.source.user_id
    user = get_quizzler_user(user_id)
    data = dict(urlparse.parse_qsl(event.postback.data))
    if data.get(ACTION) == SELECT_TICKET:
        if user is not None:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='無效：您已經註冊過了')
            )
            return
        store.set(f'{user_id}.ticket', data.get('ticket'))
        store.set(f'{user_id}.serial', False)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的 KKTIX 報名序號')
        )
