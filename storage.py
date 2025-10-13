import asyncio
import csv
import logging
import os
import pickle
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple


# In-memory storage (protected by a single lock to keep invariants between maps)
_storage_lock = asyncio.Lock()


# Users to tracked words
_tracked_by_user: Dict[int, Set[str]] = {}

# Word to user ids tracking that word
_users_by_word: Dict[str, Set[int]] = {}

# Users to banned words
_banned_by_user: Dict[int, Set[str]] = {}

# Word to last 5 messages: list of tuples (link, preview, timestamp, group_name)
_message_history: Dict[str, Deque[Tuple[str, str, float, str]]] = {}

_last_save: float = 0.0


@dataclass
class Paths:
    tracked_path: str = "db.pkl"
    users_by_word_path: str = "db2.pkl"
    banned_path: str = "dbb.pkl"
    history_path: str = "history.pkl"
    analytics_notifications: str = "analytics_notifications.csv"
    analytics_interactions: str = "analytics_interactions.csv"


_paths = Paths()

# Analytics lock for CSV writes
_analytics_lock = asyncio.Lock()


async def init_storage() -> None:
    """Load databases from disk. Missing files are tolerated."""
    async with _storage_lock:
        global _tracked_by_user, _users_by_word, _banned_by_user, _message_history

        _tracked_by_user = _safe_load_pickle(_paths.tracked_path, default={})
        _users_by_word = _safe_load_pickle(_paths.users_by_word_path, default={})
        _banned_by_user = _safe_load_pickle(_paths.banned_path, default={})
        raw_history = _safe_load_pickle(_paths.history_path, default={})
        # Rebuild deques with maxlen=5
        _message_history = {}
        for word, entries in raw_history.items():
            dq: Deque[Tuple[str, str, float, str]] = deque(maxlen=5)
            if isinstance(entries, list):
                for item in entries[-5:]:
                    try:
                        link, preview, ts, group_name = item
                        dq.append((str(link), str(preview), float(ts), str(group_name)))
                    except Exception:
                        # Skip malformed entries
                        continue
            _message_history[word] = dq
        logging.info("Storage initialized: %d users, %d words, %d histories", len(_tracked_by_user), len(_users_by_word), len(_message_history))


def _safe_load_pickle(path: str, default):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        logging.warning("Could not load %s, using default", path)
        return default


async def _atomic_pickle_dump(obj, path: str) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(obj, f)
    os.replace(tmp_path, path)


async def save_if_needed(force: bool = False) -> None:
    """Save all databases to disk atomically, throttled to once per 10s unless forced."""
    global _last_save
    now = time.time()
    async with _storage_lock:
        if not force and (now - _last_save) < 10:
            return
        _last_save = now
        try:
            await _atomic_pickle_dump(_tracked_by_user, _paths.tracked_path)
            await _atomic_pickle_dump(_users_by_word, _paths.users_by_word_path)
            await _atomic_pickle_dump(_banned_by_user, _paths.banned_path)
            # Serialize deques as lists
            history_serializable = {w: list(dq) for w, dq in _message_history.items()}
            await _atomic_pickle_dump(history_serializable, _paths.history_path)
            logging.info("Databases saved successfully")
        except Exception as e:
            logging.error("Error saving databases: %s", e)


async def periodic_save_task(stop_event: asyncio.Event) -> None:
    """Background task to periodically save databases every 30 seconds."""
    while not stop_event.is_set():
        try:
            await save_if_needed(force=False)
        except Exception as e:
            logging.error("Periodic save failed: %s", e)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            pass


async def ensure_user(user_id: int) -> None:
    async with _storage_lock:
        if user_id not in _tracked_by_user:
            _tracked_by_user[user_id] = set()
        if user_id not in _banned_by_user:
            _banned_by_user[user_id] = set()


async def add_tracked_word(user_id: int, word: str) -> None:
    normalized = word.lower()
    async with _storage_lock:
        _tracked_by_user.setdefault(user_id, set()).add(normalized)
        _users_by_word.setdefault(normalized, set()).add(user_id)
    await save_if_needed()


async def remove_tracked_word(user_id: int, word: str) -> None:
    normalized = word.lower()
    async with _storage_lock:
        if user_id in _tracked_by_user and normalized in _tracked_by_user[user_id]:
            _tracked_by_user[user_id].remove(normalized)
        if normalized in _users_by_word and user_id in _users_by_word[normalized]:
            _users_by_word[normalized].remove(user_id)
            if not _users_by_word[normalized]:
                _users_by_word.pop(normalized, None)
    await save_if_needed()


async def remove_all_tracked_words(user_id: int) -> None:
    async with _storage_lock:
        words = list(_tracked_by_user.get(user_id, set()))
    for w in words:
        await remove_tracked_word(user_id, w)


async def get_tracked_words(user_id: int) -> Set[str]:
    async with _storage_lock:
        return set(_tracked_by_user.get(user_id, set()))


async def users_tracking(word: str) -> Set[int]:
    normalized = word.lower()
    async with _storage_lock:
        return set(_users_by_word.get(normalized, set()))


async def add_banned_word(user_id: int, word: str) -> None:
    normalized = word.lower()
    async with _storage_lock:
        _banned_by_user.setdefault(user_id, set()).add(normalized)
    await save_if_needed()


async def remove_banned_word(user_id: int, word: str) -> None:
    normalized = word.lower()
    async with _storage_lock:
        if user_id in _banned_by_user and normalized in _banned_by_user[user_id]:
            _banned_by_user[user_id].remove(normalized)
    await save_if_needed()


async def remove_all_banned_words(user_id: int) -> None:
    async with _storage_lock:
        words = list(_banned_by_user.get(user_id, set()))
    for w in words:
        await remove_banned_word(user_id, w)


async def get_banned_words(user_id: int) -> Set[str]:
    async with _storage_lock:
        return set(_banned_by_user.get(user_id, set()))


async def update_message_history(word: str, link: str, preview: str, timestamp: float, group_name: str) -> None:
    """Update message history for a word, ensuring unique links only."""
    normalized = word.lower()
    async with _storage_lock:
        dq = _message_history.get(normalized)
        if dq is None:
            dq = deque(maxlen=5)
            _message_history[normalized] = dq
        
        # Check if this link already exists in the history
        existing_links = {entry[0] for entry in dq}
        if link not in existing_links:
            dq.append((link, preview[:100], float(timestamp), group_name))
    await save_if_needed()


async def get_message_history(word: str) -> List[Tuple[str, str, float, str]]:
    normalized = word.lower()
    async with _storage_lock:
        dq = _message_history.get(normalized, deque())
        return list(dq)


async def clear_message_history(word: str) -> None:
    normalized = word.lower()
    async with _storage_lock:
        _message_history[normalized] = deque(maxlen=5)
    await save_if_needed()


async def rank_tracked_words() -> List[Tuple[int, str]]:
    async with _storage_lock:
        ranking = [(len(users), word) for word, users in _users_by_word.items()]
    ranking.sort(reverse=True)
    return ranking


async def get_all_user_ids() -> Set[int]:
    async with _storage_lock:
        return set(_tracked_by_user.keys()) | set(_banned_by_user.keys())


async def count_all_users() -> int:
    async with _storage_lock:
        return len(set(_tracked_by_user.keys()) | set(_banned_by_user.keys()))


async def count_active_users() -> int:
    async with _storage_lock:
        return sum(1 for _uid, words in _tracked_by_user.items() if words)


# ==================== ANALYTICS FUNCTIONS ====================

def _ensure_csv_headers():
    """Ensure CSV files exist with proper headers."""
    # Notifications CSV
    if not os.path.exists(_paths.analytics_notifications):
        with open(_paths.analytics_notifications, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'user_id', 'word', 'message_type', 'status'])
    
    # Interactions CSV
    if not os.path.exists(_paths.analytics_interactions):
        with open(_paths.analytics_interactions, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'user_id', 'action_type', 'details'])


async def log_notification(user_id: int, word: str, message_type: str, status: str = 'success'):
    """Log a notification event to CSV."""
    async with _analytics_lock:
        _ensure_csv_headers()
        try:
            with open(_paths.analytics_notifications, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    user_id,
                    word,
                    message_type,
                    status
                ])
        except Exception as e:
            logging.error(f"Failed to log notification: {e}")


def _map_to_unified_action(action_type: str, details: str) -> str:
    """Map commands and callbacks to unified action names."""
    # Mapping of commands and callbacks to unified action names
    action_map = {
        # Start/Help - includes both commands, callbacks, and bot_message types
        '/start': 'Start Bot',
        'Start': 'Start Bot',
        'Bot Intro': 'Bot Intro',
        'menu_main': 'View Main Menu',
        'Menu': 'View Main Menu',
        '/help': 'View Help',
        'menu_help': 'View Help',
        'Help': 'View Help',
        
        # Tracking
        '/track': 'Track Word',
        'menu_track': 'Track Word',
        'Track': 'Track Word',
        'Track Ask': 'Track Word',
        'Track Receive': 'Track Word',
        '/untrack': 'Untrack Word',
        'Untrack': 'Untrack Word',
        'menu_view_tracked': 'View Tracked Words',
        'tracked:clear_all': 'Clear All Tracked',
        'tracked:clear_confirm': 'Clear All Tracked',
        'clear_all_tracked': 'Clear All Tracked',
        
        # Banning
        '/ban': 'Ban Word',
        'banned:add': 'Ban Word',
        'Ban': 'Ban Word',
        'Ban Ask': 'Ban Word',
        'Ban Receive': 'Ban Word',
        '/unban': 'Unban Word',
        'Unban': 'Unban Word',
        'menu_banned': 'View Banned Words',
        'banned:clear_all': 'Clear All Banned',
        'banned:clear_confirm': 'Clear All Banned',
        'clear_all_banned': 'Clear All Banned',
        
        # Admin/Mod
        '/admin_panel': 'Admin Panel',
        'menu_admin': 'Admin Panel',
        'admin:panel': 'Admin Panel',
        'Admin Panel': 'Admin Panel',
        '/mod_panel': 'Moderator Panel',
        'menu_mod': 'Moderator Panel',
        'mod:panel': 'Moderator Panel',
        'Mod Panel': 'Moderator Panel',
        'admin:analytics': 'View Analytics',
        'Save': 'Save Database',
        'User Count': 'View User Stats',
        'Rank Tracked': 'View Word Rankings',
        'Show Word': 'View Word Info',
        'Show Admins': 'View Admins',
        'Show Mods': 'View Mods',
        'Send Everyone': 'Broadcast to All',
        'Send Active': 'Broadcast to Active',
        'Get Admin': 'Get Admin Rights',
        'Get Admin Notification': 'Admin Rights Notification',
        'Get Mod': 'Get Mod Rights',
        'Get Mod Notification': 'Mod Rights Notification',
        'Broadcast': 'Broadcast Message',
        'Broadcast Status': 'Broadcast Message',
        'Broadcast Receive': 'Broadcast Message',
        'Broadcast Complete': 'Broadcast Message',
        'See Feedback': 'View Feedback',
        'Clear Feedback': 'Clear Feedback',
        
        # Other
        '/ping': 'Check Bot Status',
        'Ping': 'Check Bot Status',
        '/author': 'View About',
        'Author': 'View About',
        'help:about': 'View About',
        'help:stats': 'View My Stats',
        'help:feedback': 'Send Feedback',
        '/feedback': 'Send Feedback',
        'Feedback': 'Send Feedback',
        'Feedback Ask': 'Send Feedback',
        'Feedback Receive': 'Send Feedback',
        'Cancel': 'Cancel Operation',
        'Default': None,  # Don't count generic default messages
    }
    
    # Check if details matches a known action
    if details in action_map:
        mapped = action_map[details]
        # Return None for explicitly excluded actions
        return mapped if mapped is not None else details
    
    # For actions, check action_type
    if action_type == 'action' and details in action_map:
        return action_map[details]
    
    # Return original details if no mapping found
    return details


async def log_interaction(user_id: int, action_type: str, details: str = ''):
    """Log a user interaction event to CSV with unified action names."""
    # Map to unified action name
    unified_action = _map_to_unified_action(action_type, details)
    
    # Skip logging if mapping returned None (for explicitly excluded actions like "Default")
    if unified_action == details and details == 'Default':
        return
    
    async with _analytics_lock:
        _ensure_csv_headers()
        try:
            with open(_paths.analytics_interactions, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    user_id,
                    action_type,
                    unified_action  # Store unified action instead of raw details
                ])
        except Exception as e:
            logging.error(f"Failed to log interaction: {e}")


async def get_daily_stats(date: Optional[str] = None) -> Dict:
    """Get statistics for a specific date (format: YYYY-MM-DD). Defaults to today."""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    stats = {
        'date': date,
        'notifications_sent': 0,
        'interactions': 0,
        'unique_users': set(),
        'words_detected': {},
        'user_actions': {}
    }
    
    # Track unique messages per word (word -> set of message identifiers)
    word_unique_messages = {}
    
    async with _analytics_lock:
        # Read notifications - count unique messages per word
        if os.path.exists(_paths.analytics_notifications):
            with open(_paths.analytics_notifications, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['timestamp'].startswith(date):
                        stats['notifications_sent'] += 1
                        stats['unique_users'].add(int(row['user_id']))
                        word = row['word']
                        # Use timestamp as unique message identifier (messages sent at same time are same)
                        message_id = row['timestamp']
                        if word not in word_unique_messages:
                            word_unique_messages[word] = set()
                        word_unique_messages[word].add(message_id)
        
        # Convert unique message sets to counts
        for word, message_set in word_unique_messages.items():
            stats['words_detected'][word] = len(message_set)
        
        # Read interactions - count unified actions
        if os.path.exists(_paths.analytics_interactions):
            with open(_paths.analytics_interactions, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['timestamp'].startswith(date):
                        stats['interactions'] += 1
                        stats['unique_users'].add(int(row['user_id']))
                        # Get action from details column
                        # (new data has unified actions, old data needs mapping)
                        action = row.get('details', '')
                        if action and action != 'Default':
                            # For old data that wasn't mapped, try mapping it now
                            if (action.startswith('/') or action.startswith('menu_') or action.startswith('admin:') or 
                                action.startswith('mod:') or action.startswith('tracked:') or action.startswith('banned:') or action.startswith('help:') or
                                action in ['Start', 'Track', 'Ban', 'Help', 'Ping', 'Author', 'Feedback', 'Untrack', 'Unban', 'Menu', 'Cancel']):
                                action_type = row.get('action_type', '')
                                action = _map_to_unified_action(action_type, action)
                            stats['user_actions'][action] = stats['user_actions'].get(action, 0) + 1
    
    stats['unique_users'] = len(stats['unique_users'])
    
    # Get most tracked words
    stats['most_tracked_words'] = await rank_tracked_words()
    stats['most_tracked_words'] = stats['most_tracked_words'][:20]  # Top 20
    
    return stats


async def get_analytics_summary(days: int = 7) -> Dict:
    """Get analytics summary for the last N days."""
    summary = {
        'period_days': days,
        'total_notifications': 0,
        'total_interactions': 0,
        'unique_users': set(),
        'top_words': {},
        'top_actions': {},
        'daily_breakdown': []
    }
    
    # Track unique messages per word (word -> set of message identifiers)
    word_unique_messages = {}
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    async with _analytics_lock:
        # Read notifications - count unique messages per word
        if os.path.exists(_paths.analytics_notifications):
            with open(_paths.analytics_notifications, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = datetime.fromisoformat(row['timestamp'])
                    if start_date <= ts <= end_date:
                        summary['total_notifications'] += 1
                        summary['unique_users'].add(int(row['user_id']))
                        word = row['word']
                        # Use timestamp as unique message identifier
                        message_id = row['timestamp']
                        if word not in word_unique_messages:
                            word_unique_messages[word] = set()
                        word_unique_messages[word].add(message_id)
        
        # Convert unique message sets to counts
        for word, message_set in word_unique_messages.items():
            summary['top_words'][word] = len(message_set)
        
        # Read interactions - count unified actions
        if os.path.exists(_paths.analytics_interactions):
            with open(_paths.analytics_interactions, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = datetime.fromisoformat(row['timestamp'])
                    if start_date <= ts <= end_date:
                        summary['total_interactions'] += 1
                        summary['unique_users'].add(int(row['user_id']))
                        # Get action from details column
                        # (new data has unified actions, old data needs mapping)
                        action = row.get('details', '')
                        if action and action != 'Default':
                            # For old data that wasn't mapped, try mapping it now
                            if action.startswith('/') or action in ['Start', 'Track', 'Ban', 'Help', 'Ping', 'Author', 'Feedback', 'Untrack', 'Unban', 'Menu', 'Cancel']:
                                action_type = row.get('action_type', '')
                                action = _map_to_unified_action(action_type, action)
                            summary['top_actions'][action] = summary['top_actions'].get(action, 0) + 1
    
    summary['unique_users'] = len(summary['unique_users'])
    
    # Sort top words and actions
    summary['top_words'] = sorted(summary['top_words'].items(), key=lambda x: x[1], reverse=True)[:10]
    summary['top_actions'] = sorted(summary['top_actions'].items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Get most tracked words
    summary['most_tracked_words'] = await rank_tracked_words()
    summary['most_tracked_words'] = summary['most_tracked_words'][:20]  # Top 20
    
    return summary


async def export_analytics_csv(days: int = 30) -> Tuple[str, str]:
    """Return paths to analytics CSV files (or create filtered versions for the period)."""
    # For now, just return the full files
    # In the future, could create filtered temporary files
    return (_paths.analytics_notifications, _paths.analytics_interactions)




