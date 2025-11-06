import asyncio
from telethon import TelegramClient, events
from telethon.tl import types
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.auth import LogOutRequest
from telethon.tl.functions.messages import EditMessageRequest, DeleteMessagesRequest, SendReactionRequest
from telethon.errors import ChatRestrictedError, ChatWriteForbiddenError, MessageNotModifiedError
from dotenv import load_dotenv
import os
from collections import defaultdict
import time
import random
import sys
import pickle
import unicodedata
import argparse
import re
import json

load_dotenv()

SESSION_NAME = 'telegram_cli_session'
MEDIA_DIR = 'downloads'
CACHE_FILE = 'dialogs_cache.pkl'
CONFIG_FILE = '.ntc_config'
DRAFTS_FILE = 'drafts.json'
MESSAGE_CACHE_FILE = 'message_cache.pkl'

def get_or_prompt_api_keys():
    """Получить API ID и HASH из .env или попросить у пользователя"""
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')

    if api_id and api_hash:
        return api_id, api_hash

    print("\n⚠ API_ID и API_HASH не найдены в .env\n")
    print("Получи их на https://my.telegram.org\n")

    api_id = input("API_ID: ").strip()
    api_hash = input("API_HASH: ").strip()

    if not api_id or not api_hash:
        print("\n✗ API_ID и API_HASH обязательны!")
        exit(1)

    with open('.env', 'a') as f:
        f.write(f"\nAPI_ID={api_id}\n")
        f.write(f"API_HASH={api_hash}\n")

    print("\n✓ Сохранено в .env\n")
    return api_id, api_hash

API_ID, API_HASH = get_or_prompt_api_keys()

if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

class C:
    PUR = '\033[95m'
    GRAY = '\033[90m'
    WHITE = '\033[97m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    STRIKETHROUGH = '\033[9m'
    INVERSE = '\033[7m'
    HIDDEN = '\033[8m'

THEMES = {
    'dark': {
        'primary': '\033[95m',
        'secondary': '\033[90m',
        'accent': '\033[97m',
        'dim': '\033[2m',
    },
    'light': {
        'primary': '\033[94m',
        'secondary': '\033[37m',
        'accent': '\033[30m',
        'dim': '\033[2m',
    },
    'purple': {
        'primary': '\033[95m',
        'secondary': '\033[35m',
        'accent': '\033[97m',
        'dim': '\033[2m',
    },
    'matrix': {
        'primary': '\033[92m',
        'secondary': '\033[32m',
        'accent': '\033[97m',
        'dim': '\033[2m',
    },
}

LANGUAGES = {
    'en': {'name': 'English', 'session': 'Session', 'logged_in': 'Logged in', 'chats': 'chats', 'history': 'history', 'no_chat': 'no chat', 'error': 'error', 'not_found': 'not found', 'no_media': 'no media', 'exit': 'exit', 'send_text': 'message', 'cant_write': 'cannot write'},
    'ru': {'name': 'Русский', 'session': 'Сессия', 'logged_in': 'Вошли', 'chats': 'чаты', 'history': 'история', 'no_chat': 'нет чата', 'error': 'ошибка', 'not_found': 'не найдено', 'no_media': 'нет медиа', 'exit': 'выход', 'send_text': 'сообщение', 'cant_write': 'не могу писать'},
}

CMD_ALIASES = {
    'l': 'list',
    's': 'select',
    'm': 'msg',
    'sr': 'search',
    'sd': 'send',
    'r': 'reply',
    'f': 'forward',
    'i': 'img',
    'si': 'send-img',
    'n': 'name',
    'b': 'bio',
    'cu': 'cu',
    'mp': 'mp',
    'lo': 'logout',
    'sa': 'saved',
    'sl': 'slots',
    'a': 'about',
    'h': 'help',
    'e': 'exit',
    'd': 'del',
    't': 'text',
    'th': 'theme',
}

class TelegramCLI:
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH, flood_sleep_threshold=0)
        self.current_chat = None
        self.dialogs = []
        self.message_cache = defaultdict(dict)
        self.message_list = []
        self.media_list = []
        self.image_counter = 0
        self.running = True
        self.message_read_status = {}
        self.display_counter = 0
        self.update_task = None
        self.language = 'en'
        self.theme = 'dark'
        self.drafts = self.load_drafts()
        self.folders = {}
        self.current_folder = None
        self.load_theme_from_config()
        self.load_message_cache()

    def load_theme_from_config(self):
        """Load theme from config file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.theme = config.get('theme', 'dark')
            except:
                pass

    def save_theme_to_config(self):
        """Save theme to config file"""
        config = {'theme': self.theme}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    existing = json.load(f)
                    existing.update(config)
                    config = existing
            except:
                pass
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def get_theme_color(self, key):
        """Get color from current theme"""
        return THEMES[self.theme].get(key, C.RESET)

    def load_drafts(self):
        """Load drafts from file"""
        if os.path.exists(DRAFTS_FILE):
            try:
                with open(DRAFTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_drafts(self):
        """Save drafts to file"""
        try:
            with open(DRAFTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.drafts, f, ensure_ascii=False, indent=2)
        except:
            pass

    def save_draft(self, chat_id, text):
        """Save draft for current chat"""
        self.drafts[str(chat_id)] = text
        self.save_drafts()

    def get_draft(self, chat_id):
        """Get draft for chat"""
        return self.drafts.get(str(chat_id), '')

    def clear_draft(self, chat_id):
        """Clear draft for chat"""
        if str(chat_id) in self.drafts:
            del self.drafts[str(chat_id)]
            self.save_drafts()

    def load_message_cache(self):
        """Load message cache from file"""
        if os.path.exists(MESSAGE_CACHE_FILE):
            try:
                with open(MESSAGE_CACHE_FILE, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.message_cache = cache_data.get('messages', defaultdict(dict))
                    print(f"{C.GREEN}✓{C.RESET} Message cache loaded")
            except:
                pass

    def save_message_cache(self):
        """Save message cache to file"""
        try:
            cache_data = {
                'messages': dict(self.message_cache),
                'timestamp': time.time()
            }
            with open(MESSAGE_CACHE_FILE, 'wb') as f:
                pickle.dump(cache_data, f)
        except:
            pass

    def t(self, key):
        return LANGUAGES[self.language].get(key, key)

    def get_chat_type(self, entity):
        if isinstance(entity, types.Channel):
            return 'channel' if entity.broadcast else 'group'
        elif isinstance(entity, types.Chat):
            return 'group'
        elif isinstance(entity, types.User):
            return 'bot' if entity.bot else 'private'
        return 'unknown'

    def get_type_badge(self, entity):
        primary = self.get_theme_color('primary')
        secondary = self.get_theme_color('secondary')
        badges = {
            'bot': f'{primary}*{C.RESET}',
            'private': f'{secondary}@{C.RESET}',
            'group': f'{secondary}#{C.RESET}',
            'channel': f'{secondary}~{C.RESET}',
        }
        return badges.get(self.get_chat_type(entity), '?')

    def get_display_width(self, text):
        width = 0
        for char in text:
            category = unicodedata.category(char)
            if category.startswith('M'):
                continue
            ea_width = unicodedata.east_asian_width(char)
            width += 2 if ea_width in ('F', 'W') else 1
        return width

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'rb') as f:
                    return pickle.load(f)
            except:
                return []
        return []

    def save_cache(self):
        try:
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(self.dialogs, f)
        except:
            pass

    def get_media_type(self, msg):
        if not msg.media:
            return None
        if isinstance(msg.media, types.MessageMediaPhoto):
            return ('img', '.jpg')
        elif isinstance(msg.media, types.MessageMediaDocument):
            mime = getattr(msg.media.document, 'mime_type', '')
            filename = 'file'
            if msg.media.document.attributes:
                attr = msg.media.document.attributes[0]
                if hasattr(attr, 'file_name'):
                    filename = attr.file_name

            if 'sticker' in mime or filename.endswith(('.webp', '.tgs')):
                return ('sticker', '.webp')
            elif 'gif' in mime or filename.endswith('.gif'):
                return ('gif', '.gif')
            elif 'video' in mime or filename.endswith('.mp4'):
                return ('video', '.mp4')
            elif 'voice' in mime or filename.endswith('.ogg'):
                return ('voice', '.ogg')
            elif 'audio' in mime or filename.endswith('.mp3'):
                return ('audio', '.mp3')
            else:
                ext = os.path.splitext(filename)[1] or '.bin'
                return ('document', ext)
        return ('media', '')

    def format_media_label(self, msg):
        media_info = self.get_media_type(msg)
        if not media_info:
            return ""
        media_type, ext = media_info
        primary = self.get_theme_color('primary')
        labels = {'img': 'IMG', 'sticker': 'STK', 'video': 'VID', 'audio': 'AUD', 'document': 'DOC', 'gif': 'GIF', 'voice': 'VCE'}
        label = labels.get(media_type, media_type.upper())
        return f"{primary}[{label}{ext}]{C.RESET}"

    def parse_markdown(self, text):
        """Convert Telegram/Markdown formatting to terminal ANSI codes"""
        # Bold **text**
        text = re.sub(r'\*\*(.+?)\*\*', f'{C.BOLD}\\1{C.RESET}', text)
        # Italic *text* or _text_
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', f'{C.ITALIC}\\1{C.RESET}', text)
        text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', f'{C.ITALIC}\\1{C.RESET}', text)
        # Code `text`
        text = re.sub(r'`(.+?)`', f'{C.GRAY}{C.INVERSE}\\1{C.RESET}', text)
        # Strikethrough ~~text~~
        text = re.sub(r'~~(.+?)~~', f'{C.STRIKETHROUGH}\\1{C.RESET}', text)
        # Underline __text__
        text = re.sub(r'__(.+?)__', f'{C.UNDERLINE}\\1{C.RESET}', text)
        # Spoiler ||text||
        text = re.sub(r'\|\|(.+?)\|\|', f'{C.GRAY}{C.HIDDEN}\\1{C.RESET}', text)
        return text

    def calculate_speed(self, text_length):
        if text_length <= 10:
            return 0.008
        elif text_length <= 30:
            return 0.006
        elif text_length <= 60:
            return 0.004
        return 0.002

    async def start(self):
        session_file = f"{SESSION_NAME}.session"
        primary = self.get_theme_color('primary')
        if os.path.exists(session_file):
            print(f"{primary}✓{C.RESET} {self.t('session')}")
        else:
            print(f"{primary}+{C.RESET} First login")
        await self.client.start()
        me = await self.client.get_me()
        print(f"{primary}✓{C.RESET} {self.t('logged_in')}: {me.first_name}\n")

        # Load folders
        await self.load_folders()

        @self.client.on(events.NewMessage())
        async def handle_new_message(event):
            await self.on_new_message(event)

    async def load_folders(self):
        """Load Telegram folders"""
        try:
            dialogs = await self.client.get_dialogs()
            # Telegram folders are accessible via dialog filters
            self.folders = {'all': dialogs}
        except:
            pass

    async def update_read_status_loop(self):
        while self.running:
            if self.current_chat:
                try:
                    async for msg in self.client.iter_messages(self.current_chat, limit=30):
                        if msg.out:
                            key = f"{self.current_chat.id}_{msg.id}"
                            is_read = hasattr(msg, 'read_date') and msg.read_date is not None
                            self.message_read_status[key] = is_read

                            # Track who read in groups
                            if hasattr(msg, 'reactions') and msg.reactions:
                                self.message_read_status[f"{key}_readers"] = msg.reactions
                except:
                    pass
            await asyncio.sleep(3)

    def animate_send(self):
        frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴']
        primary = self.get_theme_color('primary')
        for i in range(3):
            sys.stdout.write(f"\r{primary}{frames[i % len(frames)]}{C.RESET}")
            sys.stdout.flush()
            time.sleep(0.01)
        sys.stdout.write(f"\r{C.RESET}")
        sys.stdout.flush()

    def get_status(self, msg):
        if msg.out:
            key = f"{self.current_chat.id}_{msg.id}"
            is_read = self.message_read_status.get(key, False)

            # Check for group read receipts
            readers_key = f"{key}_readers"
            if readers_key in self.message_read_status:
                readers = self.message_read_status[readers_key]
                return f"{C.WHITE}✓✓[{len(readers)}]{C.RESET}"

            return f"{C.WHITE}✓✓{C.RESET}" if is_read else f"{C.GRAY}✓{C.RESET}"
        return f"{C.WHITE}•{C.RESET}"

    async def show_msg_animated(self, msg):
        if not msg or not (msg.text or msg.media):
            return
        if msg.media:
            self.image_counter += 1
            self.media_list.append({'msg_id': msg.id, 'img_num': self.image_counter})
        self.display_counter += 1
        sender = "You" if msg.out else (msg.sender.first_name[:10] if hasattr(msg.sender, 'first_name') else "?")
        time_str = msg.date.strftime("%H:%M")
        status = self.get_status(msg)
        media_label = self.format_media_label(msg) if msg.media else ""

        primary = self.get_theme_color('primary')
        secondary = self.get_theme_color('secondary')
        dim = self.get_theme_color('dim')

        sender_prefix = f"{primary}→{C.RESET}" if msg.out else f"{secondary}←{C.RESET}"

        # Show edit indicator
        edit_indicator = f"{C.GRAY}[edited]{C.RESET} " if hasattr(msg, 'edit_date') and msg.edit_date else ""

        if msg.text:
            text = self.parse_markdown(msg.text[:100])
            line = f"{self.display_counter:2} {dim}{time_str}{C.RESET} {status} {sender_prefix} {sender} | {edit_indicator}"
            sys.stdout.write(line)
            sys.stdout.flush()
            speed = self.calculate_speed(len(msg.text))

            # Smart animation that skips ANSI codes
            i = 0
            while i < len(text):
                if text[i:i+2] == '\033':
                    # Find end of ANSI sequence
                    end = text.find('m', i)
                    if end != -1:
                        sys.stdout.write(text[i:end+1])
                        sys.stdout.flush()
                        i = end + 1
                        continue
                sys.stdout.write(text[i])
                sys.stdout.flush()
                time.sleep(speed)
                i += 1

            if media_label:
                sys.stdout.write(f" {media_label}\n")
            else:
                sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            line = f"{self.display_counter:2} {dim}{time_str}{C.RESET} {status} {sender_prefix} {sender} | {edit_indicator}{media_label}\n"
            sys.stdout.write(line)
            sys.stdout.flush()

    async def on_new_message(self, event):
        if not self.current_chat or event.chat_id != self.current_chat.id:
            return
        msg = event.message
        self.message_cache[self.current_chat.id][msg.id] = msg
        if msg.id not in self.message_list:
            self.message_list.append(msg.id)

        if not msg.out:
            sys.stdout.write("\n")
            sys.stdout.flush()

        await self.show_msg_animated(msg)

        # Show draft if exists
        draft = self.get_draft(self.current_chat.id)
        if draft:
            sys.stdout.write(f"{C.DIM}[draft: {draft[:30]}...]{C.RESET} ")

        primary = self.get_theme_color('primary')
        sys.stdout.write(f"{primary}>{C.RESET} ")
        sys.stdout.flush()

    async def list_chats(self, limit=None, folder=None):
        secondary = self.get_theme_color('secondary')
        print(f"\n{secondary}chats{C.RESET}")
        self.dialogs = []
        async for d in self.client.iter_dialogs(limit=100):
            self.dialogs.append(d)
        self.save_cache()

        for idx, d in enumerate(self.dialogs[:limit] if limit else self.dialogs, 1):
            name = d.name[:32]
            badge = self.get_type_badge(d.entity)
            unread = f"+{d.unread_count}" if d.unread_count > 0 else ""

            # Check for draft
            draft_indicator = f"{C.YELLOW}📝{C.RESET}" if self.get_draft(d.id) else ""

            name_width = self.get_display_width(name)
            padding = max(0, 32 - name_width)
            unread_str = unread.rjust(6)

            dim = self.get_theme_color('dim')
            print(f"{dim}│{C.RESET}  {idx:2}  {dim}│{C.RESET} {name}{' ' * padding} {badge} {draft_indicator} {dim}│{C.RESET} {unread_str} {dim}│{C.RESET}")

        print()

    async def select_chat(self, idx):
        try:
            idx = int(idx) - 1
            if 0 <= idx < len(self.dialogs):
                self.current_chat = self.dialogs[idx]
                primary = self.get_theme_color('primary')
                print(f"\n{primary}→{C.RESET} {self.current_chat.name}\n")
                self.message_cache.clear()
                self.message_list.clear()
                self.media_list.clear()
                self.image_counter = 0
                self.display_counter = 0
                self.message_read_status.clear()

                # Show draft if exists
                draft = self.get_draft(self.current_chat.id)
                if draft:
                    print(f"{C.YELLOW}📝 Draft: {draft}{C.RESET}\n")

                await self.show_messages(15)
                return True
            return False
        except:
            return False

    async def show_messages(self, limit=15):
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return

        chat_name = getattr(self.current_chat, 'name', None) or getattr(self.current_chat, 'title', 'Unknown')
        secondary = self.get_theme_color('secondary')
        print(f"{secondary}history — {str(chat_name)[:40]}{C.RESET}")
        msgs = []
        try:
            async for m in self.client.iter_messages(self.current_chat, limit=limit):
                msgs.append(m)
        except:
            print(f"{secondary}error{C.RESET}")
            return

        for idx, msg in enumerate(reversed(msgs), 1):
            try:
                if not (msg.text or msg.media):
                    continue
                self.message_cache[self.current_chat.id][msg.id] = msg
                if msg.id not in self.message_list:
                    self.message_list.append(msg.id)
                if msg.out:
                    key = f"{self.current_chat.id}_{msg.id}"
                    is_read = hasattr(msg, 'read_date') and msg.read_date is not None
                    self.message_read_status[key] = is_read
                if msg.media:
                    self.image_counter += 1
                    if msg.id not in [m['msg_id'] for m in self.media_list]:
                        self.media_list.append({'msg_id': msg.id, 'img_num': self.image_counter})

                sender = "You" if msg.out else (getattr(msg.sender, 'first_name', '?')[:10] if msg.sender else "?")
                time_str = msg.date.strftime("%H:%M") if msg.date else "--:--"
                status = self.get_status(msg)
                media_label = self.format_media_label(msg) if msg.media else ""

                primary = self.get_theme_color('primary')
                dim = self.get_theme_color('dim')

                sender_prefix = f"{primary}→{C.RESET}" if msg.out else f"{secondary}←{C.RESET}"
                self.display_counter = idx

                edit_indicator = f"{C.GRAY}[edited]{C.RESET} " if hasattr(msg, 'edit_date') and msg.edit_date else ""

                if msg.text:
                    text = self.parse_markdown(msg.text[:80])
                    line = f"{idx:2} {dim}{time_str}{C.RESET} {status} {sender_prefix} {sender} | {edit_indicator}{text}"
                    print(line + (f" {media_label}" if media_label else ""))
                else:
                    line = f"{idx:2} {dim}{time_str}{C.RESET} {status} {sender_prefix} {sender} | {edit_indicator}{media_label}"
                    print(line)
            except:
                continue
        print()

        # Save cache after loading messages
        self.save_message_cache()

    async def search_messages(self, query):
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        secondary = self.get_theme_color('secondary')
        dim = self.get_theme_color('dim')
        print(f"\n{secondary}search: {query}{C.RESET}")
        found = 0
        try:
            async for msg in self.client.iter_messages(self.current_chat, search=query, limit=15):
                if msg.text:
                    found += 1
                    sender = "You" if msg.out else (getattr(msg.sender, 'first_name', '?')[:10] if msg.sender else "?")
                    time_str = msg.date.strftime("%H:%M")
                    text = self.parse_markdown(msg.text[:70])
                    print(f"  {found}. {dim}{time_str}{C.RESET} {sender} | {text}")
        except:
            pass
        if found == 0:
            print(f"{secondary}no results{C.RESET}")
        print()

    async def show_my_profile(self):
        try:
            me = await self.client.get_me()
            primary = self.get_theme_color('primary')
            print(f"\n{primary}profile{C.RESET}")
            print(f"  id: {me.id}")
            print(f"  name: {me.first_name} {me.last_name or ''}")
            print(f"  user: @{me.username or 'none'}")
            full = await self.client.get_entity(me.id)
            if hasattr(full, 'about'):
                print(f"  bio: {full.about or 'none'}")
            print()
        except:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}error{C.RESET}")

    async def change_username(self, username):
        try:
            self.animate_send()
            await self.client(UpdateUsernameRequest(username=username))
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} username @{username}")
        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")

    async def change_name(self, first_name, last_name=""):
        try:
            self.animate_send()
            await self.client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} name changed")
        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")

    async def change_bio(self, bio):
        try:
            self.animate_send()
            await self.client(UpdateProfileRequest(about=bio))
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} bio changed")
        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")

    async def edit_message(self, num, new_text):
        """Edit a sent message"""
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                print(f"{C.GRAY}invalid message number{C.RESET}")
                return

            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)

            if not msg or not msg.out:
                print(f"{C.GRAY}can only edit your own messages{C.RESET}")
                return

            self.animate_send()
            await self.client.edit_message(self.current_chat, msg_id, new_text)
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} message edited")

            # Update cache
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)
            self.message_cache[self.current_chat.id][msg_id] = msg

        except MessageNotModifiedError:
            print(f"{C.GRAY}message not modified{C.RESET}")
        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")

    async def delete_message(self, num):
        """Delete a message"""
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                print(f"{C.GRAY}invalid message number{C.RESET}")
                return

            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)

            if not msg:
                print(f"{C.GRAY}message not found{C.RESET}")
                return

            # Check if user can delete
            if not msg.out:
                # Check if user is admin in group
                chat = await self.client.get_entity(self.current_chat)
                if isinstance(chat, (types.Channel, types.Chat)):
                    perms = await self.client.get_permissions(self.current_chat, 'me')
                    if not perms.delete_messages:
                        print(f"{C.GRAY}no permission to delete{C.RESET}")
                        return

            self.animate_send()
            await self.client.delete_messages(self.current_chat, [msg_id])
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} message deleted")

            # Update cache
            if msg_id in self.message_cache.get(self.current_chat.id, {}):
                del self.message_cache[self.current_chat.id][msg_id]
            if msg_id in self.message_list:
                self.message_list.remove(msg_id)

        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")

    async def react_to_message(self, num, emoji):
        """Add reaction to a message"""
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                print(f"{C.GRAY}invalid message number{C.RESET}")
                return

            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)

            if not msg:
                print(f"{C.GRAY}message not found{C.RESET}")
                return

            self.animate_send()

            # Send reaction
            from telethon.tl.types import ReactionEmoji
            reaction = [ReactionEmoji(emoticon=emoji)]
            await self.client(SendReactionRequest(
                peer=self.current_chat,
                msg_id=msg_id,
                reaction=reaction
            ))

            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} reacted with {emoji}")

        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")

    async def change_theme(self, theme_name):
        """Change color theme"""
        if theme_name not in THEMES:
            print(f"{C.GRAY}available themes: {', '.join(THEMES.keys())}{C.RESET}")
            return

        self.theme = theme_name
        self.save_theme_to_config()
        primary = self.get_theme_color('primary')
        print(f"{primary}✓{C.RESET} theme changed to {theme_name}")

    async def send_to_user(self, username, text):
        """Send message to user by username"""
        try:
            # Remove @ if present
            username = username.lstrip('@')

            self.animate_send()

            # Get user entity
            user = await self.client.get_entity(username)

            # Send message
            msg = await self.client.send_message(user, text)

            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} sent to @{username}")

        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")

    async def logout(self):
        try:
            self.animate_send()

            # Save cache before logout
            self.save_message_cache()
            self.save_drafts()

            await self.client(LogOutRequest())
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} logged out")
            self.running = False
            return True
        except Exception as e:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}✗ {str(e)}{C.RESET}")
            return False

    async def pin_message(self, num):
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                return
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} pinned")
        except:
            pass

    async def forward_to_saved(self, num):
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                print(f"{C.GRAY}invalid{C.RESET}")
                return
            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)
            if not msg:
                print(f"{C.GRAY}no msg{C.RESET}")
                return
            me = await self.client.get_me()
            saved_msgs = await self.client.get_entity(me.id)
            self.animate_send()
            await self.client.forward_messages(saved_msgs, msg_id, from_peer=self.current_chat)
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} forwarded")
        except:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}error{C.RESET}")

    async def go_to_saved_messages(self):
        try:
            me = await self.client.get_me()
            self.current_chat = await self.client.get_entity(me.id)
            primary = self.get_theme_color('primary')
            print(f"\n{primary}→{C.RESET} Saved Messages\n")
            self.message_cache.clear()
            self.message_list.clear()
            self.media_list.clear()
            self.image_counter = 0
            self.display_counter = 0
            self.message_read_status.clear()
            await self.show_messages(15)
        except:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}error{C.RESET}")

    async def slot_machine(self):
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        self.animate_send()
        try:
            msg = await self.client.send_message(self.current_chat, '🎰')
        except (ChatRestrictedError, ChatWriteForbiddenError):
            primary = self.get_theme_color('primary')
            print(f"{primary}✗{C.RESET} cannot write")
            return
        except:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}error{C.RESET}")
            return

        await asyncio.sleep(0.5)
        emojis = ['🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '7️⃣', '💎']
        r1, r2, r3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
        primary = self.get_theme_color('primary')
        if r1 == r2 == r3:
            result = f"{primary}jackpot! {r1}{r2}{r3}{C.RESET}" if r1 == '7️⃣' else f"{C.WHITE}win {r1}{r2}{r3}{C.RESET}"
        elif r1 == r2 or r2 == r3:
            result = f"{C.GRAY}small win {r1}{r2}{r3}{C.RESET}"
        else:
            result = f"{C.GRAY}lose {r1}{r2}{r3}{C.RESET}"
        print(result)
        self.message_cache[self.current_chat.id][msg.id] = msg
        if msg.id not in self.message_list:
            self.message_list.append(msg.id)

    async def download_img(self, num):
        try:
            num = int(num)
            item = next((i for i in self.media_list if i['img_num'] == num), None)
            if not item:
                print(f"{C.GRAY}not found{C.RESET}")
                return
            msg = await self.client.get_messages(self.current_chat, ids=item['msg_id'])
            if not msg or not msg.media:
                print(f"{C.GRAY}no media{C.RESET}")
                return
            media_info = self.get_media_type(msg)
            folder = os.path.join(MEDIA_DIR, media_info[0]) if media_info else MEDIA_DIR
            if not os.path.exists(folder):
                os.makedirs(folder)
            file_path = await msg.download_media(file=folder)
            primary = self.get_theme_color('primary')
            print(f"{primary}✓{C.RESET} {os.path.abspath(file_path)}")
        except:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}error{C.RESET}")

    async def send_img(self, path):
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        if not os.path.exists(path):
            print(f"{C.GRAY}not found{C.RESET}")
            return
        self.animate_send()
        try:
            msg = await self.client.send_file(self.current_chat, path)
            self.message_cache[self.current_chat.id][msg.id] = msg
            if msg.id not in self.message_list:
                self.message_list.append(msg.id)
            await self.show_msg_animated(msg)
        except (ChatRestrictedError, ChatWriteForbiddenError):
            primary = self.get_theme_color('primary')
            print(f"{primary}✗{C.RESET} cannot write")
        except:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}error{C.RESET}")

    async def send_msg(self, text):
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return

        # Clear draft after sending
        self.clear_draft(self.current_chat.id)

        self.animate_send()
        try:
            msg = await self.client.send_message(self.current_chat, text)
            self.message_cache[self.current_chat.id][msg.id] = msg
            if msg.id not in self.message_list:
                self.message_list.append(msg.id)
            await self.show_msg_animated(msg)
        except (ChatRestrictedError, ChatWriteForbiddenError):
            primary = self.get_theme_color('primary')
            print(f"{primary}✗{C.RESET} cannot write")
        except:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}error{C.RESET}")

    async def reply(self, num, text):
        if not self.current_chat:
            secondary = self.get_theme_color('secondary')
            print(f"{secondary}no chat{C.RESET}")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                return
            self.animate_send()
            msg = await self.client.send_message(self.current_chat, text, reply_to=self.message_list[num])
            self.message_cache[self.current_chat.id][msg.id] = msg
            if msg.id not in self.message_list:
                self.message_list.append(msg.id)
            await self.show_msg_animated(msg)
        except (ChatRestrictedError, ChatWriteForbiddenError):
            primary = self.get_theme_color('primary')
            print(f"{primary}✗{C.RESET} cannot write")
        except:
            pass

    def show_help(self):
        primary = self.get_theme_color('primary')
        accent = self.get_theme_color('accent')
        help_text = f"""
{primary}ntc - n1ghtfallz Telegram Client{C.RESET}

{accent}chats{C.RESET}
  ntc --list, ntc -l [n]           show chats
  ntc --select, ntc -s <n>         select chat
  ntc --msg, ntc -m [n]            show messages
  ntc --search, ntc -sr <text>     search
  ntc --text, ntc -t @user <text>  send to user

{accent}messages{C.RESET}
  ntc --send, ntc -sd <text>       send message
  ntc --reply, ntc -r <#> <text>   reply
  ntc --forward, ntc -f <#>        forward to saved
  ntc --edit <#> <text>            edit message
  ntc --del, ntc -d <#>            delete message
  ntc --react <#> <emoji>          add reaction

{accent}media{C.RESET}
  ntc --img, ntc -i <n>            download
  ntc --send-img, ntc -si <path>   send file

{accent}profile{C.RESET}
  ntc --mp                         my profile
  ntc --cu <user>                  change username
  ntc --name, ntc -n <name>        change name
  ntc --bio, ntc -b <text>         change bio

{accent}settings{C.RESET}
  ntc --theme, ntc -th <name>      change theme
                                   (dark, light, purple, matrix)

{accent}other{C.RESET}
  ntc --logout, ntc -lo            logout
  ntc --saved, ntc -sa             saved messages
  ntc --slots, ntc -sl             slot machine
  ntc --about, ntc -a              about
  ntc --help, ntc -h               help
  ntc --exit, ntc -e               exit

{accent}features{C.RESET}
  • reactions, reply
  • fast loading
  • idk
"""
        print(help_text)

    def show_about(self):
        primary = self.get_theme_color('primary')
        about_text = f"""
{primary}ntc - n1ghtfallz Telegram Client{C.RESET}

owner: @n1ghtfallz
version: 1.0
coded via claude sonnet 4
language: python 3.14


{primary}made for fun by n1ght{C.RESET}
"""
        print(about_text)

    def parse_command(self, cmd_input):
        parts = cmd_input.split()
        if not parts:
            return None, None, None

        if parts[0] == 'ntc':
            if len(parts) < 2:
                return 'send_direct', 'ntc', None

            if parts[1].startswith('-'):
                cmd_raw = parts[1]
                if cmd_raw.startswith('--'):
                    cmd = cmd_raw[2:]
                else:
                    alias = cmd_raw[1:]
                    cmd = CMD_ALIASES.get(alias, alias)

                args = ' '.join(parts[2:]) if len(parts) > 2 else None
                return cmd, args, None
            else:
                return 'send_direct', cmd_input, None
        else:
            # Check if it's a draft (incomplete message)
            if self.current_chat and not cmd_input.startswith('/'):
                # Save as draft
                self.save_draft(self.current_chat.id, cmd_input)
            return 'send_direct', cmd_input, None

    def get_input(self):
        return input(f"{self.get_theme_color('primary')}>{C.RESET} ")

    async def run(self):
        await self.start()
        secondary = self.get_theme_color('secondary')
        print(f"{secondary}type 'ntc --help' for commands\n{C.RESET}")
        self.update_task = asyncio.create_task(self.update_read_status_loop())
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                cmd_input = await loop.run_in_executor(None, self.get_input)
            except EOFError:
                break

            if not cmd_input or not cmd_input.strip():
                continue

            cmd, args, _ = self.parse_command(cmd_input.strip())

            if not cmd:
                continue

            if cmd == 'list':
                limit = int(args) if args and args.isdigit() else None
                await self.list_chats(limit)
            elif cmd == 'select':
                if args:
                    await self.select_chat(args)
            elif cmd == 'msg':
                limit = int(args) if args and args.isdigit() else 15
                await self.show_messages(limit)
            elif cmd == 'search':
                if args:
                    await self.search_messages(args)
            elif cmd == 'send':
                if args:
                    await self.send_msg(args)
            elif cmd == 'reply':
                if args and len(args.split()) >= 2:
                    parts = args.split(' ', 1)
                    await self.reply(parts[0], parts[1])
            elif cmd == 'forward':
                if args:
                    await self.forward_to_saved(args)
            elif cmd == 'edit':
                if args and len(args.split()) >= 2:
                    parts = args.split(' ', 1)
                    await self.edit_message(parts[0], parts[1])
            elif cmd == 'del':
                if args:
                    await self.delete_message(args)
            elif cmd == 'react':
                if args and len(args.split()) >= 2:
                    parts = args.split(' ', 1)
                    await self.react_to_message(parts[0], parts[1])
            elif cmd == 'img':
                if args:
                    await self.download_img(args)
            elif cmd == 'send-img':
                if args:
                    await self.send_img(args)
            elif cmd == 'mp':
                await self.show_my_profile()
            elif cmd == 'cu':
                if args:
                    await self.change_username(args)
            elif cmd == 'name':
                if args:
                    name_parts = args.split(' ', 1)
                    first = name_parts[0]
                    last = name_parts[1] if len(name_parts) > 1 else ""
                    await self.change_name(first, last)
            elif cmd == 'bio':
                if args:
                    await self.change_bio(args)
            elif cmd == 'theme':
                if args:
                    await self.change_theme(args)
            elif cmd == 'text':
                if args and len(args.split()) >= 2:
                    parts = args.split(' ', 1)
                    await self.send_to_user(parts[0], parts[1])
            elif cmd == 'logout':
                if await self.logout():
                    break
            elif cmd == 'saved':
                await self.go_to_saved_messages()
            elif cmd == 'slots':
                await self.slot_machine()
            elif cmd == 'about':
                self.show_about()
            elif cmd == 'help':
                self.show_help()
            elif cmd == 'exit':
                print(f"{secondary}exit{C.RESET}")
                self.running = False
                break
            elif cmd == 'send_direct':
                if self.current_chat:
                    await self.send_msg(args)
            else:
                print(f"{secondary}unknown: --{cmd}{C.RESET}")

            await asyncio.sleep(0.01)

        if self.update_task:
            self.update_task.cancel()

        # Save everything before exit
        self.save_message_cache()
        self.save_drafts()

        await self.client.disconnect()

async def main():
    parser = argparse.ArgumentParser(prog='ntc', add_help=False)

    parser.add_argument('--help', action='store_true')
    parser.add_argument('--about', action='store_true')
    parser.add_argument('--list', nargs='?', const=None)
    parser.add_argument('--select', type=int)
    parser.add_argument('--msg', type=int, nargs='?', const=15)
    parser.add_argument('--search', type=str)
    parser.add_argument('--send', type=str)
    parser.add_argument('--reply', nargs=2, metavar=('NUM', 'TEXT'))
    parser.add_argument('--forward', type=int)
    parser.add_argument('--edit', nargs=2, metavar=('NUM', 'TEXT'))
    parser.add_argument('--del', type=int, dest='delete')
    parser.add_argument('--react', nargs=2, metavar=('NUM', 'EMOJI'))
    parser.add_argument('--img', type=int)
    parser.add_argument('--send-img', type=str)
    parser.add_argument('--mp', action='store_true')
    parser.add_argument('--cu', type=str)
    parser.add_argument('--name', type=str, nargs='+')
    parser.add_argument('--bio', type=str)
    parser.add_argument('--theme', type=str)
    parser.add_argument('--text', type=str, nargs='+')
    parser.add_argument('--logout', action='store_true')
    parser.add_argument('--saved', action='store_true')
    parser.add_argument('--slots', action='store_true')

    args = parser.parse_args()

    if any(vars(args).values()):
        cli = TelegramCLI()
        try:
            await cli.start()

            if args.help:
                cli.show_help()
            elif args.about:
                cli.show_about()
            elif args.list is not None:
                await cli.list_chats(args.list)
            elif args.select:
                await cli.select_chat(args.select)
            elif args.msg is not None:
                await cli.show_messages(args.msg)
            elif args.search:
                await cli.search_messages(args.search)
            elif args.send:
                await cli.send_msg(args.send)
            elif args.reply:
                await cli.reply(args.reply[0], args.reply[1])
            elif args.forward:
                await cli.forward_to_saved(args.forward)
            elif args.edit:
                await cli.edit_message(args.edit[0], args.edit[1])
            elif args.delete:
                await cli.delete_message(args.delete)
            elif args.react:
                await cli.react_to_message(args.react[0], args.react[1])
            elif args.img:
                await cli.download_img(args.img)
            elif args.send_img:
                await cli.send_img(args.send_img)
            elif args.mp:
                await cli.show_my_profile()
            elif args.cu:
                await cli.change_username(args.cu)
            elif args.name:
                first = args.name[0]
                last = ' '.join(args.name[1:]) if len(args.name) > 1 else ""
                await cli.change_name(first, last)
            elif args.bio:
                await cli.change_bio(args.bio)
            elif args.theme:
                await cli.change_theme(args.theme)
            elif args.text:
                username = args.text[0]
                text = ' '.join(args.text[1:])
                await cli.send_to_user(username, text)
            elif args.logout:
                await cli.logout()
            elif args.saved:
                await cli.go_to_saved_messages()
            elif args.slots:
                await cli.slot_machine()

            await cli.client.disconnect()
        except KeyboardInterrupt:
            print(f"\n{C.GRAY}interrupted{C.RESET}")
        except Exception as e:
            print(f"{C.GRAY}error: {e}{C.RESET}")
    else:
        cli = TelegramCLI()
        try:
            await cli.run()
        except KeyboardInterrupt:
            print(f"\n{C.GRAY}exit{C.RESET}")

if __name__ == '__main__':
    asyncio.run(main())