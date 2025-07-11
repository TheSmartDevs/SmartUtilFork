# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev

import re
import os
import random
import aiohttp
import asyncio
import pycountry
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from config import BIN_KEY, COMMAND_PREFIX, CC_GEN_LIMIT, MULTI_CCGEN_LIMIT, BAN_REPLY
from core import banned_users
from utils import notify_admin, LOGGER

def is_amex_bin(bin_str):
    clean_bin = bin_str.replace('x', '').replace('X', '')
    if len(clean_bin) >= 2:
        first_two = clean_bin[:2]
        return first_two in ['34', '37']
    return False

async def get_bin_info(bin, client, message):
    headers = {'x-api-key': BIN_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://data.handyapi.com/bin/{bin}", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_msg = f"API returned status code {response.status}"
                    LOGGER.error(error_msg)
                    await client.send_message(message.chat.id, f"**Error: {error_msg}**")
                    return None
    except Exception as e:
        error_msg = f"Error fetching BIN info: {str(e)}"
        LOGGER.error(error_msg)
        await client.send_message(message.chat.id, f"**Error: {error_msg}**")
        await notify_admin(client, "/gen", e, message)
        return None

def luhn_algorithm(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

def calculate_luhn_check_digit(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit

def generate_credit_card(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 14 if is_amex else 15
    cvv_length = 4 if is_amex else 3
    
    for _ in range(amount):
        while True:
            card_body = ''.join([str(random.randint(0, 9)) if char.lower() == 'x' else char for char in bin])
            remaining_digits = target_length - len(card_body)
            card_body += ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            check_digit = calculate_luhn_check_digit(card_body)
            card_number = card_body + str(check_digit)
            if luhn_algorithm(card_number):
                card_month = month or f"{random.randint(1, 12):02}"
                card_year = year or random.randint(2024, 2029)
                card_cvv = cvv or ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
                cards.append(f"{card_number}|{card_month}|{card_year}|{card_cvv}")
                break
    return cards

def parse_input(user_input):
    bin = None
    month = None
    year = None
    cvv = None
    amount = 10
    match = re.match(
        r"^(\d{6,16}[xX]{0,10}|\d{6,15})"
        r"(?:[|:/](\d{2}))?"
        r"(?:[|:/](\d{2,4}))?"
        r"(?:[|:/]([0-9]{3,4}|xxx|rnd)?)?"
        r"(?:\s+(\d{1,4}))?$",
        user_input.strip(), re.IGNORECASE
    )
    if match:
        bin, month, year, cvv, amount = match.groups()
        if bin:
            has_x = 'x' in bin.lower()
            bin_length = len(bin)
            if has_x and bin_length > 16:
                return None, None, None, None, None
            if not has_x and (bin_length < 6 or bin_length > 15):
                return None, None, None, None, None
        if cvv and cvv.lower() not in ['xxx', 'rnd']:
            is_amex = is_amex_bin(bin) if bin else False
            expected_cvv_length = 4 if is_amex else 3
            if len(cvv) != expected_cvv_length:
                return None, None, None, None, None
        if cvv and cvv.lower() in ['xxx', 'rnd'] or cvv is None:
            cvv = None  # Set cvv to None to generate random CVV
        if year and len(year) == 2:
            year = f"20{year}"
        amount = int(amount) if amount else 10
    else:
        return None, None, None, None, None
    return bin, month, year, cvv, amount

def generate_custom_cards(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 14 if is_amex else 15
    cvv_length = 4 if is_amex else 3
    
    for _ in range(amount):
        while True:
            card_body = bin.replace('x', '').replace('X', '')
            remaining_digits = target_length - len(card_body)
            card_body += ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            check_digit = calculate_luhn_check_digit(card_body)
            card_number = card_body + str(check_digit)
            if luhn_algorithm(card_number):
                card_month = month or f"{random.randint(1, 12):02}"
                card_year = year or random.randint(2024, 2029)
                card_cvv = cvv or ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
                cards.append(f"{card_number}|{card_month}|{card_year}|{card_cvv}")
                break
    return cards

def get_flag(country_code, client=None, message=None):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            raise ValueError("Invalid country code")
        country_name = country.name
        flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return country_name, flag_emoji
    except Exception as e:
        error_msg = f"Error in get_flag: {str(e)}"
        LOGGER.error(error_msg)
        if client and message:
            asyncio.create_task(notify_admin(client, "/gen", e, message))
        raise

def get_country_code_from_name(country_name, client=None, message=None):
    try:
        country = pycountry.countries.lookup(country_name)
        return country.alpha_2
    except Exception as e:
        error_msg = f"Error in get_country_code_from_name: {str(e)}"
        LOGGER.error(error_msg)
        if client and message:
            asyncio.create_task(notify_admin(client, "/gen", e, message))
        raise

def setup_gen_handler(app: Client):
    @app.on_message(filters.command(["gen"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def generate_handler(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY)
            return

        user_input = message.text.split(maxsplit=1)
        if len(user_input) == 1:
            await client.send_message(message.chat.id, "**Provide a valid BIN ❌**")
            return

        user_input = user_input[1]
        bin, month, year, cvv, amount = parse_input(user_input)

        if not bin:
            LOGGER.error(f"Invalid BIN: {bin}")
            await client.send_message(message.chat.id, "**Sorry Bin Must Be 6-15 Digits or Up to 16 Digits with 'x' ❌**")
            return

        if cvv is not None:
            is_amex = is_amex_bin(bin)
            expected_cvv_length = 4 if is_amex else 3
            if len(cvv) != expected_cvv_length:
                cvv_type = "4 digits for AMEX" if is_amex else "3 digits for non-AMEX"
                await client.send_message(message.chat.id, f"**Invalid CVV format. CVV must be {cvv_type} ❌**")
                return

        if amount > CC_GEN_LIMIT:
            await client.send_message(message.chat.id, f"**You can only generate up to {CC_GEN_LIMIT} credit cards ❌**")
            return

        bin_info = await get_bin_info(bin[:6], client, message)
        if not bin_info or bin_info.get("Status") != "SUCCESS" or not isinstance(bin_info.get("Country"), dict):
            return

        bank = bin_info.get("Issuer")
        country_name = bin_info["Country"].get("Name", "Unknown")
        card_type = bin_info.get("Type", "Unknown")
        card_scheme = bin_info.get("Scheme", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"

        country_code = bin_info["Country"]["A2"]
        country_name, flag_emoji = get_flag(country_code, client, message)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"

        progress_message = await client.send_message(message.chat.id, "**Generating Credit Cards...**")
        LOGGER.info("Generating Credit Cards...")

        cards = generate_custom_cards(bin, amount, month, year, cvv) if 'x' in bin.lower() else generate_credit_card(bin, amount, month, year, cvv)

        if amount <= 10:
            card_text = "\n".join([f"`{card}`" for card in cards])
            await progress_message.delete()
            response_text = f"**BIN ⇾ {bin}**\n**Amount ⇾ {amount}**\n\n{card_text}\n\n**Bank:** {bank_text}\n**Country:** {country_name} {flag_emoji}\n**BIN Info:** {bin_info_text}"
            callback_data = f"regenerate|{user_input.replace(' ', '_')}"

            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Re-Generate", callback_data=callback_data)]]
            )
            await client.send_message(message.chat.id, response_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        else:
            file_name = f"{bin} x {amount}.txt"
            try:
                with open(file_name, "w") as file:
                    file.write("\n".join(cards))

                await progress_message.delete()
                caption = (
                    f"**🔍 Multiple CC Generate Successful 📋**\n"
                    f"**━━━━━━━━━━━━━━━━**\n"
                    f"**• BIN:** {bin}\n"
                    f"**• INFO:** {bin_info_text}\n"
                    f"**• BANK:** {bank_text}\n"
                    f"**• COUNTRY:** {country_name} {flag_emoji}\n"
                    f"**━━━━━━━━━━━━━━━━**\n"
                    f"**👁 Thanks For Using Our Tool ✅**"
                )

                await client.send_document(message.chat.id, document=file_name, caption=caption, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await client.send_message(message.chat.id, "**Sorry Bro API Response Unavailable**")
                LOGGER.error(f"Error saving cards to file: {str(e)}")
                await notify_admin(client, "/gen", e, message)
            finally:
                if os.path.exists(file_name):
                    os.remove(file_name)

    @app.on_callback_query(filters.regex(r"regenerate\|(.+)"))
    async def regenerate_callback(client: Client, callback_query):
        user_id = callback_query.from_user.id if callback_query.from_user else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(callback_query.message.chat.id, BAN_REPLY)
            return

        original_input = callback_query.data.split('|', 1)[1]
        original_input = original_input.replace('_', ' ')
        bin, month, year, cvv, amount = parse_input(original_input)

        if not bin:
            await callback_query.answer("Sorry Bin Must Be 6-15 Digits or Up to 16 Digits with 'x' ❌", show_alert=True)
            return

        if cvv is not None:
            is_amex = is_amex_bin(bin)
            expected_cvv_length = 4 if is_amex else 3
            if len(cvv) != expected_cvv_length:
                cvv_type = "4 digits for AMEX" if is_amex else "3 digits for non-AMEX"
                await callback_query.answer(f"Invalid CVV format. CVV must be {cvv_type} ❌", show_alert=True)
                return

        if amount > CC_GEN_LIMIT:
            await callback_query.answer(f"You can only generate up to {CC_GEN_LIMIT} credit cards ❌", show_alert=True)
            return

        bin_info = await get_bin_info(bin[:6], client, callback_query.message)
        if not bin_info or bin_info.get("Status") != "SUCCESS" or not isinstance(bin_info.get("Country"), dict):
            return

        bank = bin_info.get("Issuer")
        country_name = bin_info["Country"].get("Name", "Unknown")
        card_type = bin_info.get("Type", "Unknown")
        card_scheme = bin_info.get("Scheme", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"

        country_code = bin_info["Country"]["A2"]
        country_name, flag_emoji = get_flag(country_code, client, callback_query.message)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"

        cards = generate_custom_cards(bin, amount, month, year, cvv) if 'x' in bin.lower() else generate_credit_card(bin, amount, month, year, cvv)

        card_text = "\n".join([f"`{card}`" for card in cards[:10]])
        response_text = f"**BIN ⇾ {bin}**\n**Amount ⇾ {amount}**\n\n{card_text}\n\n**Bank:** {bank_text}\n**Country:** {country_name} {flag_emoji}\n**BIN Info:** {bin_info_text}"

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Re-Generate", callback_data=f"regenerate|{original_input.replace(' ', '_')}")]
        ])

        await callback_query.message.edit_text(response_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
