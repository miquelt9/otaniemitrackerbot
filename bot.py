import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Updater, filters, MessageHandler
import pickle
import time
import string
from datetime import datetime

TOKEN = open('token.txt').read().strip()
BASE_URL = f'https://api.telegram.org/bot{TOKEN}'
PSWD_ADM = open('pswd.adm').read().strip()
PSWD_MOD = open('pswd.mod').read().strip()
GID = open('group_id.txt').read().strip()  # Otaniemi group ID
GROUP_LINK = open('group_link.txt').read().strip()  # Otaniemi group ID

# Global dictionary DB for storing ppl info
# Contains user.set(tracked_words)
db = {}

# Contains word.set(users_who_track_it)
db2 = {}

# Contains user.set(banned_words)
dbb = {}

admins = set()

mods = set()

last_save = 0

translator = str.maketrans(string.punctuation, ' ' * len(string.punctuation))


def remove_punctuation(input_string):
    cleaned_str = input_string.translate(translator)
    return cleaned_str


def save_if_needed(force=False):

    global last_save
    current_time = time.time()

    if (current_time - last_save >= 10) or force:
        formatted_time = datetime.fromtimestamp(
            current_time).strftime('%H:%M %d/%m/%Y')
        print("Saving... at " + str(formatted_time))
        last_save = current_time

        with open("db.pkl", "wb") as pickle_file:
            pickle.dump(db, pickle_file)

        with open("db2.pkl", "wb") as pickle_file:
            pickle.dump(db2, pickle_file)

        with open("dbb.pkl", "wb") as pickle_file:
            pickle.dump(dbb, pickle_file)


def load_db():
    global db, db2, dbb
    with open("db.pkl", "rb") as pickle_file:
        db = pickle.load(pickle_file)

    with open("db2.pkl", "rb") as pickle_file:
        db2 = pickle.load(pickle_file)

    with open("dbb.pkl", "rb") as pickle_file:
        dbb = pickle.load(pickle_file)


def new_user(user):
    """
    Check if a user already exists, otherwise it creates it with default params.
    """
    if user.id not in db:
        db[user.id] = set()
    if user.id not in dbb:
        dbb[user.id] = set()

# Tracking words methods


def add_track_word(user, word):

    if word not in db[user.id]:
        db[user.id].add(word)

    if word not in db2:
        # print("added: " + str(user.id))
        db2[word] = {str(user.id)}
    else:
        db2[word].add(str(user.id))

    save_if_needed()


def remove_track_word(user, word):

    if word in db[user.id]:
        db[user.id].remove(word)

    if word in db2:
        db2[word].remove(str(user.id))
        if not db2[word]:
            db2.pop(word)

    save_if_needed()


def remove_all_track_words(user):
    words = list(db[user.id])
    for word in words:
        remove_track_word(user, word)


def get_tracked_words(user):
    return db[user.id]


def get_users_who_track(word):
    if word in db2:
        return db2[word]
    return {}

# Banned words methods


def add_ban_word(user, word):

    if word not in dbb[user.id]:
        dbb[user.id].add(word)

    save_if_needed()


def remove_ban_word(user, word):

    if word in dbb[user.id]:
        dbb[user.id].remove(word)

    save_if_needed()


def remove_all_ban_words(user):
    words = list(dbb[user.id])
    for word in words:
        remove_ban_word(user, word)


def get_banned_words(userId):
    return dbb[userId]

# General methods


def extract_word(input_string):
    # Regular expression pattern to match single-quoted, double-quoted, or unquoted words
    pattern = r"'([^']+)'|\"([^\"]+)\"|(\w+)"

    match = re.search(pattern, input_string)
    if match:
        return match.group(1) or match.group(2) or match.group(3)
    else:
        return None


async def check_if_message_to_group(context, message, user):
    if int(message.chat_id) == int(GID):
        await context.bot.send_message(user.id, "To prevent message influx write me directly @otaniemitrackerbot")
        return True
    elif message.chat_id < 0:
        await context.bot.send_message(user.id, "Please write directly to the bot (@otaniemitrackerbot)")
        return True
    return False


def check_strings_not_in_list(input_list, banned_list):
    for word in input_list:
        if word in banned_list:
            return False
    return True


### Bot commands ###

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    new_user(user)
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    name = user.first_name
    await context.bot.send_message(user.id, 'Welcome ' + name + '!')
    await context.bot.send_message(user.id, 'Write /help to list the available commands')


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await context.bot.send_message(message.chat_id, "This bot will track the words you wish in \
                                    https://t.me/aaltomarketplace so you get the\
                                    messages filtered.\
                                    \n\nYou can use:"
                                   + "\n/track 'word'          (to start tracking a word)"
                                   + "\n/untrack 'word'     (to stop tracking a word)"
                                   + "\nYou can also /ban 'word' - /unban 'word'"
                                   + "\n/show                     (to display current tracked/banned words)"
                                   + "\n/clear                      (stop tracking all words)"
                                   + "\n/full_help               (shows a more detailed help menu)"
                                   + "\n/rate [message]    (send any feedback)"
                                   + "\n\n-> Note that the bot is case insensitive"
                                   + "\n-> To report any error contact @miquelt_9")

    if update.effective_user in mods or update.effective_user in admins:
        await context.bot.send_message(user.id, "\nAs an mod you are granted extra commands:\
                                                        \n/user_count                            (which shows how many users are using the bot)\
                                                        \n/rank_tracked                           (shows the words tracked by people)\
                                                        \n/show_mods                          (show current admins)\
                                                        \n/save                                        (saves the db)\
                                                        \n/see_feedback                            (shows users' feedback)")

    if update.effective_user in admins:
        await context.bot.send_message(user.id, "\nAs an admin you are granted extra commands:\
                                                        \n/show_admins                        (show current admins)\
                                                        \n/show_word 'word'                (which shows current id of users who are tracking a word)\
                                                        \n/clear_feedback\
                                                        \n/send_active [message]\
                                                        \n/send_everyone [message]")


async def full_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await context.bot.send_message(message.chat_id, "All the commands available are:"
                                   + "\n/track 'word'\n/untrack 'word'"
                                   + "\n/ban 'word'\n/unban 'word'"
                                   + "\n/show\n/show_tracked\n/show_banned"
                                   + "\n/clear (only clears tracked words)\n/clear_banned (only clears banned words)"
                                   + "\n/rate [message] - /feedback [message] (send any feedback)"
                                   + "\n/author")


async def author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    await context.bot.send_message(user.id, 'Otaniemi Buy/Sell Tracker Bot\
                                    \n Miquel Torner Viñals\
                                    \n Bernat Borràs Civil')

## Tracking words commands ##


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text.lower()
    splitted_input = user_input.split()

    if (len(splitted_input) == 2):
        user_word = extract_word(splitted_input[1])
        add_track_word(user, user_word)
        await context.bot.send_message(user.id, 'Succesfully tracking ' + user_word)
    else:
        await context.bot.send_message(user.id, 'Error: Add just one word after:\
                                        \n/track "word"')


async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    user_input = update.message.text.lower()
    splitted_input = user_input.split()

    if (len(splitted_input) == 2):
        user_word = extract_word(splitted_input[1])
        remove_track_word(user, splitted_input[1])
        await context.bot.send_message(user.id, 'Succesfully stopped tracking ' + user_word)
    else:
        await context.bot.send_message(user.id, 'Error: Add just one word after:\
                                        /untrack "word"')


async def show_tracked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    tracked_words = get_tracked_words(user)

    if tracked_words:
        await context.bot.send_message(user.id, 'Your tracked words are: ' + str(tracked_words))
    else:
        await context.bot.send_message(user.id, 'You are not tracking any words right now')


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await show_tracked(update, context)
    await show_banned(update, context)


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    remove_all_track_words(user)
    await context.bot.send_message(user.id, "You are not longer tracking any words")


## Banning words methods ##

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text.lower()
    splitted_input = user_input.split()

    if (len(splitted_input) == 2):
        user_word = extract_word(splitted_input[1])
        add_ban_word(user, user_word)
        await context.bot.send_message(user.id, 'Succesfully banned ' + user_word + "! You won't receive any message that includes it")
    else:
        await context.bot.send_message(user.id, 'Error: Add just one word after:\
                                        \n/ban "word"')


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    user_input = update.message.text.lower()
    splitted_input = user_input.split()

    if (len(splitted_input) == 2):
        user_word = extract_word(splitted_input[1])
        remove_ban_word(user, splitted_input[1])
        await context.bot.send_message(user.id, 'The word ' + user_word + ' is no longer banned')
    else:
        await context.bot.send_message(user.id, 'Error: Add just one word after:\
                                        /unban "word"')


async def show_banned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    baned_words = get_banned_words(user.id)

    if baned_words:
        await context.bot.send_message(user.id, 'Your banned words are: ' + str(baned_words))
    else:
        await context.bot.send_message(user.id, "There aren't any banned words")


async def clear_banned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    remove_all_ban_words(user)
    await context.bot.send_message(user.id, "Succesfully cleared the banned words")


### ADMIN AND MOD COMMANDS ###

async def show_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        user_input = message.text
        splitted_input = user_input.split()

        if (len(splitted_input) == 2):
            users = get_users_who_track(extract_word(splitted_input[1]))
            await context.bot.send_message(user.id, 'Current users who are tracking ' + splitted_input[1] + ': ' + str(users))
        else:
            await context.bot.send_message(user.id, 'Error on /show_words')


async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    admin = update.effective_user
    message = update.message

    if int(message.chat_id) == int(GID):
        await context.bot.send_message(admin.id, "To prevent message influx write me directly @otaniemitrackerbot")
        return
    elif message.chat_id < 0:
        await context.bot.send_message(admin.id, "Please write directly to the bot (@otaniemitrackerbot)")
        return

    if admin in admins or admin in mods:
        num_users = len(db)
        active_users = 0
        for user in db:
            if db[user]:
                active_users += 1
        await context.bot.send_message(admin.id, 'There are currently ' + str(active_users) + " active users out of " + str(num_users) + ' registered.')


async def rank_tracked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        ranking = []
        for word in db2:
            ranking.append((len(db2[word]), word))

        sorted_ranking = sorted(ranking, reverse=True)
        rank_text = ""
        for item in sorted_ranking:
            rank_text += "\n" + str(item[1]) + " - " + str(item[0]) + " ppl"
        await context.bot.send_message(user.id, "Ranking the words tracked by people:" + rank_text)


async def save_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        save_if_needed(force=True)
        await context.bot.send_message(user.id, "The database was succesfully saved!")


async def send_everyone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        splitted_input = message.text.split()
        admin_message = ' '.join(splitted_input[1:])
        for user in db.keys():
            await context.bot.send_message(int(user), admin_message)


async def send_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        splitted_input = message.text.split()
        admin_message = ' '.join(splitted_input[1:])
        for user in db.keys():
            if db[user]:
                await context.bot.send_message(int(user), admin_message)


async def show_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        await context.bot.send_message(message.chat_id, 'Current admins are: ' + str(admins))


async def show_mods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        await context.bot.send_message(message.chat_id, 'Current mods are: ' + str(mods))


async def get_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text
    splitted_input = user_input.split()

    if user in admins:
        if len(splitted_input) == 2:
            await context.bot.send_message(user.id, 'You are already a superuser.')

    else:
        if (len(splitted_input) == 2):
            if splitted_input[1] == PSWD_ADM:
                for admin_user in admins:
                    await context.bot.send_message(admin_user.id, 'A new user '+str(user.full_name)+' got admin rights! (@'+str(user.username)+')')

                await context.bot.send_message(message.chat_id, 'You got superuser rights')
                admins.add(user)
                mods.add(user)


async def get_mod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text
    splitted_input = user_input.split()

    if user in mods:
        if len(splitted_input) == 2:
            await context.bot.send_message(user.id, 'You are already a mod.')

    else:
        if (len(splitted_input) == 2):
            if splitted_input[1] == PSWD_MOD:
                for admin_user in admins:
                    await context.bot.send_message(admin_user.id, 'A new user '+str(user.full_name)+' got mod rights! (@'+str(user.username)+')')
                for mod_user in mods:
                    if mod_user not in admins:
                        await context.bot.send_message(mod_user.id, 'A new user '+str(user.full_name)+' got mod rights! (@'+str(user.username)+')')

                await context.bot.send_message(message.chat_id, 'You got mod rights')
                mods.add(user)


async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    file_path = "feedback.txt"

    splitted_input = message.text.split()
    if len(splitted_input) < 2:
        await context.bot.send_message(user.id, "Please add a message /feedback [message]")
        return

    with open(file_path, 'a') as file:
        feedback_message = ' '.join(splitted_input[1:])
        file.write(feedback_message + "\n")
        await context.bot.send_message(user.id, "Your feedback was succesfully sent to the mods!")


async def see_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    file_path = "feedback.txt"

    if user in admins or user in mods:
        with open(file_path, 'r') as file:
            for line in file:
                txt = line.strip()
                await context.bot.send_message(message.chat_id, 'Someone said: ' + txt)


async def clear_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    file_path = "feedback.txt"

    if user in admins:
        with open(file_path, 'w') as file:
            pass
            await context.bot.send_message(user.id, "The feedback file was cleared")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    message = update.message

    if int(message.chat_id) == int(GID):
        if message.photo:
            # Handle single photos as before
            caption = message.caption or ''
            splitted_input = remove_punctuation(caption.lower()).split()
            sender_username = message.from_user.username if message.from_user.username else ""
            already_sent = set()
            message_link = f"{GROUP_LINK}/{message.message_id}"
            for word in splitted_input:
                if word in db2:
                    for user_id in db2[word]:
                        if check_strings_not_in_list(splitted_input, get_banned_words(int(user_id))):
                            if user_id not in already_sent:
                                notification_message = f"You might be interested in this message ({word} detected)\n{message_link}"
                                await context.bot.send_message(user_id, notification_message, disable_notification=True)
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
                    already_sent = set()
                    message_link = f"{GROUP_LINK}/{message.message_id}"
                    for word in splitted_input:
                        if word in db2:
                            for user_id in db2[word]:
                                if check_strings_not_in_list(splitted_input, get_banned_words(int(user_id))):
                                    if user_id not in already_sent:
                                        notification_message = f"You might be interested in this message ({word} detected)\n{message_link}"
                                        await context.bot.send_message(user_id, notification_message, disable_notification=True)
                                        already_sent.add(user_id)


def main():

    load_db()

    # print(db)
    # print(db2)

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("author", author))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("full_help", full_help))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("untrack", untrack))
    app.add_handler(CommandHandler("show", show))
    app.add_handler(CommandHandler("show_tracked", show_tracked))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("show_banned", show_banned))
    app.add_handler(CommandHandler("clear_banned", clear_banned))
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
    app.add_handler(CommandHandler("feedback", rate))
    app.add_handler(CommandHandler("rate", rate))
    app.add_handler(CommandHandler("see_feedback", see_feedback))
    app.add_handler(CommandHandler("check_feedback", see_feedback))
    app.add_handler(CommandHandler("clear_feedback", clear_feedback))

    # Add a message handler that will be called for any message
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO, message_handler))

    # Start the bot
    app.run_polling()


if __name__ == '__main__':
    main()