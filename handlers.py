import time
import asyncio
from aiogram import F, Bot, Router, types
from aiogram.filters import ChatMemberUpdatedFilter, MEMBER, JOIN_TRANSITION
from aiogram.types import ChatMemberUpdated
from constants import (CORRECT_ANSWER_PREFIX, WRONG_ANSWER_PREFIX, DICE_SEND_MSG,
                       CORRECT_ANSWER_MSG, WRONG_USER_MSG, WRONG_ANSWER_MSG, BAN_TIMEOUT, ANSWER_TIMEOUT)
from utils import get_callback_user_info, get_dice_keyboard, get_dice_value, set_permissions_to

router = Router()

# Словарь для хранения таймеров
user_timers = {}

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def new_member_handler(event: ChatMemberUpdated, bot: Bot):
    user_id = event.new_chat_member.user.id
    chat_id = event.chat.id

    await set_permissions_to(user_id=user_id, chat_id=chat_id, permissions=False, bot=bot)

    dice_msg = await get_dice_value(chat_id=chat_id, bot=bot)
    keyboard = get_dice_keyboard(dice_value=dice_msg.dice.value, user_id=user_id)

    sent_message = await bot.send_message(
        chat_id,
        DICE_SEND_MSG,
        reply_markup=keyboard.as_markup(),
    )

    # Создаем и запускаем таймер
    timer = asyncio.create_task(handle_timeout(bot, chat_id, user_id, dice_msg.message_id, sent_message.message_id))
    user_timers[user_id] = timer

async def handle_timeout(bot: Bot, chat_id: int, user_id: int, dice_message_id: int, question_message_id: int):
    await asyncio.sleep(ANSWER_TIMEOUT)
    if user_id in user_timers:
        del user_timers[user_id]
        await bot.delete_message(chat_id, dice_message_id)
        await bot.delete_message(chat_id, question_message_id)
        
        # Отправляем личное сообщение пользователю
        try:
            await bot.send_message(user_id, f"Вы не ответили вовремя. {WRONG_ANSWER_MSG}")
        except Exception:
            # Если не удалось отправить личное сообщение, игнорируем ошибку
            pass

        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            until_date=int(time.time() + BAN_TIMEOUT)
        )
        await asyncio.sleep(BAN_TIMEOUT)
        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)

@router.callback_query(F.data.startswith(CORRECT_ANSWER_PREFIX))
async def correct_answer_handler(callback: types.CallbackQuery, bot: Bot):
    user_id, is_target_user, chat_id = get_callback_user_info(
        callback=callback, prefix=CORRECT_ANSWER_PREFIX)

    if is_target_user:
        # Отменяем таймер
        if user_id in user_timers:
            user_timers[user_id].cancel()
            del user_timers[user_id]

        await set_permissions_to(user_id=user_id, chat_id=chat_id, permissions=True, bot=bot)
        await callback.answer(CORRECT_ANSWER_MSG)
        await callback.message.delete()
        await bot.delete_message(chat_id, callback.message.message_id - 1)
    else:
        await callback.answer(WRONG_USER_MSG, show_alert=True)

@router.callback_query(F.data.startswith(WRONG_ANSWER_PREFIX))
async def wrong_answer_handler(callback: types.CallbackQuery, bot: Bot):
    user_id, is_target_user, chat_id = get_callback_user_info(
        callback=callback, prefix=WRONG_ANSWER_PREFIX)

    if is_target_user:
        # Отменяем таймер
        if user_id in user_timers:
            user_timers[user_id].cancel()
            del user_timers[user_id]

        await callback.answer(WRONG_ANSWER_MSG, show_alert=True)

        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            until_date=int(time.time() + BAN_TIMEOUT)
        )
        
        await callback.message.delete()
        await bot.delete_message(chat_id, callback.message.message_id - 1)
        
        await asyncio.sleep(BAN_TIMEOUT)
        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
    else:
        await callback.answer(WRONG_USER_MSG, show_alert=True)