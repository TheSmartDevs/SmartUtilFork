# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev

import aiohttp
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient
from telethon.sessions import StringSession
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)
from telethon.errors import (
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError
)
from asyncio.exceptions import TimeoutError
import asyncio
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

logger = LOGGER

TIMEOUT_OTP = 600
TIMEOUT_2FA = 300

session_data = {}

def setup_string_handler(app: Client):
    @app.on_message(filters.command(["pyro", "tele"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def session_setup(client, message: Message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY)
            return

        if message.chat.type in (ChatType.SUPERGROUP, ChatType.GROUP):
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌ String Session Generator Only Works In Private Chats**",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        platform = "PyroGram" if message.command[0] == "pyro" else "Telethon"
        await handle_start(client, message, platform)

    @app.on_callback_query(filters.regex(r"^session_start_"))
    async def callback_query_start_handler(client, callback_query):
        user_id = callback_query.from_user.id if callback_query.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(callback_query.message.chat.id, BAN_REPLY)
            return

        await handle_callback_query(client, callback_query)

    @app.on_callback_query(filters.regex(r"^session_restart_"))
    async def callback_query_restart_handler(client, callback_query):
        user_id = callback_query.from_user.id if callback_query.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(callback_query.message.chat.id, BAN_REPLY)
            return

        await handle_callback_query(client, callback_query)

    @app.on_callback_query(filters.regex(r"^session_close$"))
    async def callback_query_close_handler(client, callback_query):
        user_id = callback_query.from_user.id if callback_query.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(callback_query.message.chat.id, BAN_REPLY)
            return

        await handle_callback_query(client, callback_query)

    @app.on_message(filters.text & filters.create(lambda _, __, message: message.chat.id in session_data))
    async def text_handler(client, message: Message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY)
            return

        await handle_text(client, message)

async def handle_start(client, message, platform):
    session_type = "Telethon" if platform == "Telethon" else "Pyrogram"
    session_data[message.chat.id] = {"type": session_type}
    await client.send_message(
        chat_id=message.chat.id,
        text=(
            f"**💥Welcome to the {session_type} session setup!**\n"
            "**━━━━━━━━━━━━━━━━━**\n"
            "**This is a totally safe session string generator. We don't save any info that you will provide, so this is completely safe.**\n\n"
            "**Note: Don't send OTP directly. Otherwise, your account could be banned, or you may not be able to log in.**"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Start", callback_data=f"session_start_{session_type.lower()}"),
            InlineKeyboardButton("Close", callback_data="session_close")
        ]]),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_callback_query(client, callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id

    if data == "session_close":
        platform = session_data.get(chat_id, {}).get("type", "").lower()
        if platform == "pyrogram":
            await callback_query.message.edit_text("**❌Cancelled. You can start by sending /pyro**", parse_mode=ParseMode.MARKDOWN)
        elif platform == "telethon":
            await callback_query.message.edit_text("**❌Cancelled. You can start by sending /tele**", parse_mode=ParseMode.MARKDOWN)
        if chat_id in session_data:
            del session_data[chat_id]
        return

    if data.startswith("session_start_"):
        session_type = data.split('_')[2]
        await callback_query.message.edit_text(
            "**Send Your API ID**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Restart", callback_data=f"session_restart_{session_type}"),
                InlineKeyboardButton("Close", callback_data="session_close")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )
        session_data[chat_id]["stage"] = "api_id"

    if data.startswith("session_restart_"):
        session_type = data.split('_')[2]
        await handle_start(client, callback_query.message, platform=session_type.capitalize())

async def handle_text(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in session_data:
        return

    session = session_data[chat_id]
    stage = session.get("stage")

    if stage == "api_id":
        try:
            api_id = int(message.text)
            session["api_id"] = api_id
            await client.send_message(
                chat_id=message.chat.id,
                text="**Send Your API Hash**",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"),
                    InlineKeyboardButton("Close", callback_data="session_close")
                ]]),
                parse_mode=ParseMode.MARKDOWN 
            )
            session["stage"] = "api_hash"
        except ValueError:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌Invalid API ID. Please enter a valid integer.**"
            )
            logger.error(f"Invalid API ID provided by user {message.from_user.id}")

    elif stage == "api_hash":
        session["api_hash"] = message.text
        await client.send_message(
            chat_id=message.chat.id,
            text="** Send Your Phone Number\n[Example: +880xxxxxxxxxx] **",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"),
                InlineKeyboardButton("Close", callback_data="session_close")
            ]]),
            parse_mode=ParseMode.MARKDOWN 
        )
        session["stage"] = "phone_number"

    elif stage == "phone_number":
        session["phone_number"] = message.text
        otp_message = await client.send_message(
            chat_id=message.chat.id,
            text="**💥Sending OTP Check PM.....**"
        )
        await send_otp(client, message, otp_message)

    elif stage == "otp":
        otp = ''.join([char for char in message.text if char.isdigit()])
        session["otp"] = otp
        otp_message = await client.send_message(
            chat_id=message.chat.id,
            text="**💥Validating Your Inputed OTP.....**"
        )
        await validate_otp(client, message, otp_message)

    elif stage == "2fa":
        session["password"] = message.text
        await validate_2fa(client, message)

async def send_otp(client, message, otp_message):
    session = session_data[message.chat.id]
    api_id = session["api_id"]
    api_hash = session["api_hash"]
    phone_number = session["phone_number"]
    telethon = session["type"] == "Telethon"

    if telethon:
        client_obj = TelegramClient(StringSession(), api_id, api_hash)
    else:
        client_obj = Client(":memory:", api_id, api_hash)

    await client_obj.connect()

    try:
        if telethon:
            code = await client_obj.send_code_request(phone_number)
        else:
            code = await client_obj.send_code(phone_number)
        session["client_obj"] = client_obj
        session["code"] = code
        session["stage"] = "otp"
        
        asyncio.create_task(handle_otp_timeout(client, message))

        await client.send_message(
            chat_id=message.chat.id,
            text="**✅Send The OTP as text. Please send a text message embedding the OTP like: 'AB5 CD0 EF3 GH7 IJ6'**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"),
                InlineKeyboardButton("Close", callback_data="session_close")
            ]]),
            parse_mode=ParseMode.MARKDOWN 
        )
        await otp_message.delete()
    except (ApiIdInvalid, ApiIdInvalidError):
        await client.send_message(
            chat_id=message.chat.id,
            text='**❌ `API_ID` and `API_HASH` combination is invalid**',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"), InlineKeyboardButton("Close", callback_data="session_close")]
            ])
        )
        await otp_message.delete()
        logger.error(f"Invalid API_ID/API_HASH for user {message.from_user.id}")
        return
    except (PhoneNumberInvalid, PhoneNumberInvalidError):
        await client.send_message(
            chat_id=message.chat.id,
            text='**❌`PHONE_NUMBER` is invalid.**',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"), InlineKeyboardButton("Close", callback_data="session_close")]
            ])
        )
        await otp_message.delete()
        logger.error(f"Invalid phone number for user {message.from_user.id}")
        return

async def handle_otp_timeout(client, message):
    await asyncio.sleep(TIMEOUT_OTP)
    if message.chat.id in session_data and session_data[message.chat.id].get("stage") == "otp":
        await client.send_message(
            chat_id=message.chat.id,
            text="**❌ Bro Your OTP Has Expired**",
            parse_mode=ParseMode.MARKDOWN
        )
        del session_data[message.chat.id]
        logger.info(f"OTP timed out for user {message.from_user.id}")

async def validate_otp(client, message, otp_message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    phone_number = session["phone_number"]
    otp = session["otp"]
    code = session["code"]
    telethon = session["type"] == "Telethon"

    try:
        if telethon:
            await client_obj.sign_in(phone_number, otp)
        else:
            await client_obj.sign_in(phone_number, code.phone_code_hash, otp)
        await generate_session(client, message)
        await otp_message.delete()
    except (PhoneCodeInvalid, PhoneCodeInvalidError):
        await client.send_message(
            chat_id=message.chat.id,
            text='**❌Bro Your OTP Is Wrong**',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"), InlineKeyboardButton("Close", callback_data="session_close")]
            ])
        )
        await otp_message.delete()
        logger.error(f"Invalid OTP provided by user {message.from_user.id}")
        return
    except (PhoneCodeExpired, PhoneCodeExpiredError):
        await client.send_message(
            chat_id=message.chat.id,
            text='**❌Bro OTP Has expired**',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"), InlineKeyboardButton("Close", callback_data="session_close")]
            ])
        )
        await otp_message.delete()
        logger.error(f"Expired OTP for user {message.from_user.id}")
        return
    except (SessionPasswordNeeded, SessionPasswordNeededError):
        session["stage"] = "2fa"
        
        asyncio.create_task(handle_2fa_timeout(client, message))
        
        await client.send_message(
            chat_id=message.chat.id,
            text="**❌ 2FA Is Required To Login. Please Enter 2FA**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"),
                InlineKeyboardButton("Close", callback_data="session_close")
            ]]),
            parse_mode=ParseMode.MARKDOWN 
        )
        await otp_message.delete()
        logger.info(f"2FA required for user {message.from_user.id}")

async def handle_2fa_timeout(client, message):
    await asyncio.sleep(TIMEOUT_2FA)
    if message.chat.id in session_data and session_data[message.chat.id].get("stage") == "2fa":
        await client.send_message(
            chat_id=message.chat.id,
            text="**❌ Bro Your 2FA Input Has Expired**",
            parse_mode=ParseMode.MARKDOWN
        )
        del session_data[message.chat.id]
        logger.info(f"2FA timed out for user {message.from_user.id}")

async def validate_2fa(client, message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    password = session["password"]
    telethon = session["type"] == "Telethon"

    try:
        if telethon:
            await client_obj.sign_in(password=password)
        else:
            await client_obj.check_password(password=password)
        await generate_session(client, message)
    except (PasswordHashInvalid, PasswordHashInvalidError):
        await client.send_message(
            chat_id=message.chat.id,
            text='**❌Invalid Password Provided**',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Restart", callback_data=f"session_restart_{session['type'].lower()}"), InlineKeyboardButton("Close", callback_data="session_close")]
            ])
        )
        logger.error(f"Invalid 2FA password provided by user {message.from_user.id}")
        return

async def generate_session(client, message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    telethon = session["type"] == "Telethon"

    if telethon:
        string_session = client_obj.session.save()
    else:
        string_session = await client_obj.export_session_string()

    text = f"**{session['type'].upper()} SESSION FROM Smart Tool**:\n\n`{string_session}`\n\nGenerated by @ItsSmartToolBot"

    try:
        await client_obj.send_message("me", text)
    except KeyError:
        logger.error(f"Failed to send session string to saved messages for user {message.from_user.id}")
        pass

    await client_obj.disconnect()
    await client.send_message(
        chat_id=message.chat.id,
        text="**This string has been saved ✅ in your Saved Messages**",
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"Session string generated successfully for user {message.from_user.id}")
    del session_data[message.chat.id]
