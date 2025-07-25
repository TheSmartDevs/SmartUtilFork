# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev

import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

BASE_URL = "https://api.binance.com/api/v3/ticker/24hr"

async def fetch_crypto_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_URL) as response:
                response.raise_for_status()
                LOGGER.info("Successfully fetched crypto data from Binance API")
                return await response.json()
    except Exception as e:
        LOGGER.error(f"Failed to fetch crypto data: {e}")
        raise

def get_top_gainers(data, top_n=5):
    return sorted(data, key=lambda x: float(x['priceChangePercent']), reverse=True)[:top_n]

def get_top_losers(data, top_n=5):
    return sorted(data, key=lambda x: float(x['priceChangePercent']))[:top_n]

def format_crypto_info(data, start_index=0):
    result = ""
    for idx, item in enumerate(data, start=start_index + 1):
        result += (
            f"{idx}. Symbol: {item['symbol']}\n"
            f"  Change: {item['priceChangePercent']}%\n"
            f"  Last Price: {item['lastPrice']}\n"
            f"  24h High: {item['highPrice']}\n"
            f"  24h Low: {item['lowPrice']}\n"
            f"  24h Volume: {item['volume']}\n"
            f"  24h Quote Volume: {item['quoteVolume']}\n\n"
        )
    return result

def setup_binance_handler(app: Client):
    @app.on_message(filters.command(["gainers", "losers"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def handle_command(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY, parse_mode=ParseMode.MARKDOWN)
            LOGGER.info(f"Banned user {user_id} attempted to use /{message.command[0]}")
            return

        command = message.command[0]
        fetching_message = await client.send_message(message.chat.id, f"Fetching {command}...", parse_mode=ParseMode.HTML)
        
        try:
            data = await fetch_crypto_data()
            top_n = 5
            if command == "gainers":
                top_cryptos = get_top_gainers(data, top_n)
                title = "Gainers"
            else:
                top_cryptos = get_top_losers(data, top_n)
                title = "Losers"

            formatted_info = format_crypto_info(top_cryptos)
            await fetching_message.delete()
            response_message = f"List Of Top {title}:\n\n{formatted_info}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Next", callback_data=f"{command}_1")]
            ])
            await client.send_message(message.chat.id, response_message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            LOGGER.info(f"Sent top {title.lower()} to chat {message.chat.id}")

        except Exception as e:
            await fetching_message.delete()
            await client.send_message(message.chat.id, "Error: Unable to fetch data from Binance API", parse_mode=ParseMode.HTML)
            LOGGER.error(f"Error processing /{command}: {e}")
            await notify_admin(client, f"/{command}", e, message)

    @app.on_callback_query(filters.regex(r"^(gainers|losers)_\d+"))
    async def handle_pagination(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id if callback_query.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await callback_query.message.edit_text(BAN_REPLY, parse_mode=ParseMode.MARKDOWN)
            LOGGER.info(f"Banned user {user_id} attempted to use pagination for {callback_query.data}")
            return

        command, page = callback_query.data.split('_')
        page = int(page)
        next_page = page + 1
        prev_page = page - 1

        try:
            data = await fetch_crypto_data()
            top_n = 5
            if command == "gainers":
                top_cryptos = get_top_gainers(data, top_n * next_page)[(page-1)*top_n:page*top_n]
                title = "Gainers"
            else:
                top_cryptos = get_top_losers(data, top_n * next_page)[(page-1)*top_n:page*top_n]
                title = "Losers"

            formatted_info = format_crypto_info(top_cryptos, start_index=(page-1)*top_n)
            response_message = f"List Of Top {title}:\n\n{formatted_info}"

            keyboard_buttons = []
            if prev_page > 0:
                keyboard_buttons.append(InlineKeyboardButton("Previous", callback_data=f"{command}_{prev_page}"))
            if len(top_cryptos) == top_n:
                keyboard_buttons.append(InlineKeyboardButton("Next", callback_data=f"{command}_{next_page}"))

            keyboard = InlineKeyboardMarkup([keyboard_buttons])
            await callback_query.message.edit_text(response_message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            LOGGER.info(f"Updated pagination for {command} (page {page}) in chat {callback_query.message.chat.id}")

        except Exception as e:
            await callback_query.message.edit_text("Error: Unable to fetch data from Binance API", parse_mode=ParseMode.HTML)
            LOGGER.error(f"Error in pagination for {command} (page {page}): {e}")
            await notify_admin(client, f"/{command} pagination", e, callback_query.message)
