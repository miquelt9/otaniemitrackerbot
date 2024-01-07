# Otaniemi Tracker Bot
Source code for otaniemi tracker bot (https://t.me/otaniemitrackerbot)

### > What can this bot do?

This bot became the solution to a problem I had when moving to Finland for Erasmus since the apartment I got was not furnished, the main recommended group to get the furniture has a lot influx so I needed a way to filter what was important for me. The bot allows you to track the objects you are interested in the desired group and forwards to you any message that you might be interested in so you don't miss it.

The commands for the bot are the follwing ones:
| Command | Description | Permisions |
|---|---|---|
| /start | Starts the bot | User  |
| /help | Shows help message | User  |
| /full_help | Shows a more detailed help message | User |
| /track [word] | Starts tracking a word  | User |
| /untrack [word]| Stops tracking a word | User |
| /ban [word]| Bans a word | User |
| /unban [word]| Unbans a word | User |
| /show | Shows the tracked and banned words | User |
| /show_tracked | Shows the tracked words | User |
| /show_banned | Shows the banned words | User |
| /clear | Clears the tracked words | User |
| /clear_banned | Clears the banned words | User |
| /feedback [message] | Sends a feedback message to the bot | User |
| /rate [message] | " | User |
| /author | Shows the credits | User |
| /get_mod [pswd] | Gives mod rights to the user | User |
| /get_admin [pswd] | Gives admin and mod rights to the user | User |
| /user_count | Shows current count of users of the bot | Mod |
| /rank_words | Shows a list of the tracked words ordered by #ppl tracking it | Mod |
| /rank_tracked | " | Mod |
| /save | Saves the current database (otherwise only done when a user sends a command) | Mod |
| /see_feedback | Shows the feedback sent by the users | Mod |
| /check_feedback | Shows the feedback sent by the users | Mod |
| /show_mods | Shows all the users that has mods rights | Mod |
| /show_admins | Shows all the users that has admins rights | Admin |
| /clear_feedback | Cleans the feedback file | Admin |
| /send_active [message] | Send a message to all active users | Admin |
| /send_everyone [message] | Send a message to all users | Admin |


### > How to run it yourself

In order to run the bot you will first have to install the requirements using:
```
pip install -r requirements.txt
```
You will also need a tocken of the bot (https://t.me/botfather) which you should put into a `token.txt` file.   
The same applies for `pswd.adm` and `pswd.mod` which are the files that contains the respective passwords in plain text.   
Also, this bot loads the DB when it starts, if the correct files aren't manually created (which I don't personally recommend since those are pickle files named `db.pkl`, `db2.pkl` and `dbb.pkl`) you have to create them, the recommended way is to comment the _load_db()_ method on the python code and run it then send the _/start_ command followed by a _/track [word]_ or _/get_mod [your_pswd]_ and _/save_. After the files will already be created and you can uncomment it and run as usually.
The last needed file is the `group_id.txt`, which contains the id of the tracked group, in order to get it I personally recommend printing the chat id, there's a commented line in _message_handler(...)_ method to make it easier. Also group public `group_link.txt` is needed (see the description of the group to find it).

-> Now available the [basic_testing_files.zip](./basic_testing_files.zip) so you don't need to do all the stuff above to run it (except for group_id.txt and token.txt)

To run it use:
```
python3 bot.py
```
### > Want to contribute?
Then check the [issues](https://github.com/miquelt9/otaniemitrackerbot/issues) tab from the project to start working or create your own to let the other know about your thoughs and findings.   
