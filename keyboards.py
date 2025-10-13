from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Callable, List, Tuple


def main_menu_kb(is_admin: bool, is_mod: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📝 Track Words", callback_data="menu_track")],
        [InlineKeyboardButton("👁 View Tracked Words", callback_data="menu_view_tracked")],
        [InlineKeyboardButton("🚫 Manage Banned Words", callback_data="menu_banned")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("🛡 Admin Panel", callback_data="menu_admin")])
    elif is_mod:
        buttons.append([InlineKeyboardButton("🛡 Mod Panel", callback_data="menu_mod")])
    return InlineKeyboardMarkup(buttons)


def back_button(cb: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=cb)]])


def pagination_kb(page: int, total_pages: int, base: str) -> InlineKeyboardMarkup:
    prev_cb = f"{base}:page:{page-1}" if page > 1 else "noop"
    next_cb = f"{base}:page:{page+1}" if page < total_pages else "noop"
    center = InlineKeyboardButton(f"Page {page}/{total_pages}", callback_data="noop")
    row = [InlineKeyboardButton("◀️ Prev", callback_data=prev_cb), center, InlineKeyboardButton("Next ▶️", callback_data=next_cb)]
    return InlineKeyboardMarkup([row, [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]])


def words_list_kb(words: List[str], page: int, total_pages: int, base: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for w in words:
        rows.append([InlineKeyboardButton(w, callback_data=f"{base}:select:{w}")])
    # add pagination row - use "noop" for disabled buttons
    prev_cb = f"{base}:page:{page-1}" if page > 1 else "noop"
    next_cb = f"{base}:page:{page+1}" if page < total_pages else "noop"
    center = InlineKeyboardButton(f"Page {page}/{total_pages}", callback_data="noop")
    rows.append([InlineKeyboardButton("◀️ Prev", callback_data=prev_cb), center, InlineKeyboardButton("Next ▶️", callback_data=next_cb)])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def word_detail_kb(word: str, base: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 Stop tracking", callback_data=f"{base}:stop:{word}")],
        [InlineKeyboardButton("🧾 See latest messages", callback_data=f"{base}:history:{word}")],
        [InlineKeyboardButton("⬅️ Back to list", callback_data=f"{base}:back")],
    ])


def notification_actions_kb(word: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Latest messages", callback_data=f"notif:history:{word}")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])


def banned_detail_kb(word: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Unban", callback_data=f"banned:remove:{word}")],
        [InlineKeyboardButton("⬅️ Back to list", callback_data="banned:back")],
    ])


def confirm_kb(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes", callback_data=f"confirm:{action}"), InlineKeyboardButton("❌ No", callback_data="cancel")]
    ])


def add_tracked_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Track a word", callback_data="menu_track")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
    ])


def add_banned_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Ban a word", callback_data="banned:add")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
    ])


def words_list_with_clear_kb(words: List[str], page: int, total_pages: int, base: str) -> InlineKeyboardMarkup:
    """Word list keyboard with 'Clear All' button."""
    rows: List[List[InlineKeyboardButton]] = []
    for w in words:
        rows.append([InlineKeyboardButton(w, callback_data=f"{base}:select:{w}")])
    
    # Clear all button
    if words:
        rows.append([InlineKeyboardButton("🗑️ Clear All", callback_data=f"{base}:clear_all")])
    
    # Pagination row - use "noop" for disabled buttons
    prev_cb = f"{base}:page:{page-1}" if page > 1 else "noop"
    next_cb = f"{base}:page:{page+1}" if page < total_pages else "noop"
    center = InlineKeyboardButton(f"Page {page}/{total_pages}", callback_data="noop")
    rows.append([InlineKeyboardButton("◀️ Prev", callback_data=prev_cb), center, InlineKeyboardButton("Next ▶️", callback_data=next_cb)])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def confirm_clear_kb(word_type: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard for clearing all words."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Clear All", callback_data=f"{word_type}:clear_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"{word_type}:back")],
    ])


def help_menu_kb(is_admin: bool, is_mod: bool) -> InlineKeyboardMarkup:
    """Interactive help menu with command buttons."""
    buttons = [
        [InlineKeyboardButton("📝 Track a Word", callback_data="menu_track")],
        [InlineKeyboardButton("👁 View My Tracked Words", callback_data="menu_view_tracked")],
        [InlineKeyboardButton("🚫 Ban a Word", callback_data="banned:add")],
        [InlineKeyboardButton("🗂 Manage Banned Words", callback_data="menu_banned")],
        [InlineKeyboardButton("💬 Send Feedback", callback_data="help:feedback")],
        [InlineKeyboardButton("📊 My Stats", callback_data="help:stats")],
        [InlineKeyboardButton("ℹ️ About", callback_data="help:about")],
    ]
    
    if is_admin:
        buttons.append([InlineKeyboardButton("🛡 Admin Panel", callback_data="menu_admin")])
    elif is_mod:
        buttons.append([InlineKeyboardButton("🔧 Moderator Tools", callback_data="menu_mod")])
    
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(buttons)


def admin_panel_kb() -> InlineKeyboardMarkup:
    """Admin panel main menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users & Stats", callback_data="admin:users")],
        [InlineKeyboardButton("📊 Analytics Dashboard", callback_data="admin:analytics")],
        [InlineKeyboardButton("📝 Feedback Management", callback_data="admin:feedback")],
        [InlineKeyboardButton("📢 Broadcast Messages", callback_data="admin:broadcast")],
        [InlineKeyboardButton("💾 Save Database", callback_data="admin:save")],
        [InlineKeyboardButton("📤 Export Database", callback_data="admin:export")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_main")],
    ])


def mod_panel_kb() -> InlineKeyboardMarkup:
    """Moderator panel main menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 User Statistics", callback_data="mod:users")],
        [InlineKeyboardButton("📊 Word Rankings", callback_data="mod:rankings")],
        [InlineKeyboardButton("📝 View Feedback", callback_data="mod:feedback")],
        [InlineKeyboardButton("💾 Save Database", callback_data="mod:save")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_main")],
    ])


def analytics_menu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    """Analytics dashboard menu."""
    buttons = [
        [InlineKeyboardButton("📅 Today's Stats", callback_data="analytics:today")],
        [InlineKeyboardButton("📈 Weekly Summary", callback_data="analytics:week")],
        [InlineKeyboardButton("📉 Monthly Summary", callback_data="analytics:month")],
    ]
    
    if is_admin:
        buttons.append([InlineKeyboardButton("📥 Export Data", callback_data="analytics:export")])
    
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="admin:panel" if is_admin else "mod:panel")])
    return InlineKeyboardMarkup(buttons)


def broadcast_menu_kb() -> InlineKeyboardMarkup:
    """Broadcast message options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 All Users", callback_data="broadcast:everyone")],
        [InlineKeyboardButton("🎯 Active Users Only", callback_data="broadcast:active")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin:panel")],
    ])


def feedback_actions_kb() -> InlineKeyboardMarkup:
    """Feedback management actions."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Clear All Feedback", callback_data="feedback:clear")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin:panel")],
    ])


