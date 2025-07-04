# Copyright @ISmartDevs
# Channel t.me/TheSmartDev
import aiohttp
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from config import COMMAND_PREFIX
from utils import LOGGER, notify_admin  # Import LOGGER and notify_admin from utils
from core import banned_users  # Check if user is banned

# Temporary in-memory storage
currency_storage = {}

async def get_converted_amount(from_currency: str, amount: float, to_currency: str) -> dict:
    url = f"https://real-time-global-exchange-rates.bjcoderx.workers.dev/?From={from_currency}&Amount={amount}&To={to_currency}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                LOGGER.error("API request failed with status code %s", response.status)
                raise Exception("API request failed")
            data = await response.json()
            LOGGER.info("Successfully fetched conversion rate for %s to %s", from_currency, to_currency)
            return data

def setup_currency_handler(app: Client):
    @app.on_message(filters.command(["currency"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def currency_handler(client, message):
        # Check if user is banned
        user_id = message.from_user.id if message.from_user else None
        # FIX: Await the banned_users.find_one as it's an async call
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, "**✘Sorry You're Banned From Using Me↯**", parse_mode=ParseMode.MARKDOWN)
            LOGGER.info(f"Banned user {user_id} attempted to use /currency")
            return

        if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
            return

        command = message.text.split()
        if len(command) < 3:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌ Please provide the correct format: /currency `USD` 10 `INR`**",
                parse_mode=ParseMode.MARKDOWN
            )
            LOGGER.warning("Invalid command format: %s", message.text)
            return

        from_currency = command[1].upper()
        try:
            amount = float(command[2])
        except ValueError:
            await client.send_message(
                chat_id=message.chat.id,
                text="**❌ Invalid amount. Please use a number like: /currency USD 10 INR**",
                parse_mode=ParseMode.MARKDOWN
            )
            LOGGER.warning("Invalid amount provided: %s", command[2])
            return

        to_currency = command[3].upper() if len(command) > 3 else "INR"

        loading_msg = await client.send_message(
            chat_id=message.chat.id,
            text="**🔄 Smart Tools Converting Currency..**",
            parse_mode=ParseMode.MARKDOWN
        )

        try:
            conversion_data = await get_converted_amount(from_currency, amount, to_currency)
            converted_amount = float(conversion_data["converted_amount"])
            rate = float(conversion_data["rate"])
            currency_storage[message.chat.id] = {"rate": rate, "converted_amount": converted_amount}

            await loading_msg.edit_text(
                f"📊 Currency Conversion Results:\n\n"
                f"✨ **From Currency:** `{from_currency}`\n"
                f"💥 **Amount:** `{amount}`\n"
                f"⚡️ **To Currency:** `{to_currency}`\n"
                f"💰 **Converted Amount:** `{converted_amount}`\n"
                f"💹 **Exchange Rate:** `{rate}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh${from_currency}${amount}${to_currency}${rate}")]]
                )
            )
            LOGGER.info("Currency conversion result sent for %s to %s: %s %s", from_currency, to_currency, amount, converted_amount)
        except Exception as e:
            await loading_msg.edit_text(
                "**Sorry Bro API Dead Of Exchanger❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            LOGGER.error("Exception occurred: %s", e)
            # Notify admins about the error
            await notify_admin(client, "/currency", e, message)

    @app.on_callback_query(filters.regex(r"refresh\$(\w+)\$(\d+\.\d+|\d+)\$(\w+)\$(\d+\.\d+|\d+)"))
    async def refresh_callback(client: Client, callback_query: CallbackQuery):
        # Check if user is banned
        user_id = callback_query.from_user.id if callback_query.from_user else None
        # FIX: Await the banned_users.find_one as it's an async call
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await callback_query.message.edit_text("**✘Sorry You're Banned From Using Me↯**", parse_mode=ParseMode.MARKDOWN)
            LOGGER.info(f"Banned user {user_id} attempted to use refresh for {callback_query.data}")
            return

        _, from_currency, amount, to_currency, previous_rate = callback_query.data.split("$")
        amount = float(amount)
        previous_rate = float(previous_rate)

        try:
            conversion_data = await get_converted_amount(from_currency, amount, to_currency)
            current_rate = float(conversion_data["rate"])
            converted_amount = float(conversion_data["converted_amount"])

            previous_data = currency_storage.get(callback_query.message.chat.id, None)
            if not previous_data:
                await callback_query.answer("No previous data found❌", show_alert=True)
                LOGGER.info("No previous data found for refresh in chat %s", callback_query.message.chat.id)
                return

            previous_converted_amount = previous_data["converted_amount"]

            if current_rate == previous_rate:
                await callback_query.answer("No Change Detected From Database❌", show_alert=True)
                LOGGER.info("No change detected for %s to %s", from_currency, to_currency)
            else:
                currency_storage[callback_query.message.chat.id] = {"rate": current_rate, "converted_amount": converted_amount}

                await callback_query.message.edit_text(
                    f"📊 Currency Conversion Results:\n\n"
                    f"✨ **From Currency:** `{from_currency}`\n"
                    f"💥 **Amount:** `{amount}`\n"
                    f"⚡️ **To Currency:** `{to_currency}`\n"
                    f"💰 **Converted Amount:** `{converted_amount}`\n"
                    f"💹 **Exchange Rate:** `{current_rate}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh${from_currency}${amount}${to_currency}${current_rate}")]]
                    )
                )
                await callback_query.answer("Currency Conversion Updated✨", show_alert=True)
                LOGGER.info("Rate updated for %s to %s: %s", from_currency, to_currency, current_rate)
        except Exception as e:
            await callback_query.message.edit_text(
                "**Sorry Bro API Dead Of Exchanger❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            LOGGER.error("Exception occurred during refresh: %s", e)
            # Notify admins about the error
            await notify_admin(client, "/currency refresh", e, callback_query.message)
