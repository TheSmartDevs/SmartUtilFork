# Copyright @ISmartCoder
# Updates Channel t.me/TheSmartDev

import os
from utils import LOGGER
from core import banned_users
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, COMMAND_PREFIX, BAN_REPLY
import uuid
import asyncio
import aiohttp
from PIL import Image
import subprocess

async def get_sticker_set(bot_token: str, name: str):
    url = f"https://api.telegram.org/bot{bot_token}/getStickerSet"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={"name": name}) as response:
            if response.status != 200:
                LOGGER.error(f"Failed to get sticker set: {await response.json()}")
                return None
            return (await response.json()).get("result")

async def add_sticker_to_set(bot_token: str, user_id: int, name: str, png_sticker: str, emojis: str):
    url = f"https://api.telegram.org/bot{bot_token}/addStickerToSet"
    async with aiohttp.ClientSession() as session:
        with open(png_sticker, "rb") as sticker_file:
            form = aiohttp.FormData()
            form.add_field("png_sticker", sticker_file)
            form.add_field("user_id", str(user_id))
            form.add_field("name", name)
            form.add_field("emojis", emojis)
            async with session.post(url, data=form) as response:
                if response.status != 200:
                    error = await response.json()
                    LOGGER.error(f"Failed to add PNG sticker: {error}")
                    raise Exception(error["description"])
                return await response.json()

async def add_video_sticker_to_set(bot_token: str, user_id: int, name: str, webm_sticker: str, emojis: str):
    url = f"https://api.telegram.org/bot{bot_token}/addStickerToSet"
    async with aiohttp.ClientSession() as session:
        with open(webm_sticker, "rb") as sticker_file:
            form = aiohttp.FormData()
            form.add_field("webm_sticker", sticker_file)
            form.add_field("user_id", str(user_id))
            form.add_field("name", name)
            form.add_field("emojis", emojis)
            async with session.post(url, data=form) as response:
                if response.status != 200:
                    error = await response.json()
                    LOGGER.error(f"Failed to add video sticker: {error}")
                    raise Exception(error["description"])
                return await response.json()

async def add_animated_sticker_to_set(bot_token: str, user_id: int, name: str, tgs_sticker: str, emojis: str):
    url = f"https://api.telegram.org/bot{bot_token}/addStickerToSet"
    async with aiohttp.ClientSession() as session:
        with open(tgs_sticker, "rb") as sticker_file:
            form = aiohttp.FormData()
            form.add_field("tgs_sticker", sticker_file)
            form.add_field("user_id", str(user_id))
            form.add_field("name", name)
            form.add_field("emojis", emojis)
            async with session.post(url, data=form) as response:
                if response.status != 200:
                    error = await response.json()
                    LOGGER.error(f"Failed to add animated sticker: {error}")
                    raise Exception(error["description"])
                return await response.json()

async def create_sticker_set(bot_token: str, user_id: int, name: str, title: str, sticker_file: str, emojis: str, sticker_type: str):
    url = f"https://api.telegram.org/bot{bot_token}/createNewStickerSet"
    file_param = "png_sticker" if sticker_type == "png" else "tgs_sticker" if sticker_type == "tgs" else "webm_sticker"
    async with aiohttp.ClientSession() as session:
        with open(sticker_file, "rb") as sticker_file:
            form = aiohttp.FormData()
            form.add_field(file_param, sticker_file)
            form.add_field("user_id", str(user_id))
            form.add_field("name", name)
            form.add_field("title", title)
            form.add_field("emojis", emojis)
            async with session.post(url, data=form) as response:
                if response.status != 200:
                    error = await response.json()
                    LOGGER.error(f"Failed to create sticker set: {error}")
                    raise Exception(error["description"])
                return await response.json()

async def resize_png_for_sticker(input_file: str, output_file: str):
    try:
        async with asyncio.Lock():
            with Image.open(input_file) as im:
                width, height = im.size
                if width == 512 or height == 512:
                    im.save(output_file, "PNG", optimize=True)
                    return output_file
                
                if width > height:
                    new_width = 512
                    new_height = int((512 / width) * height)
                else:
                    new_height = 512
                    new_width = int((512 / height) * width)
                
                im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)
                im.save(output_file, "PNG", optimize=True)
                return output_file
    except Exception as e:
        LOGGER.error(f"Error resizing PNG: {str(e)}")
        return None

async def process_video_sticker(input_file: str, output_file: str):
    try:
        command = [
            "ffmpeg", "-i", input_file,
            "-t", "3",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2,fps=24",
            "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "150k",
            "-an", "-y",
            output_file
        ]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            LOGGER.error(f"FFmpeg error: {stderr.decode()}")
            return None
        if os.path.exists(output_file) and os.path.getsize(output_file) > 256 * 1024:
            LOGGER.warning("File size exceeds 256KB, re-encoding with lower quality")
            command[-3] = "-b:v"
            command[-2] = "100k"
            process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                LOGGER.error(f"FFmpeg error: {stderr.decode()}")
                return None
        return output_file
    except Exception as e:
        LOGGER.error(f"Error processing video: {str(e)}")
        return None

async def process_gif_to_webm(input_file: str, output_file: str):
    try:
        command = [
            "ffmpeg", "-i", input_file,
            "-t", "3",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2,fps=24",
            "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "150k",
            "-an", "-y",
            output_file
        ]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            LOGGER.error(f"FFmpeg error: {stderr.decode()}")
            return None
        if os.path.exists(output_file) and os.path.getsize(output_file) > 256 * 1024:
            LOGGER.warning("File size exceeds 256KB, re-encoding with lower quality")
            command[-3] = "-b:v"
            command[-2] = "100k"
            process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                LOGGER.error(f"FFmpeg error: {stderr.decode()}")
                return None
        return output_file
    except Exception as e:
        LOGGER.error(f"Error processing GIF: {str(e)}")
        return None

def setup_kang_handler(app: Client, bot_token: str):
    
    @app.on_message(filters.command(["kang"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def kang(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await client.send_message(message.chat.id, BAN_REPLY, parse_mode=ParseMode.MARKDOWN)
            return

        user = message.from_user
        packnum = 1
        packname = f"a{user.id}_by_{client.me.username}"
        max_stickers = 120
        temp_files = []

        temp_message = await client.send_message(chat_id=message.chat.id, text="<b>Kanging this Sticker...✨</b>")

        # Optimized sticker set check
        while packnum <= 100:  # Prevent infinite loop
            sticker_set = await get_sticker_set(bot_token, packname)
            if not sticker_set or len(sticker_set["stickers"]) < max_stickers:
                break
            packnum += 1
            packname = f"a{packnum}_{user.id}_by_{client.me.username}"

        if not message.reply_to_message:
            await temp_message.edit_text("<b>Please reply to a sticker, image, or document to kang it!</b>")
            return

        reply = message.reply_to_message
        if reply.sticker:
            file_id = reply.sticker.file_id
        elif reply.photo:
            file_id = reply.photo.file_id
        elif reply.document:
            file_id = reply.document.file_id
        elif reply.animation:
            file_id = reply.animation.file_id
        else:
            await temp_message.edit_text("<b>Please reply to a valid sticker, image, GIF, or document!</b>")
            return

        sticker_format = "png"
        if reply.sticker:
            if reply.sticker.is_animated:
                sticker_format = "tgs"
            elif reply.sticker.is_video:
                sticker_format = "webm"
        elif reply.animation or (reply.document and reply.document.mime_type == "image/gif"):
            sticker_format = "gif"

        try:
            file_name = f"kangsticker_{uuid.uuid4().hex}"
            if sticker_format == "tgs":
                kang_file = await app.download_media(file_id, file_name=f"{file_name}.tgs")
            elif sticker_format == "webm":
                kang_file = await app.download_media(file_id, file_name=f"{file_name}.webm")
            elif sticker_format == "gif":
                kang_file = await app.download_media(file_id, file_name=f"{file_name}.gif")
            else:
                kang_file = await app.download_media(file_id, file_name=f"{file_name}.png")
            
            if not kang_file:
                await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
                return
            
            temp_files.append(kang_file)

        except Exception as e:
            LOGGER.error(f"Download error: {str(e)}")
            await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
            return

        sticker_emoji = "🌟"
        if len(message.command) > 1:
            sticker_emoji = message.command[1]
        elif reply.sticker and reply.sticker.emoji:
            sticker_emoji = reply.sticker.emoji

        # Construct full name for display title
        full_name = user.first_name
        if user.last_name:
            full_name += f" {user.last_name}"
        pack_title = f"{full_name}'s Pack"

        try:
            if sticker_format == "png":
                output_file = f"resized_{uuid.uuid4().hex}.png"
                processed_file = await resize_png_for_sticker(kang_file, output_file)
                if not processed_file:
                    await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
                    return
                kang_file = processed_file
                temp_files.append(kang_file)
            
            elif sticker_format == "gif":
                output_file = f"compressed_{uuid.uuid4().hex}.webm"
                processed_file = await process_gif_to_webm(kang_file, output_file)
                if not processed_file:
                    await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
                    return
                kang_file = output_file
                sticker_format = "webm"
                temp_files.append(kang_file)
            
            elif sticker_format == "webm":
                output_file = f"compressed_{uuid.uuid4().hex}.webm"
                processed_file = await process_video_sticker(kang_file, output_file)
                if not processed_file:
                    await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
                    return
                kang_file = output_file
                temp_files.append(kang_file)

        except Exception as e:
            LOGGER.error(f"Processing error: {str(e)}")
            await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
            return

        try:
            if sticker_format == "tgs":
                await add_animated_sticker_to_set(bot_token, user.id, packname, kang_file, sticker_emoji)
            elif sticker_format == "webm":
                await add_video_sticker_to_set(bot_token, user.id, packname, kang_file, sticker_emoji)
            else:
                await add_sticker_to_set(bot_token, user.id, packname, kang_file, sticker_emoji)

            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("View Sticker Pack", url=f"t.me/addstickers/{packname}")]])
            await temp_message.edit_text(
                f"**Sticker Kanged Successful! ✅**\n**Sticker Emoji: {sticker_emoji}**\n**Sticker Pack Name: {pack_title}**",
                reply_markup=keyboard
            )

        except Exception as e:
            if "STICKERSET_INVALID" in str(e):
                try:
                    await create_sticker_set(bot_token, user.id, packname, pack_title, kang_file, sticker_emoji, sticker_format)
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("View Sticker Pack", url=f"t.me/addstickers/{packname}")]])
                    await temp_message.edit_text(
                        f"**Sticker Kanged Successful! ✅**\n**Sticker Emoji: {sticker_emoji}**\n**Sticker Pack Name: {pack_title}**",
                        reply_markup=keyboard
                    )
                except Exception as ce:
                    LOGGER.error(f"Create sticker set error: {str(ce)}")
                    await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
            else:
                LOGGER.error(f"Add sticker error: {str(e)}")
                await temp_message.edit_text("<b>❌ Failed To Kang The Sticker</b>")
        
        finally:
            # Optimized cleanup
            for file in temp_files:
                try:
                    os.remove(file)
                except:
                    LOGGER.warning(f"Failed to remove temporary file: {file}")
