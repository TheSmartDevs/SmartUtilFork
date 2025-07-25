# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev

import re
import time
import asyncio
import random
import string
import hashlib
import aiohttp
from bs4 import BeautifulSoup
from pyrogram.enums import ParseMode, ChatType
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

user_data = {}
token_map = {}
user_tokens = {}
MAX_MESSAGE_LENGTH = 4000

BASE_URL = "https://api.mail.tm"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def short_id_generator(email):
    unique_string = email + str(time.time())
    return hashlib.md5(unique_string.encode()).hexdigest()[:10]

def generate_random_username(length=8):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

async def get_domain():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/domains", headers=HEADERS) as response:
                data = await response.json()
                if isinstance(data, list) and data:
                    return data[0]['domain']
                elif 'hydra:member' in data and data['hydra:member']:
                    return data['hydra:member'][0]['domain']
    except Exception as e:
        LOGGER.error(f"Error fetching domain: {e}")
    return None

async def create_account(email, password):
    data = {
        "address": email,
        "password": password
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/accounts", headers=HEADERS, json=data) as response:
                if response.status in [200, 201]:
                    return await response.json()
                else:
                    LOGGER.error(f"Error Code: {response.status} Response: {await response.text()}")
                    return None
    except Exception as e:
        LOGGER.error(f"Error in create_account: {e}")
        return None

async def get_token(email, password):
    data = {
        "address": email,
        "password": password
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/token", headers=HEADERS, json=data) as response:
                if response.status == 200:
                    return (await response.json()).get('token')
                else:
                    LOGGER.error(f"Token Error Code: {response.status} Token Response: {await response.text()}")
                    return None
    except Exception as e:
        LOGGER.error(f"Error in get_token: {e}")
        return None

def get_text_from_html(html_content_list):
    html_content = ''.join(html_content_list)
    soup = BeautifulSoup(html_content, 'html.parser')

    for a_tag in soup.find_all('a', href=True):
        url = a_tag['href']
        new_content = f"{a_tag.text} [{url}]"
        a_tag.string = new_content

    text_content = soup.get_text()
    cleaned_content = re.sub(r'\s+', ' ', text_content).strip()
    return cleaned_content

async def list_messages(token):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/messages", headers=headers) as response:
                data = await response.json()
                if isinstance(data, list):
                    return data
                elif 'hydra:member' in data:
                    return data['hydra:member']
                else:
                    return []
    except Exception as e:
        LOGGER.error(f"Error in list_messages: {e}")
        return []

def setup_tmail_handler(app: Client):
    @app.on_message(filters.command(["tmail"], prefixes=COMMAND_PREFIX))
    async def generate_mail(client, message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(
                chat_id=message.chat.id,
                text=BAN_REPLY
            )
            return

        if message.chat.type != ChatType.PRIVATE:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌ Bro Tempmail Feature Only Works In Private**"
            )
            return

        loading_msg = await client.send_message(
            chat_id=message.chat.id,
            text="**Generating Temporary Mail...**"
        )

        args_text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        args = args_text.split()
        if len(args) == 1 and ':' in args[0]:
            username, password = args[0].split(':')
        else:
            username = generate_random_username()
            password = generate_random_password()

        domain = await get_domain()
        if not domain:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌TempMail API Dead Bro**"
            )
            await client.delete_messages(message.chat.id, [loading_msg.message_id])
            return

        email = f"{username}@{domain}"
        account = await create_account(email, password)
        if not account:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌Username already taken. Choose another one.**"
            )
            await client.delete_messages(message.chat.id, [loading_msg.message_id])
            return

        await asyncio.sleep(2)

        token = await get_token(email, password)
        if not token:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌Failed to retrieve token**"
            )
            await client.delete_messages(message.chat.id, [loading_msg.message_id])
            return

        short_id = short_id_generator(email)
        token_map[short_id] = token

        output_message = (
            "**📧 SmartTools-Email Details 📧**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"**📧 Email:** `{email}`\n"
            f"**🔑 Password:** `{password}`\n"
            f"**🔒 Token:** `{token}`\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "**Note: Keep the token to Access Mail**"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("Incoming Emails", callback_data=f"check_{short_id}")]])

        await client.send_message(
            chat_id=message.chat.id,
            text=output_message,
            reply_markup=keyboard
        )
        await client.delete_messages(message.chat.id, [loading_msg.id])

    @app.on_callback_query(filters.regex(r'^check_'))
    async def check_mail(client, callback_query):
        user_id = callback_query.from_user.id if callback_query.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await callback_query.answer("✘Sorry You're Banned From Using Me↯", show_alert=True)
            return

        short_id = callback_query.data.split('_')[1]
        token = token_map.get(short_id)
        if not token:
            await client.send_message(
                chat_id=callback_query.message.chat.id,
                text="**❌Session expired, Please use .cmail or /cmail with your token.**"
            )
            return

        user_tokens[callback_query.from_user.id] = token
        
        messages = await list_messages(token)
        if not messages:
            await callback_query.answer("No messages received ❌", show_alert=True)
            return

        loading_msg = await client.send_message(
            chat_id=callback_query.message.chat.id,
            text="**Checking Mails.. Please wait..**"
        )

        output = "**📧 Your SmartTools-Mail Messages 📧**\n"
        output += "**━━━━━━━━━━━━━━━━━━**\n"
        
        buttons = []
        for idx, msg in enumerate(messages[:10], 1):
            output += f"{idx}. From: `{msg['from']['address']}` - Subject: {msg['subject']}\n"
            button = InlineKeyboardButton(f"{idx}", callback_data=f"read_{msg['id']}")
            buttons.append(button)
        
        keyboard = []
        for i in range(0, len(buttons), 5):
            keyboard.append(buttons[i:i+5])

        await client.send_message(
            chat_id=callback_query.message.chat.id,
            text=output,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await client.delete_messages(callback_query.message.chat.id, [loading_msg.id])

    @app.on_callback_query(filters.regex(r"^close_message"))
    async def close_message(client, callback_query):
        await callback_query.message.delete()

    @app.on_callback_query(filters.regex(r"^read_"))
    async def read_message(client, callback_query):
        user_id = callback_query.from_user.id if callback_query.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await callback_query.answer("✘Sorry You're Banned From Using Me↯", show_alert=True)
            return

        message_id = callback_query.data.split('_')[1]
        token = user_tokens.get(callback_query.from_user.id)

        if not token:
            await client.send_message(
                chat_id=callback_query.message.chat.id,
                text="**❌Token not found. Please use .cmail or /cmail with your token again**"
            )
            return

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BASE_URL}/messages/{message_id}", headers=headers) as response:
                    if response.status == 200:
                        details = await response.json()
                        if 'html' in details:
                            message_text = get_text_from_html(details['html'])
                        elif 'text' in details:
                            message_text = details['text']
                        else:
                            message_text = "Content not available."
                        
                        if len(message_text) > MAX_MESSAGE_LENGTH:
                            message_text = message_text[:MAX_MESSAGE_LENGTH - 100] + "... [message truncated]"

                        output = f"**From:** `{details['from']['address']}`\n**Subject:** `{details['subject']}`\n━━━━━━━━━━━━━━━━━━\n{message_text}"

                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("Close", callback_data="close_message")]
                        ])

                        await client.send_message(
                            chat_id=callback_query.message.chat.id,
                            text=output,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
                    else:
                        await client.send_message(
                            chat_id=callback_query.message.chat.id,
                            text="**❌ Error retrieving message details**"
                        )
        except Exception as e:
            LOGGER.error(f"Error in read_message: {e}")
            await notify_admin(client, "/cmail read", e, callback_query.message)
            await client.send_message(
                chat_id=callback_query.message.chat.id,
                text="**❌ Error retrieving message details**"
            )

    @app.on_message(filters.command(["cmail"], prefixes=COMMAND_PREFIX))
    async def manual_check_mail(client, message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(
                chat_id=message.chat.id,
                text=BAN_REPLY
            )
            return

        if message.chat.type != ChatType.PRIVATE:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌ Bro Tempmail Feature Only Works In Private**"
            )
            return

        loading_msg = await client.send_message(
            chat_id=message.chat.id,
            text="**Checking Mails.. Please wait**"
        )

        token = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        if not token:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌ Please provide a token after the .cmail or /cmail command.**"
            )
            await client.delete_messages(message.chat.id, [loading_msg.id])
            return

        user_tokens[message.from_user.id] = token
        messages = await list_messages(token)
        if not messages:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌ No messages found or maybe wrong token**"
            )
            await client.delete_messages(message.chat.id, [loading_msg.id])
            return

        output = "**📧 Your SmartTools-Mail Messages 📧**\n"
        output += "**━━━━━━━━━━━━━━━━━━**\n"
        
        buttons = []
        for idx, msg in enumerate(messages[:10], 1):
            output += f"{idx}. From: `{msg['from']['address']}` - Subject: {msg['subject']}\n"
            button = InlineKeyboardButton(f"{idx}", callback_data=f"read_{msg['id']}")
            buttons.append(button)

        keyboard = []
        for i in range(0, len(buttons), 5):
            keyboard.append(buttons[i:i+5])

        await client.send_message(
            chat_id=message.chat.id,
            text=output,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await client.delete_messages(message.chat.id, [loading_msg.id])
