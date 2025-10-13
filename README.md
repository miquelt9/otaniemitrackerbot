# Otaniemi Tracker Bot
Source code for otaniemi tracker bot (https://t.me/otaniemitrackerbot)

### > What can this bot do?

This bot became the solution to a problem I had when moving to Finland for Erasmus since the apartment I got was not furnished, the main recommended group to get the furniture has a lot influx so I needed a way to filter what was important for me. The bot allows you to track the objects you are interested in the desired group and forwards to you any message that you might be interested in so you don't miss it.

The bot now features an **interactive menu system** that makes it much easier to use! Most functionality is accessible through buttons and menus rather than commands.

### > Key Features

- **Interactive Menus**: Easy-to-use button-based interface
- **Word Tracking**: Track specific words to get notified when they appear in groups
- **Word Banning**: Ban words to avoid notifications containing them
- **Analytics Dashboard**: View usage statistics and popular words
- **Broadcast System**: Admins can send messages to all users
- **Database Export**: Export all data for backup and analysis
- **Smart Notifications**: Ignores old messages to prevent spam when bot restarts
- **Real-time Updates**: Instant notifications when tracked words are detected

### > Commands

| Command | Description | Permissions |
|---|---|---|
| `/start` | Starts the bot and shows main menu | User |
| `/help` | Shows interactive help menu | User |
| `/track [word]` | Starts tracking a word | User |
| `/ban [word]` | Bans a word (not recommended) | User |
| `/feedback [message]` | Sends feedback to the team | User |
| `/ping` | Check if the bot is awake | User |
| `/author` | Shows the credits | User |
| `/user_count` | Shows current count of users | Mod |
| `/rank_words` | Shows tracked words by popularity | Mod |
| `/save` | Saves the current database | Mod |
| `/see_feedback` | Shows user feedback | Mod |
| `/show_mods` | Shows all moderators | Mod |
| `/show_admins` | Shows all administrators | Admin |
| `/clear_feedback` | Clears all feedback | Admin |
| `/export_database` | Exports database files for backup | Admin |

### > How to run it yourself

#### Prerequisites
1. **Python 3.8+** installed on your system
2. **Bot Token** from [@BotFather](https://t.me/botfather)
3. **Group IDs** and **Group Links** for the groups you want to monitor

#### Setup Instructions

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create required files:**
   - `token.txt` - Your bot token from BotFather
   - `group1_id.txt` - ID of the first group to monitor
   - `group1_link.txt` - Public link to the first group
   - `group2_id.txt` - ID of the second group to monitor  
   - `group2_link.txt` - Public link to the second group
   - `pswd.adm` - Admin password (plain text)
   - `pswd.mod` - Moderator password (plain text)

3. **Run the bot:**
   ```bash
   python3 bot.py
   ```

#### Getting Group IDs

To get a group ID:
1. Add your bot to the group
2. Send a message in the group
3. Check the bot logs - the group ID will be printed
4. Save it to the appropriate `group_id.txt` file

#### Database Files

The bot automatically creates the required database files (`db.pkl`, `db2.pkl`, `dbb.pkl`, `history.pkl`) when first run. No manual setup required!

### > Want to contribute?

Check the [issues](https://github.com/miquelt9/otaniemitrackerbot/issues) tab from the project to start working or create your own to let others know about your thoughts and findings.

### > License

This project is open source. Feel free to use, modify, and distribute according to your needs.
