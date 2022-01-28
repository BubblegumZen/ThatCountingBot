# ThatCountingBot
 
__Recommended Versions__:-

> `Python Version: >= 3.10`

> `SQLite Version: == 3.35.5`

> `discord.py: == 2.0.0a`

# About ThatCountingBot

ThatCountingBot is a discord bot written in python which uses `discord.py` wrapper for Discord API. The bot requires `Guild Member` and `Presences` Intents enabled. After April 26, 2022, you need to enable `Message Read Intents` for the bot to function. This bot can track counting in a server, and ofers count pickups from channel that were previously used for counting. It will delete the message if numbers aren't correctly sent in order, and if this violation is done 5 times in a row, then it will timeout the member for 10 minutes, the timeout limit is configurable. ThatCountingBot also offers a leveling system, that ranks users up. It also has a `$rank` command that generates a rank card similar to `MEE6` along with their server rank. 

![Level Rank Card](https://user-images.githubusercontent.com/97220904/150376149-1138f182-2ef1-489e-aafa-347a824d56ed.png)

In addition to this, it offers the `$setup` command for the counting channel and current number configuration. an `--existing` flag can be passed to the command, so it will try to look for the recent messages for a number to continue from. After pressing the `Set Channel` Button, the bot will ask the user to ping a channel.

![image](https://user-images.githubusercontent.com/97220904/150377161-927efed4-1a31-4121-a7e2-4a359028dc7f.png)

# How to run the bot

1. Go to [Discord Developer Page](https://discord.com/developers/applications)
2. Create an Application
3. Head over to `Bot` section and select `Create a bot account`
4. Turn on `Message Intent` and `Guild/Server Member Intent`.
5. Click on `COPY TOKEN`
6. Clone this repository to a local folde
7. Open `config.py` file and replace the placeholder `BOT_TOKEN` with the token you just copied.
8. Open command prompt and change your working directory to the folder you cloned the repo into.
> Recommended (Create a virtual environment!) [If you do not want this, skip to #12]
9. Type `py -3.10 -m venv count` and wait for it to create the Virtual Environment
10. Type `source count/bin/activate/`
11. If everything went well, you should now see something like this: `(count) .../your_directory`
12. Type `python main.py`

And you should see `<bot name> Is now online!`. Your bot should now be online and ready to be used. The `requirements.txt` will be installed automatically before the bot starts.
