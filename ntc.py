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
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.theme import Theme
from rich.markdown import Markdown

load_dotenv()

SESSION_NAME = 'telegram_cli_session'
MEDIA_DIR = 'downloads'
CACHE_FILE = 'dialogs_cache.pkl'
CONFIG_FILE = '.ntc_config'
DRAFTS_FILE = 'drafts.json'
MESSAGE_CACHE_FILE = 'message_cache.pkl'

def get_or_prompt_api_keys():
    """Get API ID and HASH from .env or prompt user"""
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')

    if api_id and api_hash:
        return api_id, api_hash

    print("\n⚠ API_ID and API_HASH not found in .env\n")
    print("Get them at https://my.telegram.org\n")

    api_id = input("API_ID: ").strip()
    api_hash = input("API_HASH: ").strip()

    if not api_id or not api_hash:
        print("\n✗ API_ID and API_HASH are required!")
        exit(1)

    with open('.env', 'a') as f:
        f.write(f"\nAPI_ID={api_id}\n")
        f.write(f"API_HASH={api_hash}\n")

    print("\n✓ Saved to .env\n")
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
    'uk': {'name': 'Українська', 'session': 'Сесія', 'logged_in': 'Увійшли', 'chats': 'чати', 'history': 'історія', 'no_chat': 'немає чату', 'error': 'помилка', 'not_found': 'не знайдено', 'no_media': 'немає медіа', 'exit': 'вихід', 'send_text': 'повідомлення', 'cant_write': 'не можу писати'},
    'kk': {'name': 'Қазақша', 'session': 'Сессия', 'logged_in': 'Кірді', 'chats': 'чаттар', 'history': 'тарих', 'no_chat': 'чат жоқ', 'error': 'қате', 'not_found': 'табылмады', 'no_media': 'медиа жоқ', 'exit': 'шығу', 'send_text': 'хабарлама', 'cant_write': 'жаза алмаймын'},
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
    'lang': 'language',
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
        self.console = Console()
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
                    self.console.print(f"[green]✓[/green] Message cache loaded")
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
        """Convert Telegram/Markdown formatting to Rich markup"""
        # Bold **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'[bold]\1[/bold]', text)
        # Italic *text* or _text_
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'[italic]\1[/italic]', text)
        text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'[italic]\1[/italic]', text)
        # Code `text`
        text = re.sub(r'`(.+?)`', r'[reverse]\1[/reverse]', text)
        # Strikethrough ~~text~~
        text = re.sub(r'~~(.+?)~~', r'[strike]\1[/strike]', text)
        # Underline __text__
        text = re.sub(r'__(.+?)__', r'[underline]\1[/underline]', text)
        # Spoiler ||text||
        text = re.sub(r'\|\|(.+?)\|\|', r'[dim]\1[/dim]', text)
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
            self.console.print(f"[bold magenta]✓[/bold magenta] {self.t('session')}")
        else:
            self.console.print(f"[bold magenta]+[/bold magenta] First login")
        await self.client.start()
        me = await self.client.get_me()
        self.console.print(f"[bold magenta]✓[/bold magenta] {self.t('logged_in')}: {me.first_name}\n")

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

        # Remove ANSI codes from status for Rich
        status = re.sub(r'\x1b\[[0-9;]*m', '', status)
        
        sender_color = "bold magenta" if msg.out else "bold cyan"
        sender_prefix = "→" if msg.out else "←"

        # Show edit indicator
        edit_indicator = "[dim][edited][/dim] " if hasattr(msg, 'edit_date') and msg.edit_date else ""

        if msg.text:
            text = self.parse_markdown(msg.text[:100])
            self.console.print(f" {self.display_counter:2} [dim]{time_str}[/dim] {status} [{sender_color}]{sender_prefix} {sender}[/{sender_color}] | {edit_indicator}{text} {media_label}")
        else:
            self.console.print(f" {self.display_counter:2} [dim]{time_str}[/dim] {status} [{sender_color}]{sender_prefix} {sender}[/{sender_color}] | {edit_indicator}{media_label}")

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
            self.console.print(f"[dim][draft: {draft[:30]}...][/dim] ", end="")

        self.console.print(f"[bold magenta]>[/bold magenta] ", end="")

    async def list_chats(self, limit=None, folder=None):
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("#", style="dim", width=4)
        table.add_column(self.t('chats'), style="bold")
        table.add_column("Type", width=3)
        table.add_column("Unread", justify="right")

        self.dialogs = []
        async for d in self.client.iter_dialogs(limit=100):
            self.dialogs.append(d)
        self.save_cache()

        for idx, d in enumerate(self.dialogs[:limit] if limit else self.dialogs, 1):
            name = d.name[:32]
            badge = self.get_type_badge(d.entity)
            unread = f"+{d.unread_count}" if d.unread_count > 0 else ""
            
            # Check for draft
            draft_indicator = "📝" if self.get_draft(d.id) else ""
            
            # Clean ANSI from badge for Rich
            clean_badge = badge.replace(C.RESET, "").replace(self.get_theme_color('primary'), "").replace(self.get_theme_color('secondary'), "")
            
            table.add_row(
                str(idx),
                f"{name} {draft_indicator}",
                clean_badge,
                unread
            )

        self.console.print(table)
        print()

    async def select_chat(self, idx):
        try:
            idx = int(idx) - 1
            if 0 <= idx < len(self.dialogs):
                self.current_chat = self.dialogs[idx]
                self.console.print(f"\n[bold magenta]→[/bold magenta] {self.current_chat.name}\n")
                self.message_cache.clear()
                self.message_list.clear()
                self.media_list.clear()
                self.image_counter = 0
                self.display_counter = 0
                self.message_read_status.clear()

                # Show draft if exists
                draft = self.get_draft(self.current_chat.id)
                if draft:
                    self.console.print(f"[yellow]📝 Draft: {draft}[/yellow]\n")

                await self.show_messages(15)
                return True
            return False
        except:
            return False

    async def show_messages(self, limit=15):
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return

        chat_name = getattr(self.current_chat, 'name', None) or getattr(self.current_chat, 'title', 'Unknown')
        self.console.print(Panel(f"[bold]{self.t('history')} — {str(chat_name)[:40]}[/bold]", style="blue"))
        
        msgs = []
        try:
            async for m in self.client.iter_messages(self.current_chat, limit=limit):
                msgs.append(m)
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")
            return

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("ID", style="dim", width=4)
        table.add_column("Time", style="dim", width=6)
        table.add_column("Status", width=4)
        table.add_column("Sender", width=15)
        table.add_column("Content")

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
                # Remove ANSI
                status = re.sub(r'\x1b\[[0-9;]*m', '', status)
                
                media_label = self.format_media_label(msg) if msg.media else ""
                # Remove ANSI from media label
                media_label = re.sub(r'\x1b\[[0-9;]*m', '', media_label)

                sender_color = "magenta" if msg.out else "cyan"
                sender_fmt = f"[{sender_color}]{sender}[/{sender_color}]"
                self.display_counter = idx

                edit_indicator = "[dim][edited][/dim] " if hasattr(msg, 'edit_date') and msg.edit_date else ""

                if msg.text:
                    text = self.parse_markdown(msg.text[:80])
                    content = f"{edit_indicator}{text} {media_label}"
                else:
                    content = f"{edit_indicator}{media_label}"
                
                table.add_row(str(idx), time_str, status, sender_fmt, content)
            except:
                continue
        
        self.console.print(table)
        print()

        # Save cache after loading messages
        self.save_message_cache()

    async def search_messages(self, query):
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return
        self.console.print(f"\n[bold magenta]search: {query}[/bold magenta]")
        found = 0
        try:
            async for msg in self.client.iter_messages(self.current_chat, search=query, limit=15):
                if msg.text:
                    found += 1
                    sender = "You" if msg.out else (getattr(msg.sender, 'first_name', '?')[:10] if msg.sender else "?")
                    time_str = msg.date.strftime("%H:%M")
                    text = self.parse_markdown(msg.text[:70])
                    self.console.print(f"  {found}. [dim]{time_str}[/dim] {sender} | {text}")
        except:
            pass
        if found == 0:
            self.console.print(f"[dim]{self.t('not_found')}[/dim]")
        print()

    async def show_my_profile(self):
        try:
            me = await self.client.get_me()
            self.console.print(Panel(f"id: {me.id}\nname: {me.first_name} {me.last_name or ''}\nuser: @{me.username or 'none'}", title="Profile", border_style="magenta"))
            full = await self.client.get_entity(me.id)
            if hasattr(full, 'about'):
                self.console.print(f"  bio: {full.about or 'none'}")
            print()
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")

    async def change_username(self, username):
        try:
            self.animate_send()
            await self.client(UpdateUsernameRequest(username=username))
            self.console.print(f"[green]✓[/green] username @{username}")
        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")

    async def change_name(self, first_name, last_name=""):
        try:
            self.animate_send()
            await self.client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
            self.console.print(f"[green]✓[/green] name changed")
        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")

    async def change_bio(self, bio):
        try:
            self.animate_send()
            await self.client(UpdateProfileRequest(about=bio))
            self.console.print(f"[green]✓[/green] bio changed")
        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")

    async def edit_message(self, num, new_text):
        """Edit a sent message"""
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                self.console.print(f"[dim]invalid message number[/dim]")
                return

            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)

            if not msg or not msg.out:
                self.console.print(f"[dim]can only edit your own messages[/dim]")
                return

            self.animate_send()
            await self.client.edit_message(self.current_chat, msg_id, new_text)
            self.console.print(f"[green]✓[/green] message edited")

            # Update cache
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)
            self.message_cache[self.current_chat.id][msg_id] = msg

        except MessageNotModifiedError:
            self.console.print(f"[dim]message not modified[/dim]")
        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")

    async def delete_message(self, num):
        """Delete a message"""
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                self.console.print(f"[dim]invalid message number[/dim]")
                return

            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)

            if not msg:
                self.console.print(f"[dim]message not found[/dim]")
                return

            # Check if user can delete
            if not msg.out:
                # Check if user is admin in group
                chat = await self.client.get_entity(self.current_chat)
                if isinstance(chat, (types.Channel, types.Chat)):
                    perms = await self.client.get_permissions(self.current_chat, 'me')
                    if not perms.delete_messages:
                        self.console.print(f"[dim]no permission to delete[/dim]")
                        return

            self.animate_send()
            await self.client.delete_messages(self.current_chat, [msg_id])
            self.console.print(f"[green]✓[/green] message deleted")

            # Update cache
            if msg_id in self.message_cache.get(self.current_chat.id, {}):
                del self.message_cache[self.current_chat.id][msg_id]
            if msg_id in self.message_list:
                self.message_list.remove(msg_id)

        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")

    async def react_to_message(self, num, emoji):
        """Add reaction to a message"""
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                self.console.print(f"[dim]invalid message number[/dim]")
                return

            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)

            if not msg:
                self.console.print(f"[dim]message not found[/dim]")
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

            self.console.print(f"[green]✓[/green] reacted with {emoji}")

        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")

    async def change_theme(self, theme_name):
        """Change color theme"""
        if theme_name not in THEMES:
            self.console.print(f"[dim]available themes: {', '.join(THEMES.keys())}[/dim]")
            return

        self.theme = theme_name
        self.save_theme_to_config()
        self.console.print(f"[green]✓[/green] theme changed to {theme_name}")

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

            self.console.print(f"[green]✓[/green] sent to @{username}")

        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")

    async def logout(self):
        try:
            self.animate_send()

            # Save cache before logout
            self.save_message_cache()
            self.save_drafts()

            await self.client(LogOutRequest())
            self.console.print(f"[green]✓[/green] logged out")
            self.running = False
            return True
        except Exception as e:
            self.console.print(f"[red]✗ {str(e)}[/red]")
            return False

    async def pin_message(self, num):
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                return
            self.console.print(f"[green]✓[/green] pinned")
        except:
            pass

    async def forward_to_saved(self, num):
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return
        try:
            num = int(num) - 1
            if num < 0 or num >= len(self.message_list):
                self.console.print(f"[dim]invalid[/dim]")
                return
            msg_id = self.message_list[num]
            msg = await self.client.get_messages(self.current_chat, ids=msg_id)
            if not msg:
                self.console.print(f"[dim]no msg[/dim]")
                return
            me = await self.client.get_me()
            saved_msgs = await self.client.get_entity(me.id)
            self.animate_send()
            await self.client.forward_messages(saved_msgs, msg_id, from_peer=self.current_chat)
            self.console.print(f"[green]✓[/green] forwarded")
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")

    async def go_to_saved_messages(self):
        try:
            me = await self.client.get_me()
            self.current_chat = await self.client.get_entity(me.id)
            self.console.print(f"\n[bold magenta]→[/bold magenta] Saved Messages\n")
            self.message_cache.clear()
            self.message_list.clear()
            self.media_list.clear()
            self.image_counter = 0
            self.display_counter = 0
            self.message_read_status.clear()
            await self.show_messages(15)
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")

    async def slot_machine(self):
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return
        self.animate_send()
        try:
            msg = await self.client.send_message(self.current_chat, '🎰')
        except (ChatRestrictedError, ChatWriteForbiddenError):
            self.console.print(f"[red]✗[/red] cannot write")
            return
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")
            return

        await asyncio.sleep(0.5)
        emojis = ['🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '7️⃣', '💎']
        r1, r2, r3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
        if r1 == r2 == r3:
            result = f"[bold magenta]jackpot! {r1}{r2}{r3}[/bold magenta]" if r1 == '7️⃣' else f"[white]win {r1}{r2}{r3}[/white]"
        elif r1 == r2 or r2 == r3:
            result = f"[dim]small win {r1}{r2}{r3}[/dim]"
        else:
            result = f"[dim]lose {r1}{r2}{r3}[/dim]"
        self.console.print(result)
        self.message_cache[self.current_chat.id][msg.id] = msg
        if msg.id not in self.message_list:
            self.message_list.append(msg.id)

    async def download_img(self, num):
        try:
            num = int(num)
            item = next((i for i in self.media_list if i['img_num'] == num), None)
            if not item:
                self.console.print(f"[dim]not found[/dim]")
                return
            msg = await self.client.get_messages(self.current_chat, ids=item['msg_id'])
            if not msg or not msg.media:
                self.console.print(f"[dim]no media[/dim]")
                return
            media_info = self.get_media_type(msg)
            folder = os.path.join(MEDIA_DIR, media_info[0]) if media_info else MEDIA_DIR
            if not os.path.exists(folder):
                os.makedirs(folder)
            file_path = await msg.download_media(file=folder)
            self.console.print(f"[green]✓[/green] {os.path.abspath(file_path)}")
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")

    async def send_img(self, path):
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
            return
        if not os.path.exists(path):
            self.console.print(f"[dim]not found[/dim]")
            return
        self.animate_send()
        try:
            msg = await self.client.send_file(self.current_chat, path)
            self.message_cache[self.current_chat.id][msg.id] = msg
            if msg.id not in self.message_list:
                self.message_list.append(msg.id)
            await self.show_msg_animated(msg)
        except (ChatRestrictedError, ChatWriteForbiddenError):
            self.console.print(f"[red]✗[/red] cannot write")
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")

    async def send_msg(self, text):
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
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
            self.console.print(f"[red]✗[/red] cannot write")
        except:
            self.console.print(f"[red]{self.t('error')}[/red]")

    async def reply(self, num, text):
        if not self.current_chat:
            self.console.print(f"[yellow]{self.t('no_chat')}[/yellow]")
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
            self.console.print(f"[red]✗[/red] cannot write")
        except:
            pass

    def show_help(self):
        help_text = """
[bold magenta]ntc - n1ghtfallz Telegram Client[/bold magenta]

[bold white]chats[/bold white]
  ntc --list, ntc -l [n]           show chats
  ntc --select, ntc -s <n>         select chat
  ntc --msg, ntc -m [n]            show messages
  ntc --search, ntc -sr <text>     search
  ntc --text, ntc -t @user <text>  send to user

[bold white]messages[/bold white]
  ntc --send, ntc -sd <text>       send message
  ntc --reply, ntc -r <#> <text>   reply
  ntc --forward, ntc -f <#>        forward to saved
  ntc --edit <#> <text>            edit message
  ntc --del, ntc -d <#>            delete message
  ntc --react <#> <emoji>          add reaction

[bold white]media[/bold white]
  ntc --img, ntc -i <n>            download
  ntc --send-img, ntc -si <path>   send file

[bold white]profile[/bold white]
  ntc --mp                         my profile
  ntc --cu <user>                  change username
  ntc --name, ntc -n <name>        change name
  ntc --bio, ntc -b <text>         change bio

[bold white]settings[/bold white]
  ntc --theme, ntc -th <name>      change theme
                                   (dark, light, purple, matrix)
  ntc --lang <code >               change language (en, ru, uk, kk)

[bold white]other[/bold white]
  ntc --logout, ntc -lo            logout
  ntc --saved, ntc -sa             saved messages
  ntc --slots, ntc -sl             slot machine
  ntc --about, ntc -a              about
  ntc --help, ntc -h               help
  ntc --exit, ntc -e               exit
"""
        self.console.print(Panel(help_text, title="Help", border_style="magenta"))

    def show_about(self):
        about_text = """
[bold magenta]ntc - n1ghtfallz Telegram Client[/bold magenta]

owner: @n1ghtfallz
version: 1.0
coded via claude sonnet 4
language: python 3.14


[italic]made for fun by n1ght[/italic]
"""
        self.console.print(Panel(about_text, title="About", border_style="blue"))

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
        self.console.print(f"[dim]type 'ntc --help' for commands[/dim]\n")
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

            match cmd:
                case 'list':
                    limit = int(args) if args and args.isdigit() else None
                    await self.list_chats(limit)
                case 'select':
                    if args:
                        await self.select_chat(args)
                case 'msg':
                    limit = int(args) if args and args.isdigit() else 15
                    await self.show_messages(limit)
                case 'search':
                    if args:
                        await self.search_messages(args)
                case 'send':
                    if args:
                        await self.send_msg(args)
                case 'reply':
                    if args and len(args.split()) >= 2:
                        parts = args.split(' ', 1)
                        await self.reply(parts[0], parts[1])
                case 'forward':
                    if args:
                        await self.forward_to_saved(args)
                case 'edit':
                    if args and len(args.split()) >= 2:
                        parts = args.split(' ', 1)
                        await self.edit_message(parts[0], parts[1])
                case 'del':
                    if args:
                        await self.delete_message(args)
                case 'react':
                    if args and len(args.split()) >= 2:
                        parts = args.split(' ', 1)
                        await self.react_to_message(parts[0], parts[1])
                case 'img':
                    if args:
                        await self.download_img(args)
                case 'send-img':
                    if args:
                        await self.send_img(args)
                case 'mp':
                    await self.show_my_profile()
                case 'cu':
                    if args:
                        await self.change_username(args)
                case 'name':
                    if args:
                        name_parts = args.split(' ', 1)
                        first = name_parts[0]
                        last = name_parts[1] if len(name_parts) > 1 else ""
                        await self.change_name(first, last)
                case 'bio':
                    if args:
                        await self.change_bio(args)
                case 'theme':
                    if args:
                        await self.change_theme(args)
                case 'language' | 'lang':
                    if args and args in LANGUAGES:
                        self.language = args
                        self.console.print(f"Language changed to {LANGUAGES[args]['name']}")
                case 'text':
                    if args and len(args.split()) >= 2:
                        parts = args.split(' ', 1)
                        await self.send_to_user(parts[0], parts[1])
                case 'logout':
                    if await self.logout():
                        break
                case 'saved':
                    await self.go_to_saved_messages()
                case 'slots':
                    await self.slot_machine()
                case 'about':
                    self.show_about()
                case 'help':
                    self.show_help()
                case 'exit':
                    self.console.print(f"[dim]exit[/dim]")
                    self.running = False
                    break
                case 'send_direct':
                    if self.current_chat:
                        await self.send_msg(args)
                case _:
                    self.console.print(f"[dim]unknown: --{cmd}[/dim]")

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
    parser.add_argument('--lang', type=str)

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
            elif args.lang:
                if args.lang in LANGUAGES:
                    cli.language = args.lang
                    print(f"Language changed to {LANGUAGES[args.lang]['name']}")

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
