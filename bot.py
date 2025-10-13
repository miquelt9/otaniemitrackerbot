import re
import asyncio
from telegram import Update, BotCommand, BotCommandScopeAllPrivateChats
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters, MessageHandler, CallbackQueryHandler, ConversationHandler
import pickle
import time
import string
import logging
from datetime import datetime
from typing import Dict, Any

import storage
from utils import remove_punctuation, extract_word
import keyboards
import messages as msg_tpl

logging.basicConfig(filename='bot.log', filemode='a', format='%(asctime)s - %(message)s', level=logging.INFO)

admins = set()

mods = set()

# Async queue for notifications to avoid blocking handlers
notification_queue = asyncio.Queue()


# Conversation states
ASK_TRACK_WORD = 1
ASK_BAN_WORD = 2
ASK_FEEDBACK = 3
ASK_BROADCAST_MESSAGE = 4


def _paginate_list(items, page: int, per_page: int = 8):
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], page, total_pages


async def _answer_cb(update: Update):
    try:
        await update.callback_query.answer()
    except Exception:
        pass


def _is_message_too_old(message, max_age_minutes: int = 5) -> bool:
    """Check if a message is older than the specified number of minutes."""
    if not message or not hasattr(message, 'date'):
        return False
    
    message_age_seconds = time.time() - message.date.timestamp()
    max_age_seconds = max_age_minutes * 60
    
    if message_age_seconds > max_age_seconds:
        logging.info(f"⏰ Message dismissed - too old ({message_age_seconds:.1f}s > {max_age_seconds}s)")
        return True
    
    return False


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    kb = keyboards.main_menu_kb(user in admins, user in mods)
    if update.callback_query:
        await _answer_cb(update)
        await storage.log_interaction(user.id, 'callback', 'menu_main')
        try:
            await update.callback_query.message.edit_text(msg_tpl.main_menu_text(), reply_markup=kb)
        except Exception:
            await update.callback_query.message.reply_text(msg_tpl.main_menu_text(), reply_markup=kb)
    else:
        await check_then_send_message(context, user, msg_tpl.main_menu_text(), type="Menu", reply_markup=kb)


async def periodic_save_job(context: ContextTypes.DEFAULT_TYPE):
    await storage.save_if_needed(force=False)


# Conversation: Track word
async def track_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    
    # Check if message is too old (10 minutes) - only for command messages
    if update.message and _is_message_too_old(update.message, max_age_minutes=5):
        return ConversationHandler.END
    
    # If command has argument, process immediately
    text = update.message.text if update.message else ''
    parts = (text or '').split(maxsplit=1)
    if len(parts) == 2:
        word = extract_word(parts[1])
        if word:
            await add_track_word(user, word)
            await check_then_send_message(context, user, 'Succesfully tracking ' + word, type="Track")
            return ConversationHandler.END
    # Ask for word
    await check_then_send_message(context, user, 'Please send the word to track:', type="Track Ask", reply_markup=keyboards.cancel_kb())
    return ASK_TRACK_WORD


async def track_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    
    # Check if message is too old (10 minutes)
    if _is_message_too_old(update.message, max_age_minutes=5):
        return ConversationHandler.END
    
    word = extract_word(update.message.text)
    if not word:
        await check_then_send_message(context, user, 'Invalid word. Try again or press Cancel.', type="Track Receive", reply_markup=keyboards.cancel_kb())
        return ASK_TRACK_WORD
    await add_track_word(user, word)
    await check_then_send_message(context, user, 'Succesfully tracking ' + word, type="Track")
    return ConversationHandler.END


# Conversation: Ban word
async def ban_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    
    # Check if message is too old (10 minutes) - only for command messages
    if update.message and _is_message_too_old(update.message, max_age_minutes=5):
        return ConversationHandler.END
    
    text = update.message.text if update.message else ''
    parts = (text or '').split(maxsplit=1)
    if len(parts) == 2:
        word = extract_word(parts[1])
        if word:
            await add_ban_word(user, word)
            await check_then_send_message(context, user, 'Succesfully banned ' + word + "! You won't receive any message that includes it.", type="Ban")
            return ConversationHandler.END
    await check_then_send_message(context, user, msg_tpl.ban_word_warning(), type="Ban Ask", reply_markup=keyboards.cancel_kb())
    return ASK_BAN_WORD


async def ban_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    
    # Check if message is too old (10 minutes)
    if _is_message_too_old(update.message, max_age_minutes=5):
        return ConversationHandler.END
    
    word = extract_word(update.message.text)
    if not word:
        await check_then_send_message(context, user, 'Invalid word. Try again or press Cancel.', type="Ban Receive", reply_markup=keyboards.cancel_kb())
        return ASK_BAN_WORD
    await add_ban_word(user, word)
    await check_then_send_message(context, user, 'Succesfully banned ' + word + "! You won't receive any message that includes it.", type="Ban")
    return ConversationHandler.END


async def cancel_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await _answer_cb(update) if update.callback_query else None
    await check_then_send_message(context, user, 'Cancelled.', type="Cancel")
    return ConversationHandler.END


# Inline menu callbacks
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data
    user = update.effective_user
    await new_user(user)
    await _answer_cb(update)

    # Main menu
    if data == 'menu_main':
        await _show_main_menu(update, context)
        return
    if data == 'menu_help':
        kb = keyboards.help_menu_kb(user in admins, user in mods)
        await storage.log_interaction(user.id, 'callback', 'menu_help')
        try:
            await query.message.edit_text(msg_tpl.help_text_interactive(), reply_markup=kb)
        except Exception:
            await query.message.reply_text(msg_tpl.help_text_interactive(), reply_markup=kb)
        return
    # menu_track is handled by ConversationHandler entry point
    if data == 'menu_view_tracked':
        words = sorted(list(await storage.get_tracked_words(user.id)))
        page = 1
        items, page, total_pages = _paginate_list(words, page)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='tracked')
        await storage.log_interaction(user.id, 'callback', 'menu_view_tracked')
        try:
            await query.message.edit_text('Your tracked words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your tracked words:', reply_markup=kb)
        return
    if data == 'menu_banned':
        words = sorted(list(await storage.get_banned_words(user.id)))
        page = 1
        items, page, total_pages = _paginate_list(words, page)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='banned')
        await storage.log_interaction(user.id, 'callback', 'menu_banned')
        try:
            await query.message.edit_text('Your banned words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your banned words:', reply_markup=kb)
        return

    # Tracked list pagination and actions
    if data.startswith('tracked:page:'):
        try:
            page = int(data.split(':')[-1])
        except Exception:
            page = 1
        words = sorted(list(await storage.get_tracked_words(user.id)))
        items, page, total_pages = _paginate_list(words, page)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='tracked')
        try:
            await query.message.edit_text('Your tracked words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your tracked words:', reply_markup=kb)
        return
    if data.startswith('tracked:select:'):
        word = data.split(':')[-1]
        history = await storage.get_message_history(word)
        detail = msg_tpl.word_detail_text(word, 0.0, len(history))
        kb = keyboards.word_detail_kb(word, base='tracked')
        try:
            await query.message.edit_text(detail, reply_markup=kb)
        except Exception:
            await query.message.reply_text(detail, reply_markup=kb)
        return
    if data == 'tracked:back':
        words = sorted(list(await storage.get_tracked_words(user.id)))
        items, page, total_pages = _paginate_list(words, 1)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='tracked')
        try:
            await query.message.edit_text('Your tracked words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your tracked words:', reply_markup=kb)
        return
    if data == 'tracked:clear_all':
        words = await storage.get_tracked_words(user.id)
        await storage.log_interaction(user.id, 'callback', 'tracked:clear_all')
        kb = keyboards.confirm_clear_kb('tracked')
        try:
            await query.message.edit_text(msg_tpl.confirm_clear_text('tracked', len(words)), reply_markup=kb)
        except Exception:
            await query.message.reply_text(msg_tpl.confirm_clear_text('tracked', len(words)), reply_markup=kb)
        return
    if data == 'tracked:clear_confirm':
        await storage.remove_all_tracked_words(user.id)
        await storage.log_interaction(user.id, 'action', 'clear_all_tracked')
        await query.message.reply_text("✅ All tracked words have been cleared.", reply_markup=keyboards.back_button('menu_main'))
        return
    if data == 'tracked:clear_cancel':
        words = sorted(list(await storage.get_tracked_words(user.id)))
        items, page, total_pages = _paginate_list(words, 1)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='tracked')
        try:
            await query.message.edit_text('Your tracked words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your tracked words:', reply_markup=kb)
        return
    if data.startswith('tracked:stop:'):
        word = data.split(':')[-1]
        await storage.remove_tracked_word(user.id, word)
        await query.message.reply_text(f"Stopped tracking '{word}'.", reply_markup=keyboards.back_button('menu_view_tracked'))
        return
    if data.startswith('tracked:history:'):
        word = data.split(':')[-1]
        history = await storage.get_message_history(word)
        try:
            await query.message.edit_text(msg_tpl.format_history(word, history), reply_markup=keyboards.back_button('tracked:back'))
        except Exception:
            await query.message.reply_text(msg_tpl.format_history(word, history), reply_markup=keyboards.back_button('tracked:back'))
        return

    # Banned list pagination and actions
    if data.startswith('banned:page:'):
        try:
            page = int(data.split(':')[-1])
        except Exception:
            page = 1
        words = sorted(list(await storage.get_banned_words(user.id)))
        items, page, total_pages = _paginate_list(words, page)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='banned')
        try:
            await query.message.edit_text('Your banned words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your banned words:', reply_markup=kb)
        return
    if data.startswith('banned:select:'):
        word = data.split(':')[-1]
        try:
            await query.message.edit_text(f"Banned word: {word}", reply_markup=keyboards.banned_detail_kb(word))
        except Exception:
            await query.message.reply_text(f"Banned word: {word}", reply_markup=keyboards.banned_detail_kb(word))
        return
    if data == 'banned:back':
        words = sorted(list(await storage.get_banned_words(user.id)))
        items, page, total_pages = _paginate_list(words, 1)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='banned')
        try:
            await query.message.edit_text('Your banned words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your banned words:', reply_markup=kb)
        return
    if data == 'banned:clear_all':
        words = await storage.get_banned_words(user.id)
        await storage.log_interaction(user.id, 'callback', 'banned:clear_all')
        kb = keyboards.confirm_clear_kb('banned')
        try:
            await query.message.edit_text(msg_tpl.confirm_clear_text('banned', len(words)), reply_markup=kb)
        except Exception:
            await query.message.reply_text(msg_tpl.confirm_clear_text('banned', len(words)), reply_markup=kb)
        return
    if data == 'banned:clear_confirm':
        await storage.remove_all_banned_words(user.id)
        await storage.log_interaction(user.id, 'action', 'clear_all_banned')
        await query.message.reply_text("✅ All banned words have been cleared.", reply_markup=keyboards.back_button('menu_main'))
        return
    if data == 'banned:clear_cancel':
        words = sorted(list(await storage.get_banned_words(user.id)))
        items, page, total_pages = _paginate_list(words, 1)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='banned')
        try:
            await query.message.edit_text('Your banned words:', reply_markup=kb)
        except Exception:
            await query.message.reply_text('Your banned words:', reply_markup=kb)
        return
    if data.startswith('banned:remove:'):
        word = data.split(':')[-1]
        await storage.remove_banned_word(user.id, word)
        await query.message.reply_text(f"Unbanned '{word}'.", reply_markup=keyboards.back_button('menu_banned'))
        return

    # Help menu actions
    if data == 'help:stats':
        tracked = await storage.get_tracked_words(user.id)
        banned = await storage.get_banned_words(user.id)
        stats_text = f"📊 Your Statistics\n\n📝 Tracked words: {len(tracked)}\n🚫 Banned words: {len(banned)}"
        await query.message.reply_text(stats_text, reply_markup=keyboards.back_button('menu_help'))
        return
    if data == 'help:about':
        await query.message.reply_text(
            'Otaniemi Buy/Sell Tracker Bot\n'
            'Miquel Torner Viñals\n'
            'Bernat Borràs Civil\n'
            'Source code: https://github.com/miquelt9/otaniemitrackerbot',
            reply_markup=keyboards.back_button('menu_help')
        )
        return
    
    # Admin panel
    if data == 'menu_admin' or data == 'admin:panel':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied. Admin privileges required.")
            return
        await storage.log_interaction(user.id, 'callback', 'admin:panel')
        try:
            await query.message.edit_text(msg_tpl.admin_panel_text(), reply_markup=keyboards.admin_panel_kb())
        except Exception:
            await query.message.reply_text(msg_tpl.admin_panel_text(), reply_markup=keyboards.admin_panel_kb())
        return
    
    if data == 'admin:users':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        num_users = await storage.count_all_users()
        active_users = await storage.count_active_users()
        await query.message.reply_text(
            f"👥 User Statistics\n\n"
            f"Total users: {num_users}\n"
            f"Active users: {active_users}",
            reply_markup=keyboards.back_button('admin:panel')
        )
        return
    
    if data == 'admin:analytics':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        await storage.log_interaction(user.id, 'callback', 'admin:analytics')
        try:
            await query.message.edit_text("📊 Analytics Dashboard", reply_markup=keyboards.analytics_menu_kb(True))
        except Exception:
            await query.message.reply_text("📊 Analytics Dashboard", reply_markup=keyboards.analytics_menu_kb(True))
        return
    
    if data == 'admin:feedback':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        try:
            with open("feedback.txt", 'r') as f:
                feedback = f.read().strip()
                if feedback:
                    await query.message.reply_text(
                        f"📝 User Feedback:\n\n{feedback}",
                        reply_markup=keyboards.feedback_actions_kb()
                    )
                else:
                    await query.message.reply_text("No feedback available.", reply_markup=keyboards.back_button('admin:panel'))
        except Exception:
            await query.message.reply_text("Error reading feedback.", reply_markup=keyboards.back_button('admin:panel'))
        return
    
    if data == 'admin:broadcast':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        try:
            await query.message.edit_text(msg_tpl.broadcast_menu_text(), reply_markup=keyboards.broadcast_menu_kb())
        except Exception:
            await query.message.reply_text(msg_tpl.broadcast_menu_text(), reply_markup=keyboards.broadcast_menu_kb())
        return
    
    if data == 'admin:save':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        await storage.save_if_needed(force=True)
        await query.message.reply_text("💾 Database saved successfully!", reply_markup=keyboards.back_button('admin:panel'))
        return
    
    if data == 'admin:export':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        try:
            await query.message.reply_text("📊 Preparing database files...")
            
            # Create timestamp for filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Send db.pkl (tracked words)
            try:
                with open("db.pkl", "rb") as f:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=f,
                        filename=f"db_{timestamp}.pkl",
                        caption="📊 Tracked Words Database (db.pkl)"
                    )
            except FileNotFoundError:
                await query.message.reply_text("⚠️ db.pkl not found")
            
            # Send db2.pkl (users by word)
            try:
                with open("db2.pkl", "rb") as f:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=f,
                        filename=f"db2_{timestamp}.pkl",
                        caption="📊 Users by Word Database (db2.pkl)"
                    )
            except FileNotFoundError:
                await query.message.reply_text("⚠️ db2.pkl not found")
            
            # Send dbb.pkl (banned words)
            try:
                with open("dbb.pkl", "rb") as f:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=f,
                        filename=f"dbb_{timestamp}.pkl",
                        caption="📊 Banned Words Database (dbb.pkl)"
                    )
            except FileNotFoundError:
                await query.message.reply_text("⚠️ dbb.pkl not found")
            
            # Send history.pkl (message history)
            try:
                with open("history.pkl", "rb") as f:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=f,
                        filename=f"history_{timestamp}.pkl",
                        caption="📊 Message History Database (history.pkl)"
                    )
            except FileNotFoundError:
                await query.message.reply_text("⚠️ history.pkl not found")
            
            await query.message.reply_text("✅ Database files exported successfully!", reply_markup=keyboards.back_button('admin:panel'))
            await storage.log_interaction(user.id, 'callback', 'admin:export')
            logging.info(f"Database files exported by admin {user.id} ({user.first_name})")
            
        except Exception as e:
            await query.message.reply_text(f"❌ Export failed: {e}", reply_markup=keyboards.back_button('admin:panel'))
            logging.error(f"Database export failed: {e}")
        return
    
    if data == 'feedback:clear':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        with open("feedback.txt", 'w') as f:
            pass
        await query.message.reply_text("🗑️ Feedback cleared.", reply_markup=keyboards.back_button('admin:panel'))
        return
    
    # Mod panel
    if data == 'menu_mod' or data == 'mod:panel':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied. Moderator privileges required.")
            return
        await storage.log_interaction(user.id, 'callback', 'mod:panel')
        try:
            await query.message.edit_text(msg_tpl.mod_panel_text(), reply_markup=keyboards.mod_panel_kb())
        except Exception:
            await query.message.reply_text(msg_tpl.mod_panel_text(), reply_markup=keyboards.mod_panel_kb())
        return
    
    if data == 'mod:users':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        num_users = await storage.count_all_users()
        active_users = await storage.count_active_users()
        await query.message.reply_text(
            f"👥 User Statistics\n\n"
            f"Total users: {num_users}\n"
            f"Active users: {active_users}",
            reply_markup=keyboards.back_button('mod:panel')
        )
        return
    
    if data == 'mod:rankings':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        sorted_ranking = await storage.rank_tracked_words()
        rank_text = "📊 Word Rankings\n\n"
        for count, word in sorted_ranking[:10]:
            rank_text += f"{word} - {count} users\n"
        await query.message.reply_text(rank_text, reply_markup=keyboards.back_button('mod:panel'))
        return
    
    if data == 'mod:feedback':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        try:
            with open("feedback.txt", 'r') as f:
                feedback = f.read().strip()
                if feedback:
                    await query.message.reply_text(f"📝 User Feedback:\n\n{feedback}", reply_markup=keyboards.back_button('mod:panel'))
                else:
                    await query.message.reply_text("No feedback available.", reply_markup=keyboards.back_button('mod:panel'))
        except Exception:
            await query.message.reply_text("Error reading feedback.", reply_markup=keyboards.back_button('mod:panel'))
        return
    
    if data == 'mod:save':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        await storage.save_if_needed(force=True)
        await query.message.reply_text("💾 Database saved successfully!", reply_markup=keyboards.back_button('mod:panel'))
        return
    
    # Analytics
    if data == 'analytics:today':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        stats = await storage.get_daily_stats()
        text = msg_tpl.analytics_summary_text(stats, "Today")
        is_admin = user in admins
        await query.message.reply_text(text, reply_markup=keyboards.analytics_menu_kb(is_admin))
        return
    
    if data == 'analytics:week':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        stats = await storage.get_analytics_summary(7)
        text = msg_tpl.analytics_summary_text(stats, "Last 7 Days")
        is_admin = user in admins
        await query.message.reply_text(text, reply_markup=keyboards.analytics_menu_kb(is_admin))
        return
    
    if data == 'analytics:month':
        if user not in mods and user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        stats = await storage.get_analytics_summary(30)
        text = msg_tpl.analytics_summary_text(stats, "Last 30 Days")
        is_admin = user in admins
        await query.message.reply_text(text, reply_markup=keyboards.analytics_menu_kb(is_admin))
        return
    
    if data == 'analytics:export':
        if user not in admins:
            await query.message.reply_text("⛔ Access denied.")
            return
        notif_path, interact_path = await storage.export_analytics_csv()
        try:
            await context.bot.send_document(chat_id=user.id, document=open(notif_path, 'rb'), filename='notifications.csv')
            await context.bot.send_document(chat_id=user.id, document=open(interact_path, 'rb'), filename='interactions.csv')
            await query.message.reply_text("📥 Analytics data exported!", reply_markup=keyboards.analytics_menu_kb(True))
        except Exception as e:
            await query.message.reply_text(f"Error exporting data: {e}", reply_markup=keyboards.analytics_menu_kb(True))
        return

    # Notification actions
    if data.startswith('notif:history:'):
        word = data.split(':')[-1]
        history = await storage.get_message_history(word)
        await query.message.reply_text(msg_tpl.format_history(word, history))
        return

def read_files():
    global TOKEN
    try:
        TOKEN = open('token.txt').read().strip()
    except Exception as e:
        logging.error("Error on reading TOKEN, make sure the file token.txt exists.")

    global BASE_URL
    BASE_URL = f'https://api.telegram.org/bot{TOKEN}'

    global PSWD_ADM
    try:
        PSWD_ADM = open('pswd.adm').read().strip()
    except Exception as e:
        logging.error("Error on reading PSWD_ADM, make sure the file pswd.adm exists.")

    global PSWD_MOD
    try:
        PSWD_MOD = open('pswd.mod').read().strip()
    except Exception as e:
        logging.error("Error on reading PSWD_MOD, make sure the file pswd.mod exists.")

    global GID1 # Otaniemi buy/sell group ID
    try:
        GID1 = open('group1_id.txt').read().strip()  
    except Exception as e:
        GID1 = 0
        logging.error("Error on reading GID1, make sure the file group1_id.txt exists")

    global GROUP_LINK1 # Otaniemi buy/sell group ID
    try:
        GROUP_LINK1 = open('group1_link.txt').read().strip()  
    except Exception as e:
        GROUP_LINK1 = "error_on_bot"
        logging.error("Error on reading GROUP_LINK1, make sure the file group1_link.txt exists")

    global GID2 # Otaniemi buy/sell group ID
    try:
        GID2 = open('group2_id.txt').read().strip()  
    except Exception as e:
        GID2 = 0
        logging.error("Error on reading GID2, make sure the file group2_id.txt exists")

    global GROUP_LINK2 # Otaniemi buy/sell group ID
    try:
        GROUP_LINK2 = open('group2_link.txt').read().strip()  
    except Exception as e:
        GROUP_LINK2 = "error_on_bot"
        logging.error("Error on reading GROUP_LINK2, make sure the file group2_link.txt exists")



async def load_db_async():
    await storage.init_storage()

async def new_user(user):
    """Ensure user has default structures in storage."""
    await storage.ensure_user(user.id)

async def add_track_word(user, word):
    await storage.add_tracked_word(user.id, word)


async def remove_track_word(user, word):
    await storage.remove_tracked_word(user.id, word)


async def remove_all_track_words(user):
    await storage.remove_all_tracked_words(user.id)


async def get_tracked_words(user):
    return await storage.get_tracked_words(user.id)


async def get_users_who_track(word):
    return await storage.users_tracking(word)

# Banned words methods


async def add_ban_word(user, word):
    await storage.add_banned_word(user.id, word)


async def remove_ban_word(user, word):
    await storage.remove_banned_word(user.id, word)


async def remove_all_ban_words(user):
    await storage.remove_all_banned_words(user.id)


async def get_banned_words(userId):
    return await storage.get_banned_words(userId)

"""General methods (migrated to utils)."""


async def check_if_message_to_group(context, message, user):
    if int(message.chat_id) == int(GID1) or int(message.chat_id) == int(GID2):
        await check_then_send_message(context, user, "To prevent message influx write me directly @otaniemitrackerbot")
        return True
    elif message.chat_id < 0:
        await check_then_send_message(context, user, "Please write directly to the bot (@otaniemitrackerbot)")
        return True
    return False


def check_strings_not_in_list(input_list, banned_list):
    for word in input_list:
        if word in banned_list:
            return False
    return True

async def check_then_send_message(context, user, message, notification=None, user_id=None, type="Default", reply_markup=None, word=None):
    target_id = user_id if user_id else (user.id if user else None)
    if user_id == None:
        try:
            await context.bot.send_message(user.id, str(message), disable_notification=notification, reply_markup=reply_markup)
            logging.info("Message (type: " + type + ")\n'" + str(message) + "'\n successfully sent to user " + str(user.id))
            # Log interaction for non-notification messages
            if type not in ["Detection (Photo)", "Detection (Album)"]:
                await storage.log_interaction(user.id, 'bot_message', type)
        except Exception as e:
            logging.error("Something went wrong when sending '" + str(message) + "' to user " + str(user))
            logging.error("Catches exception: " + str(e))
    else:
        try:
            await context.bot.send_message(user_id, str(message), disable_notification=notification, reply_markup=reply_markup)
            logging.info("Message (type: " + type + ")\n'" + str(message) + "'\n successfully sent to user " + str(user_id))
            # Log notification if it's a detection
            if type in ["Detection (Photo)", "Detection (Album)"] and word:
                msg_type = "Marketplace" if "interested" in str(message) else "Giveaway"
                await storage.log_notification(user_id, word, msg_type, 'success')
        except Exception as e:
            logging.error("Something went wrong when sending '" + str(message) + "' to user " + str(user_id) + " (tracked word detected)")
            logging.error("Catches exception: " + str(e))
            # Log failed notification
            if type in ["Detection (Photo)", "Detection (Album)"] and word:
                msg_type = "Marketplace" if "interested" in str(message) else "Giveaway"
                await storage.log_notification(user_id, word, msg_type, 'failed')

### Bot commands ###

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await new_user(user)
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    # Check if message is too old (10 minutes)
    if _is_message_too_old(message, max_age_minutes=5):
        return

    await storage.log_interaction(user.id, 'command', '/start')
    name = user.first_name
    
    # Send intro message first
    await check_then_send_message(context, user, msg_tpl.bot_intro_message(GROUP_LINK1, GROUP_LINK2), type="Bot Intro")
    
    # Send welcome and menu as separate message
    kb = keyboards.main_menu_kb(user in admins, user in mods)
    await check_then_send_message(context, user, f"Welcome {name}!\n\n" + msg_tpl.main_menu_text(), type="Start", reply_markup=kb)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return    

    response_time = float(time.time()) - message.date.timestamp()

    await check_then_send_message(context, user, 'Pong! - time to reply: ' + str(int(response_time*1000)) + ' ms', type="Ping")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return
    
    # Check if message is too old (10 minutes)
    if _is_message_too_old(message, max_age_minutes=5):
        return
    
    await storage.log_interaction(user.id, 'command', '/help')
    kb = keyboards.help_menu_kb(user in admins, user in mods)
    await check_then_send_message(context, user, msg_tpl.help_text_interactive(), type="Help", reply_markup=kb)




async def author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    await check_then_send_message(context, user, 'Otaniemi Buy/Sell Tracker Bot\
                                    \n Miquel Torner Viñals\
                                    \n Bernat Borràs Civil\
                                    \n Source code and contributions: https://github.com/miquelt9/otaniemitrackerbot', type="Author")

## Tracking words commands ##


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text.lower()
    splitted_input = user_input.split()

    if (len(splitted_input) == 2):
        user_word = extract_word(splitted_input[1])
        if user_word:
            await add_track_word(user, user_word)
            await check_then_send_message(context, user, 'Succesfully tracking ' + user_word, type="Track")
        else:
            await check_then_send_message(context, user, 'Error: Add just one word after:\n/track "word"', type="Track")
    else:
        await check_then_send_message(context, user, 'Error: Add just one word after:\
                                        \n/track "word"', type="Track")


async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await storage.log_interaction(user.id, 'command', '/untrack')
    
    tracked_words = await get_tracked_words(user)

    if tracked_words:
        words = sorted(list(tracked_words))
        items, page, total_pages = _paginate_list(words, 1)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='tracked')
        await check_then_send_message(context, user, '🛑 Select a word to stop tracking:', type="Untrack", reply_markup=kb)
    else:
        await check_then_send_message(context, user, 'You are not tracking any words right now', type="Untrack")






async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await remove_all_track_words(user)
    await check_then_send_message(context, user, "You are not longer tracking any words", type="Track")


## Banning words methods ##

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text.lower()
    splitted_input = user_input.split()

    if (len(splitted_input) == 2):
        user_word = extract_word(splitted_input[1])
        if user_word:
            await add_ban_word(user, user_word)
            await check_then_send_message(context, user, 'Succesfully banned ' + user_word + "! You won't receive any message that includes it.", type="Ban")
        else:
            await check_then_send_message(context, user, 'Error: Add just one word after:\n/ban "word"', type="Ban")
    else:
        await check_then_send_message(context, user, 'Error: Add just one word after:\
                                        \n/ban "word"', type="Ban")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await storage.log_interaction(user.id, 'command', '/unban')
    
    banned_words = await get_banned_words(user.id)

    if banned_words:
        words = sorted(list(banned_words))
        items, page, total_pages = _paginate_list(words, 1)
        kb = keyboards.words_list_with_clear_kb(items, page, total_pages, base='banned')
        await check_then_send_message(context, user, '✅ Select a word to unban:', type="Unban", reply_markup=kb)
    else:
        await check_then_send_message(context, user, "There aren't any banned words", type="Unban")






### ADMIN AND MOD COMMANDS ###

async def show_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        user_input = message.text
        splitted_input = user_input.split()

        if (len(splitted_input) == 2):
            users = await get_users_who_track(extract_word(splitted_input[1]))
            await check_then_send_message(context, user, 'Current users who are tracking ' + splitted_input[1] + ': ' + str(users), type="Show Word")
        else:
            await check_then_send_message(context, user, 'Error on /show_words', type="Show Word")


async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    admin = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, admin):
        return
    
    if admin in admins or admin in mods:
        num_users = await storage.count_all_users()
        active_users = await storage.count_active_users()
        await check_then_send_message(context, admin, 'There are currently ' + str(active_users) + " active users out of " + str(num_users) + ' registered.', type="User Count")


async def rank_tracked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        sorted_ranking = await storage.rank_tracked_words()
        rank_text = ""
        for count, word in sorted_ranking:
            rank_text += "\n" + str(word) + " - " + str(count) + " ppl"
        await check_then_send_message(context, user, "Ranking the words tracked by people:" + rank_text, type="Rank Tracked")


async def save_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        await storage.save_if_needed(force=True)
        await check_then_send_message(context, user, "The database was succesfully saved!", type="Save")


async def send_everyone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        splitted_input = message.text.split()
        admin_message = ' '.join(splitted_input[1:])
        for uid in await storage.get_all_user_ids():
            await check_then_send_message(context, None, admin_message, user_id=uid, type="Send Everyone")


async def send_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        splitted_input = message.text.split()
        admin_message = ' '.join(splitted_input[1:])
        # active users are those with tracked words
        for uid in await storage.get_all_user_ids():
            if (await storage.get_tracked_words(uid)):
                await check_then_send_message(context, None, admin_message, user_id=uid, type="Send Active")


async def show_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        await check_then_send_message(context, user, 'Current admins are: ' + str(admins), type="Show Admins")


async def show_mods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        await check_then_send_message(context, user, 'Current mods are: ' + str(mods), type="Show Mods")


async def get_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text
    splitted_input = user_input.split()

    if user in admins:
        if len(splitted_input) == 2:
            await check_then_send_message(context, user, 'You are already a superuser.', type="Get Admin")

    else:
        if (len(splitted_input) == 2):
            if splitted_input[1] == PSWD_ADM:
                for admin_user in admins:
                    await check_then_send_message(context, admin_user, 'A new user '+str(user.full_name)+' got admin rights! (@'+str(user.username)+')', type="Get Admin Notification")

                await check_then_send_message(context, user, 'You got superuser rights', type="Get Admin")
                admins.add(user)
                mods.add(user)


async def get_mod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text
    splitted_input = user_input.split()

    if user in mods:
        if len(splitted_input) == 2:
            await check_then_send_message(context, user, 'You are already a mod.', type="Get Mod")

    else:
        if (len(splitted_input) == 2):
            if splitted_input[1] == PSWD_MOD:
                for admin_user in admins:
                    await check_then_send_message(context, admin_user, 'A new user '+str(user.full_name)+' got mod rights! (@'+str(user.username)+')', type="Get Mod Notification")
                for mod_user in mods:
                    if mod_user not in admins:
                        await check_then_send_message(context, mod_user, 'A new user '+str(user.full_name)+' got mod rights! (@'+str(user.username)+')', type="Get Mod Notification")

                await check_then_send_message(context, user, 'You got mod rights', type="Get Mod")
                mods.add(user)


async def feedback_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    message = update.message
    
    # Handle callback query (from help menu button)
    if update.callback_query:
        await _answer_cb(update)
        await update.callback_query.message.reply_text(
            'Please send your feedback message:',
            reply_markup=keyboards.cancel_kb()
        )
        return ASK_FEEDBACK
    
    if message and await check_if_message_to_group(context, message, user):
        return ConversationHandler.END
    
    # If command has argument, process immediately
    text = message.text if message else ''
    parts = (text or '').split(maxsplit=1)
    if len(parts) == 2:
        feedback_text = parts[1].strip()
        if feedback_text:
            with open("feedback.txt", 'a') as file:
                file.write(feedback_text + "\n")
            await check_then_send_message(context, user, "Your feedback was successfully sent to the mods!", type="Feedback")
            return ConversationHandler.END
    
    # Ask for feedback
    await check_then_send_message(context, user, 'Please send your feedback message:', type="Feedback Ask", reply_markup=keyboards.cancel_kb())
    return ASK_FEEDBACK


async def feedback_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    feedback_text = update.message.text.strip()
    
    if not feedback_text:
        await check_then_send_message(context, user, 'Invalid feedback. Try again or press Cancel.', type="Feedback Receive", reply_markup=keyboards.cancel_kb())
        return ASK_FEEDBACK
    
    with open("feedback.txt", 'a') as file:
        file.write(feedback_text + "\n")
    
    await check_then_send_message(context, user, "Your feedback was successfully sent to the mods!", type="Feedback")
    return ConversationHandler.END


# Conversation: Broadcast
async def broadcast_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    
    # Check admin privileges
    if user not in admins:
        if update.callback_query:
            await _answer_cb(update)
            await update.callback_query.message.reply_text("⛔ Access denied. Admin privileges required.")
        return ConversationHandler.END
    
    # Determine broadcast type from callback data
    if update.callback_query:
        query = update.callback_query
        await _answer_cb(update)
        
        broadcast_type = 'everyone' if query.data == 'broadcast:everyone' else 'active'
        context.user_data['broadcast_type'] = broadcast_type
        
        recipient_text = "all users" if broadcast_type == 'everyone' else "active users only"
        await query.message.reply_text(
            f'📢 Broadcasting to {recipient_text}\n\nPlease send the message you want to broadcast:',
            reply_markup=keyboards.cancel_kb()
        )
        return ASK_BROADCAST_MESSAGE
    
    return ConversationHandler.END


async def broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await new_user(user)
    
    # Check admin privileges
    if user not in admins:
        await check_then_send_message(context, user, "⛔ Access denied.")
        return ConversationHandler.END
    
    broadcast_message = update.message.text.strip()
    
    if not broadcast_message:
        await check_then_send_message(context, user, 'Invalid message. Try again or press Cancel.', type="Broadcast Receive", reply_markup=keyboards.cancel_kb())
        return ASK_BROADCAST_MESSAGE
    
    broadcast_type = context.user_data.get('broadcast_type', 'everyone')
    
    # Send to all users or active users
    sent_count = 0
    failed_count = 0
    
    if broadcast_type == 'everyone':
        user_ids = await storage.get_all_user_ids()
        recipient_text = "all users"
    else:  # active
        user_ids = []
        for uid in await storage.get_all_user_ids():
            if await storage.get_tracked_words(uid):
                user_ids.append(uid)
        recipient_text = "active users"
    
    await check_then_send_message(context, user, f"📤 Sending broadcast to {len(user_ids)} {recipient_text}...", type="Broadcast Status")
    
    for uid in user_ids:
        try:
            await check_then_send_message(context, None, broadcast_message, user_id=uid, type="Broadcast")
            sent_count += 1
        except Exception:
            failed_count += 1
    
    # Clean up user data
    context.user_data.pop('broadcast_type', None)
    
    result_message = f"✅ Broadcast complete!\n\n📊 Sent: {sent_count}\n❌ Failed: {failed_count}"
    await check_then_send_message(context, user, result_message, type="Broadcast Complete", reply_markup=keyboards.back_button('admin:panel'))
    
    return ConversationHandler.END


async def see_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    file_path = "feedback.txt"

    if user in admins or user in mods:
        with open(file_path, 'r') as file:
            for line in file:
                txt = line.strip()
                await check_then_send_message(context, user, 'Someone said: ' + txt, type="See Feedback")


async def clear_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    file_path = "feedback.txt"

    if user in admins:
        with open(file_path, 'w') as file:
            pass
            await check_then_send_message(context, user, "The feedback file was cleared", type="Clear Feedback")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return
    
    if user not in admins:
        await check_then_send_message(context, user, "⛔ Access denied. Admin privileges required.")
        return
    
    await storage.log_interaction(user.id, 'command', '/admin_panel')
    await check_then_send_message(context, user, msg_tpl.admin_panel_text(), type="Admin Panel", reply_markup=keyboards.admin_panel_kb())


async def mod_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return
    
    if user not in mods and user not in admins:
        await check_then_send_message(context, user, "⛔ Access denied. Moderator privileges required.")
        return
    
    await storage.log_interaction(user.id, 'command', '/mod_panel')
    await check_then_send_message(context, user, msg_tpl.mod_panel_text(), type="Mod Panel", reply_markup=keyboards.mod_panel_kb())


async def export_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export database files for backup (admin only)."""
    user = update.effective_user
    await new_user(user)
    
    if user not in admins:
        await check_then_send_message(context, user, "⛔ Access denied. Admin privileges required.")
        return
    
    try:
        await check_then_send_message(context, user, "📊 Preparing database files...", type="Export Database")
        
        # Create timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Send db.pkl (tracked words)
        try:
            with open("db.pkl", "rb") as f:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=f,
                    filename=f"db_{timestamp}.pkl",
                    caption="📊 Tracked Words Database (db.pkl)"
                )
        except FileNotFoundError:
            await check_then_send_message(context, user, "⚠️ db.pkl not found", type="Export Database")
        
        # Send db2.pkl (users by word)
        try:
            with open("db2.pkl", "rb") as f:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=f,
                    filename=f"db2_{timestamp}.pkl",
                    caption="📊 Users by Word Database (db2.pkl)"
                )
        except FileNotFoundError:
            await check_then_send_message(context, user, "⚠️ db2.pkl not found", type="Export Database")
        
        # Send dbb.pkl (banned words)
        try:
            with open("dbb.pkl", "rb") as f:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=f,
                    filename=f"dbb_{timestamp}.pkl",
                    caption="📊 Banned Words Database (dbb.pkl)"
                )
        except FileNotFoundError:
            await check_then_send_message(context, user, "⚠️ dbb.pkl not found", type="Export Database")
        
        # Send history.pkl (message history)
        try:
            with open("history.pkl", "rb") as f:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=f,
                    filename=f"history_{timestamp}.pkl",
                    caption="📊 Message History Database (history.pkl)"
                )
        except FileNotFoundError:
            await check_then_send_message(context, user, "⚠️ history.pkl not found", type="Export Database")
        
        await check_then_send_message(context, user, "✅ Database files exported successfully!", type="Export Database")
        await storage.log_interaction(user.id, 'command', '/export_database')
        logging.info(f"Database files exported by admin {user.id} ({user.first_name})")
        
    except Exception as e:
        await check_then_send_message(context, user, f"❌ Export failed: {e}", type="Export Database")
        logging.error(f"Database export failed: {e}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    message = update.message

    # Check if message is too old (10 minutes)
    if _is_message_too_old(message, max_age_minutes=5):
        return

    already_sent = set()
    processed_words = set()  # Track which words have been processed for history

    if int(message.chat_id) == int(GID1):   # Message received through group1 (buy/sell otaniemi)
        if message.photo:
            # Handle single photos
            caption = message.caption or ''
            splitted_input = remove_punctuation(caption.lower()).split()
            sender_username = message.from_user.username if message.from_user.username else ""
            message_link = f"{GROUP_LINK1}/{message.message_id}"
            for word in splitted_input:
                users = await storage.users_tracking(word)
                if users:
                    # Update message history only once per word
                    if word not in processed_words:
                        await storage.update_message_history(word, message_link, caption or '', float(message.date.timestamp()), 'Marketplace')
                        processed_words.add(word)
                    
                    for user_id in users:
                        banned = await storage.get_banned_words(int(user_id))
                        if check_strings_not_in_list(splitted_input, banned):
                            if user_id not in already_sent:
                                notification_message = msg_tpl.notification_text_detected(word, message_link, "You might be interested in this message")
                                await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Photo)", reply_markup=keyboards.notification_actions_kb(word), word=word)
                                already_sent.add(user_id)
        elif message.media_group_id:
            # Handle media groups (albums)
            media_group = await context.bot.get_media_group(message.media_group_id)
            for media in media_group:
                if media.caption:
                    caption = media.caption or ''
                    splitted_input = remove_punctuation(
                        caption.lower()).split()
                    sender_username = message.from_user.username if message.from_user.username else ""
                    message_link = f"{GROUP_LINK1}/{message.message_id}"
                    for word in splitted_input:
                        users = await storage.users_tracking(word)
                        if users:
                            # Update message history only once per word
                            if word not in processed_words:
                                await storage.update_message_history(word, message_link, caption or '', float(message.date.timestamp()), 'Marketplace')
                                processed_words.add(word)
                            
                            for user_id in users:
                                banned = await storage.get_banned_words(int(user_id))
                                if check_strings_not_in_list(splitted_input, banned):
                                    if user_id not in already_sent:
                                        notification_message = msg_tpl.notification_text_detected(word, message_link, "You might be interested in this message")
                                        await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Album)", reply_markup=keyboards.notification_actions_kb(word), word=word)
                                        already_sent.add(user_id)


    if int(message.chat_id) == int(GID2):   # Message received through group2 (giveaway otaniemi)
        if message.photo:
            # Handle single photos
            caption = message.caption or ''
            splitted_input = remove_punctuation(caption.lower()).split()
            sender_username = message.from_user.username if message.from_user.username else ""
            message_link = f"{GROUP_LINK2}/{message.message_id}"
            for word in splitted_input:
                users = await storage.users_tracking(word)
                if users:
                    # Update message history only once per word
                    if word not in processed_words:
                        await storage.update_message_history(word, message_link, caption or '', float(message.date.timestamp()), 'Giveaway')
                        processed_words.add(word)
                    
                    for user_id in users:
                        banned = await storage.get_banned_words(int(user_id))
                        if check_strings_not_in_list(splitted_input, banned):
                            if user_id not in already_sent:
                                notification_message = msg_tpl.notification_text_detected(word, message_link, "Free stuff is available")
                                await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Photo)", reply_markup=keyboards.notification_actions_kb(word), word=word)
                                already_sent.add(user_id)
        elif message.media_group_id:
            # Handle media groups (albums)
            media_group = await context.bot.get_media_group(message.media_group_id)
            for media in media_group:
                if media.caption:
                    caption = media.caption or ''
                    splitted_input = remove_punctuation(
                        caption.lower()).split()
                    sender_username = message.from_user.username if message.from_user.username else ""
                    message_link = f"{GROUP_LINK2}/{message.message_id}"
                    for word in splitted_input:
                        users = await storage.users_tracking(word)
                        if users:
                            # Update message history only once per word
                            if word not in processed_words:
                                await storage.update_message_history(word, message_link, caption or '', float(message.date.timestamp()), 'Giveaway')
                                processed_words.add(word)
                            
                            for user_id in users:
                                banned = await storage.get_banned_words(int(user_id))
                                if check_strings_not_in_list(splitted_input, banned):
                                    if user_id not in already_sent:
                                        notification_message = msg_tpl.notification_text_detected(word, message_link, "Free stuff is available")
                                        await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Album)", reply_markup=keyboards.notification_actions_kb(word), word=word)
                                        already_sent.add(user_id)

def main():
    read_files()
    # We'll initialize storage during application startup


    async def _post_init(app):
        await storage.init_storage()
        # schedule periodic save via JobQueue every 30s
        if app.job_queue:
            app.job_queue.run_repeating(periodic_save_job, interval=30)
        else:
            logging.warning("Job queue not available. Install APScheduler to enable periodic saves.")

    # Build application and register the post-init coroutine
    app = ApplicationBuilder().token(TOKEN).post_init(_post_init).build()

    # Add handlers (same as before)
    app.add_handler(CommandHandler("author", author))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    # handled by conversation handler (track_entry)
    app.add_handler(CommandHandler("untrack", untrack))
    app.add_handler(CommandHandler("clear", clear))
    # handled by conversation handler (ban_entry)
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("show_word", show_word))
    app.add_handler(CommandHandler("user_count", user_count))
    app.add_handler(CommandHandler("rank_tracked", rank_tracked))
    app.add_handler(CommandHandler("rank_words", rank_tracked))
    app.add_handler(CommandHandler("save", save_db))
    app.add_handler(CommandHandler("send_everyone", send_everyone))
    app.add_handler(CommandHandler("send_active", send_active))
    app.add_handler(CommandHandler("get_admin", get_admin))
    app.add_handler(CommandHandler("get_mod", get_mod))
    app.add_handler(CommandHandler("show_admins", show_admins))
    app.add_handler(CommandHandler("show_mods", show_mods))
    app.add_handler(CommandHandler("see_feedback", see_feedback))
    app.add_handler(CommandHandler("check_feedback", see_feedback))
    app.add_handler(CommandHandler("clear_feedback", clear_feedback))
    app.add_handler(CommandHandler("admin_panel", admin_panel))
    app.add_handler(CommandHandler("mod_panel", mod_panel))
    app.add_handler(CommandHandler("export_database", export_database))

    # Conversation handlers
    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("track", track_entry),
            CallbackQueryHandler(track_entry, pattern="^menu_track$")
        ],
        states={
            ASK_TRACK_WORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), track_receive)]
        },
        fallbacks=[CallbackQueryHandler(cancel_any, pattern="^cancel$")],
        name="conv_track",
        persistent=False,
        per_chat=True,
        conversation_timeout=300,
    ))
    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("ban", ban_entry),
            CallbackQueryHandler(ban_entry, pattern="^banned:add$")
        ],
        states={
            ASK_BAN_WORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), ban_receive)]
        },
        fallbacks=[CallbackQueryHandler(cancel_any, pattern="^cancel$")],
        name="conv_ban",
        persistent=False,
        per_chat=True,
        conversation_timeout=300,
    ))
    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("feedback", feedback_entry),
            CommandHandler("rate", feedback_entry),
            CallbackQueryHandler(feedback_entry, pattern="^help:feedback$"),
        ],
        states={
            ASK_FEEDBACK: [MessageHandler(filters.TEXT & (~filters.COMMAND), feedback_receive)]
        },
        fallbacks=[CallbackQueryHandler(cancel_any, pattern="^cancel$")],
        name="conv_feedback",
        persistent=False,
        per_chat=True,
        conversation_timeout=300,
    ))
    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(broadcast_entry, pattern="^broadcast:(everyone|active)$")
        ],
        states={
            ASK_BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & (~filters.COMMAND), broadcast_receive)]
        },
        fallbacks=[CallbackQueryHandler(cancel_any, pattern="^cancel$")],
        name="conv_broadcast",
        persistent=False,
        per_chat=True,
        conversation_timeout=300,
    ))

    # Callback queries for menus and notifications
    app.add_handler(CallbackQueryHandler(on_callback))

    # A message handler for group messages and generic content (photos/captions)
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler))

    # Start the bot
    app.run_polling()



if __name__ == '__main__':
    main()
