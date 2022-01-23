from jishaku.cog import STANDARD_FEATURES, OPTIONAL_FEATURES
from jishaku.features.baseclass import Feature
from utils.buttons import ButtonDelete
import humanize
import discord
import jishaku
import psutil
import sys


class Jishaku(*OPTIONAL_FEATURES, *STANDARD_FEATURES, command_attrs=dict(hidden=True)):

    @Feature.Command(name="jishaku", aliases=["jsk"], invoke_without_command=True, ignore_extra=False)
    async def jsk(self, ctx):
        """
        The Jishaku debug and diagnostic commands.
        This command on its own gives a status brief.
        All other functionality is within its subcommands.
        """
        load = int(self.load_time.timestamp())
        start = int(self.start_time.timestamp())
        summary = [
            f"Jishaku `v{jishaku.__version__}`, discord.py `v{discord.__version__}`, "
            f"Python `{sys.version}` on `{sys.platform}`, ".replace("\n", ""),
            f"\nJishaku was loaded <t:{load}:R> "
            f"\nmodule was loaded <t:{start}:R>.",
            ""
        ]
        try:
            proc = psutil.Process()
            with proc.oneshot():
                try:
                    mem = proc.memory_full_info()

                    summary.append(
                        f"This process is using {humanize.naturalsize(mem.rss)} physical memory!"
                        f"\n{humanize.naturalsize(mem.vms)} virtual memory, "
                        f"{humanize.naturalsize(mem.uss)} of which is unique to this process."
                    )
                except psutil.AccessDenied:
                    pass
                try:
                    name = proc.name()
                    pid = proc.pid
                    tc = proc.num_threads()
                    summary.append(
                        f"\nThis process is running on Process ID `{pid}` (`{name}`) with {tc} threads.")
                except psutil.AccessDenied:
                    pass
                summary.append("")
        except psutil.AccessDenied:
            summary.append("psutil is installed but this process does not have access to display this information")
            summary.append("")
        guilds = f"{len(self.bot.guilds)} guilds"
        humans = f"{sum(not m.bot for m in self.bot.users)} humans"
        bots = f"{sum(m.bot for m in self.bot.users)} bots"
        users = f"{len(self.bot.users)} users"
        cache_summary = f"can see {guilds}, {humans}, and {bots}, totaling to {users}."
        if isinstance(self.bot, discord.AutoShardedClient):
            if len(self.bot.shards) > 20:
                summary.append(
                    f"This bot is automatically sharded ({len(self.bot.shards)} shards of {self.bot.shard_count})"
                    # f" and can see {cache_summary}"
                )
            else:
                shard_ids = ', '.join(str(i) for i in self.bot.shards.keys())
                summary.append(
                    f"This bot is automatically sharded (Shards {shard_ids} of {self.bot.shard_count})"
                    f" and can see {cache_summary}"
                )
        elif self.bot.shard_count:
            summary.append(f"This bot is manually sharded and {cache_summary}")
        else:
            summary.append(f"This bot is not sharded and {cache_summary}")
        if self.bot._connection.max_messages:
            message_cache = f"\nMessage cache is capped at {self.bot._connection.max_messages}."
        else:
            message_cache = "Message cache is not enabled."
        summary.append(message_cache)
        if discord.version_info >= (1, 5, 0):
            presence_intent = f"\nPresences intent `{'enabled' if self.bot.intents.presences else 'disabled'}`"
            members_intent = f"Members intent `{'enabled' if self.bot.intents.members else 'disabled'}`"
            summary.append(f" {presence_intent} and {members_intent}.")
        else:
            guild_subs = self.bot._connection.guild_subscriptions
            guild_subscriptions = f"`guild subscriptions` are `{'enabled' if guild_subs else 'disabled'}`"
            summary.append(f"{message_cache} and {guild_subscriptions}.")
        summary.append("")
        jishaku_embed = discord.Embed(description="\n".join(summary), color=0x00ffb3)
        jishaku_embed.set_author(name="Jishaku", icon_url=ctx.me.display_avatar.url)
        jishaku_embed.set_footer(text=f"Average websocket latency: {round(self.bot.latency * 1000)}ms",
                                 icon_url=ctx.author.display_avatar.url)
        jishaku_embed.timestamp = discord.utils.utcnow()
        await ctx.reply(embed=jishaku_embed, mention_author=False, view=ButtonDelete(ctx))


def setup(client):
    client.add_cog(Jishaku(bot=client))
