import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Updater, filters, MessageHandler
import pickle
import time
import string
import logging
from datetime import datetime

logging.basicConfig(filename='bot.log', filemode='w', format='%(asctime)s - %(message)s', level=logging.INFO)

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



def save_if_needed(force=False):

    global last_save
    current_time = time.time()

    if (current_time - last_save >= 10) or force:
        last_save = current_time

        with open("db.pkl", "wb") as pickle_file:
            try:
                pickle.dump(db, pickle_file)
                logging.info("Database db.pkl successfully saved")
            except:
                logging.error("Something went wrong when trying to save db.pkl...")

        with open("db2.pkl", "wb") as pickle_file:
            try:
                pickle.dump(db2, pickle_file)
                logging.info("Database db2.pkl successfully saved")
            except:
                logging.error("Something went wrong when trying to save db2.pkl...")

        with open("dbb.pkl", "wb") as pickle_file:
            try:
                pickle.dump(dbb, pickle_file)
                logging.info("Database dbb.pkl successfully saved")
            except:
                logging.error("Something went wrong when trying to save dbb.pkl...")
        

def load_db():
    global db, db2, dbb
    with open("db.pkl", "rb") as pickle_file:
        try:
            db = pickle.load(pickle_file)
            logging.info("Database db.pkl successfully loaded")
        except:
            logging.error("Something went wrong when trying to load db.pkl...")

    with open("db2.pkl", "rb") as pickle_file:
        try:
            db2 = pickle.load(pickle_file)
            logging.info("Database db2.pkl successfully loaded")
        except:
            logging.error("Something went wrong when trying to load db2.pkl...")

    with open("dbb.pkl", "rb") as pickle_file:
        try:
            dbb = pickle.load(pickle_file)
            logging.info("Database dbb.pkl successfully loaded")
        except:
            logging.error("Something went wrong when trying to load dbb.pkl...")

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

async def check_then_send_message(context, user, message, notification=None, user_id=None, type="Default"):
    if user_id == None:
        try:
            await context.bot.send_message(user.id, str(message), disable_notification=notification)
            logging.info("Message (type: " + type + ")\n'" + str(message) + "'\n successfully sent to user " + str(user.id))
        except Exception as e:
            logging.error("Something went wrong when sending '" + str(message) + "' to user " + str(user))
            logging.error("Catches exception: " + str(e))
    else:
        try:
            await context.bot.send_message(user_id, str(message), disable_notification=notification)
            logging.info("Message (type: " + type + ")\n'" + str(message) + "'\n successfully sent to user " + str(user_id))
        except Exception as e:
            logging.error("Something went wrong when sending '" + str(message) + "' to user " + str(user_id) + " (tracked word detected)")
            logging.error("Catches exception: " + str(e))

### Bot commands ###

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    new_user(user)
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    name = user.first_name
    await check_then_send_message(context, user, 'Welcome ' + name + '!', type="Start")
    await check_then_send_message(context, user, 'Write /help to list the available commands', type="Start")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return    

    response_time = float(time.time()) - message.date.timestamp()

    await check_then_send_message(context, user, 'Still awake, time to reply: ' + str(int(response_time*1000)) + ' ms', type="Ping")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await check_then_send_message(context, user, "This bot will track the words you wish in \
                                    https://t.me/aaltomarketplace and https://t.me/annetaantavaraa so you get the messages tailored for you.\
                                    \n\nYou can use:"
                                   + "\n/track 'word'          (to start tracking a word)"
                                   + "\n/untrack 'word'     (to stop tracking a word)"
                                   + "\nYou can also /ban 'word' - /unban 'word'"
                                   + "\n/show                     (to display current tracked/banned words)"
                                   + "\n/clear                      (stop tracking all words)"
                                   + "\n/full_help               (shows a more detailed help menu)"
                                   + "\n/rate [message]    (send any feedback)"
                                   + "\n\n-> Note that the bot is case insensitive"
                                   + "\n-> To report any error contact @miquelt_9", type="Help")

    if update.effective_user in mods or update.effective_user in admins:
        await check_then_send_message(context, user, "\nAs an mod you are granted extra commands:\
                                                        \n/user_count                            (which shows how many users are using the bot)\
                                                        \n/rank_tracked                           (shows the words tracked by people)\
                                                        \n/show_mods                          (show current admins)\
                                                        \n/save                                        (saves the db)\
                                                        \n/see_feedback                            (shows users' feedback)", type="Help Mod")

    if update.effective_user in admins:
        await check_then_send_message(context, user, "\nAs an admin you are granted extra commands:\
                                                        \n/show_admins                        (show current admins)\
                                                        \n/show_word 'word'                (which shows current id of users who are tracking a word)\
                                                        \n/clear_feedback\
                                                        \n/send_active [message]\
                                                        \n/send_everyone [message]", type="Help Admin")


async def full_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    await check_then_send_message(context, user, "All the commands available are:"
                                   + "\n/track 'word'   - Track a word (messages containing the word will be send to you)"
                                   + "\n/untrack 'word' - Stop tracking a word"
                                   + "\n/ban 'word'     - Ban a word (messages containing it won't be received)"
                                   + "\n/unban 'word'   - Stop banning a word"
                                   + "\n/show           - Show tracked and banned words"
                                   + "\n/show_tracked   - Show tracked words"
                                   + "\n/show_banned    - Shows banned words"
                                   + "\n/clear          - Clears (only) tracked words" 
                                   + "\n/clear_banned   - Clears (only) banned words"
                                   + "\n/rate [message]     - Send a message for mods"
                                   + "\n/feedback [message] - Send a message for mods"
                                   + "\n/ping           - Check if the bot is awake"
                                   + "\n/author         - Display the bot's author", type="Full Help")


async def author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
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
        await check_then_send_message(context, user, 'Succesfully tracking ' + user_word, type="Track")
    else:
        await check_then_send_message(context, user, 'Error: Add just one word after:\
                                        \n/track "word"', type="Track")


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
        await check_then_send_message(context, user, 'Succesfully stopped tracking ' + user_word, type="Track")
    else:
        await check_then_send_message(context, user, 'Error: Add just one word after:\
                                        /untrack "word"', type="Track")


async def show_tracked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    tracked_words = get_tracked_words(user)

    if tracked_words:
        await check_then_send_message(context, user, 'Your tracked words are: ' + str(tracked_words), type="Show Tracked")
    else:
        await check_then_send_message(context, user, 'You are not tracking any words right now', type="Show Tracked")


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
    await check_then_send_message(context, user, "You are not longer tracking any words", type="Track")


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
        await check_then_send_message(context, user, 'Succesfully banned ' + user_word + "! You won't receive any message that includes it", type="Ban")
    else:
        await check_then_send_message(context, user, 'Error: Add just one word after:\
                                        \n/ban "word"', type="Ban")


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
        await check_then_send_message(context, user, 'The word ' + user_word + ' is no longer banned', type="Ban")
    else:
        await check_then_send_message(context, user, 'Error: Add just one word after:\
                                        /unban "word"', type="Ban")


async def show_banned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    baned_words = get_banned_words(user.id)

    if baned_words:
        await check_then_send_message(context, user, 'Your banned words are: ' + str(baned_words), type="Show Banned")
    else:
        await check_then_send_message(context, user, "There aren't any banned words", type="Show Banned")


async def clear_banned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    message = update.message
    user = update.effective_user

    if await check_if_message_to_group(context, message, user):
        return

    remove_all_ban_words(user)
    await check_then_send_message(context, user, "Succesfully cleared the banned words", type="Ban")


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
            await check_then_send_message(context, user, 'Current users who are tracking ' + splitted_input[1] + ': ' + str(users), type="Show Word")
        else:
            await check_then_send_message(context, user, 'Error on /show_words', type="Show Word")


async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    admin = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, admin):
        return
    
    if admin in admins or admin in mods:
        num_users = len(db)
        active_users = 0
        for user in db:
            if db[user]:
                active_users += 1
        await check_then_send_message(context, admin, 'There are currently ' + str(active_users) + " active users out of " + str(num_users) + ' registered.', type="User Count")


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
        await check_then_send_message(context, user, "Ranking the words tracked by people:" + rank_text, type="Rank Tracked")


async def save_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        save_if_needed(force=True)
        await check_then_send_message(context, user, "The database was succesfully saved!", type="Save")


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
            await check_then_send_message(context, int(user), admin_message, type="Send Everyone")


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
                await check_then_send_message(context, int(user), admin_message, type="Send Active")


async def show_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins:
        await check_then_send_message(context, user, 'Current admins are: ' + str(admins), type="Show Admins")


async def show_mods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    if user in admins or user in mods:
        await check_then_send_message(context, user, 'Current mods are: ' + str(mods), type="Show Mods")


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
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    user_input = message.text
    splitted_input = user_input.split()

    if user in mods:
        if len(splitted_input) == 2:
            await check_then_send_message(user.id, 'You are already a mod.', type="Get Mod")

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


async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_user(update.effective_user)
    user = update.effective_user
    message = update.message

    if await check_if_message_to_group(context, message, user):
        return

    file_path = "feedback.txt"

    splitted_input = message.text.split()
    if len(splitted_input) < 2:
        await check_then_send_message(context, user, "Please add a message /feedback [message]", type="Rate")
        return

    with open(file_path, 'a') as file:
        feedback_message = ' '.join(splitted_input[1:])
        file.write(feedback_message + "\n")
        await check_then_send_message(context, user, "Your feedback was succesfully sent to the mods!", type="Rate")


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
                await check_then_send_message(context, user, 'Someone said: ' + txt, type="See Feedback")


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
            await check_then_send_message(context, user, "The feedback file was cleared", type="Clear Feedback")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    message = update.message

    #print("Received message on chat: " + str(message.chat_id))

    if float(message.date.timestamp()) + 5*60 < time.time():
        return

    already_sent = set()

    if int(message.chat_id) == int(GID1):   # Message received through group1 (buy/sell otaniemi)
        if message.photo:
            # Handle single photos
            caption = message.caption or ''
            splitted_input = remove_punctuation(caption.lower()).split()
            sender_username = message.from_user.username if message.from_user.username else ""
            message_link = f"{GROUP_LINK1}/{message.message_id}"
            for word in splitted_input:
                if word in db2:
                    for user_id in db2[word]:
                        if check_strings_not_in_list(splitted_input, get_banned_words(int(user_id))):
                            if user_id not in already_sent:
                                notification_message = f"You might be interested in this message ({word} detected)\n{message_link}"
                                await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Photo)")
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
                        if word in db2:
                            for user_id in db2[word]:
                                if check_strings_not_in_list(splitted_input, get_banned_words(int(user_id))):
                                    if user_id not in already_sent:
                                        notification_message = f"You might be interested in this message ({word} detected)\n{message_link}"
                                        await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Album)")
                                        already_sent.add(user_id)


    if int(message.chat_id) == int(GID2):   # Message received through group2 (giveaway otaniemi)
        if message.photo:
            # Handle single photos
            caption = message.caption or ''
            splitted_input = remove_punctuation(caption.lower()).split()
            sender_username = message.from_user.username if message.from_user.username else ""
            message_link = f"{GROUP_LINK2}/{message.message_id}"
            for word in splitted_input:
                if word in db2:
                    for user_id in db2[word]:
                        if check_strings_not_in_list(splitted_input, get_banned_words(int(user_id))):
                            if user_id not in already_sent:
                                notification_message = f"Free stuff is available ({word} detected)\n{message_link}"
                                await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Photo)")
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
                        if word in db2:
                            for user_id in db2[word]:
                                if check_strings_not_in_list(splitted_input, get_banned_words(int(user_id))):
                                    if user_id not in already_sent:
                                        notification_message = f"Free stuff is available ({word} detected)\n{message_link}"
                                        await check_then_send_message(context, None, notification_message, notification=True, user_id=user_id, type="Detection (Album)")
                                        already_sent.add(user_id)

def main():

    read_files()

    load_db()

    # print(db)
    # print(db2)

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("author", author))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("full_help", full_help))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
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
