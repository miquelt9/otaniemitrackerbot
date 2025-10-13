from datetime import datetime
from typing import List, Tuple


def main_menu_text() -> str:
    return (
        "Choose an option:" 
    )


def help_text_basic() -> str:
    return (
        "This bot tracks words in groups and notifies you.\n\n"
        "Commands:\n"
        "/track 'word' - Start tracking a word\n"
        "/untrack 'word' - Stop tracking a word\n"
        "/ban 'word' - Ban a word\n"
        "/unban 'word' - Unban a word\n"
        "/show - Show tracked and banned words\n"
        "/clear - Clear tracked words\n"
        "/clear_banned - Clear banned words\n"
        "/feedback [message] - Send feedback\n"
        "/author - Show bot author"
    )


def help_text_full() -> str:
    return (
        "All commands:\n"
        "/track 'word' - Track a word\n"
        "/untrack 'word' - Stop tracking a word\n"
        "/ban 'word' - Ban a word\n"
        "/unban 'word' - Unban a word\n"
        "/show - Show tracked and banned words\n"
        "/show_tracked - Show tracked words\n"
        "/show_banned - Show banned words\n"
        "/clear - Clear tracked words\n"
        "/clear_banned - Clear banned words\n"
        "/feedback [message] - Send feedback\n"
        "/rate [message] - Send feedback (alias)\n"
        "/ping - Check bot responsiveness\n"
        "/author - Display the bot's authors"
    )


def word_detail_text(word: str, since_ts: float, message_count: int) -> str:
    since = datetime.fromtimestamp(since_ts).strftime('%Y-%m-%d %H:%M') if since_ts else "N/A"
    return (
        f"🔤 Word: {word}\n"
        f"📅 Tracking since: {since}\n"
        f"🧾 Messages stored: {message_count}"
    )


def format_history(word: str, entries: List[Tuple[str, str, float, str]]) -> str:
    if not entries:
        return f"No recent messages for '{word}'."
    lines = [f"🕘 Last messages for '{word}':"]
    for link, preview, ts, group_name in reversed(entries):
        dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
        shown_link = link if link else "Message unavailable"
        lines.append(f"\n• {dt} — {group_name}\n{preview}\n{shown_link}")
    return "\n".join(lines)


def notification_text_detected(word: str, link: str, prefix: str) -> str:
    return f"{prefix} ({word} detected)\n{link}"


def admin_panel_text() -> str:
    return "🔧 Admin Panel\n\nChoose an option:"


def mod_panel_text() -> str:
    return "🔧 Moderator Panel\n\nChoose an option:"


def confirm_clear_text(word_type: str, count: int) -> str:
    return f"⚠️ Are you sure?\n\nThis will delete all {count} {word_type} words.\nThis action cannot be undone."


def analytics_summary_text(stats: dict, period: str = "Today") -> str:
    lines = [f"📊 Analytics - {period}\n"]
    
    if 'date' in stats:
        lines.append(f"📅 Date: {stats['date']}")
    
    lines.append(f"📨 Notifications sent: {stats.get('notifications_sent', stats.get('total_notifications', 0))}")
    lines.append(f"👆 User interactions: {stats.get('interactions', stats.get('total_interactions', 0))}")
    lines.append(f"👥 Unique users: {stats.get('unique_users', 0)}")
    
    # Top detected words (unique messages per word)
    if 'words_detected' in stats and stats['words_detected']:
        lines.append("\n🔤 Top detected words (unique messages):")
        for word, count in sorted(stats['words_detected'].items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  • {word}: {count}")
    elif 'top_words' in stats and stats['top_words']:
        lines.append("\n🔤 Top detected words (unique messages):")
        for word, count in stats['top_words'][:5]:
            lines.append(f"  • {word}: {count}")
    
    # Top user actions (unified commands and button clicks)
    if 'user_actions' in stats and stats['user_actions']:
        lines.append("\n⚡ Top user actions:")
        for action, count in sorted(stats['user_actions'].items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  • {action}: {count}")
    elif 'top_actions' in stats and stats['top_actions']:
        lines.append("\n⚡ Top user actions:")
        for action, count in stats['top_actions'][:5]:
            lines.append(f"  • {action}: {count}")
    
    # Most tracked words (by number of users)
    if 'most_tracked_words' in stats and stats['most_tracked_words']:
        lines.append("\n📌 Most tracked words:")
        for count, word in stats['most_tracked_words'][:20]:
            lines.append(f"  • {word}: {count} users")
    
    return "\n".join(lines)


def broadcast_menu_text() -> str:
    return "📢 Broadcast Message\n\nChoose recipients:"


def ban_word_warning() -> str:
    return (
        "⚠️ Please send the word to ban.\n\n"
        "Note: The author discourages the use of the ban feature except for the word 'dibs', "
        "since any message containing a banned word will NOT be notified to you, "
        "and you might miss important items."
    )


def help_text_interactive() -> str:
    return (
        "ℹ️ Help & Commands\n\n"
        "Click a button below to access different features:"
    )


def bot_intro_message(group_link1: str = "", group_link2: str = "") -> str:
    """Intro message explaining what the bot does."""
    if group_link1 and group_link2:
        return (
            "👋 Welcome! "
            f"🤖 This bot will track the words you wish in {group_link1} and {group_link2} "
            "so you get tailored notifications for items you want to buy or get for free!"
        )
    else:
        return (
            "👋 Welcome! "
            "🤖 This bot will track the words you wish in the Otaniemi groups "
            "so you get tailored notifications for items you want to buy or get for free!"
        )


