# bot.py
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
import random
import ytdl
import time
import threading
import json_tools
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO,format='%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(filename)s %(lineno)d %(message)s')
logger = logging.getLogger(__name__)

intents = discord.Intents(messages=True, guilds=True)
intents.reactions = True
intents.members = True

class SillyBot(commands.Bot):
    def __init__(self,TOKEN,GUILD="",command_prefix="!",self_bot=False, intents=intents):
        commands.Bot.__init__(self,command_prefix=command_prefix,self_bot=self_bot,intents=intents)
        self.add_cog(ytdl.Music(self))
        self.GUILD = GUILD
        self.add_commands()
        self.intro_dict = json_tools.read_from_file("intro_links.json")
        self.administration = json_tools.read_from_file("administration.json")
        self.use_cache = True
        self.cache_dir = Path("./cache")
        self.intro_manager = ytdl.IntroManager(self.cache_dir)
        self.run(TOKEN)

    def check_blocklisted(self, user:str):
        blocklisted_users:list[str] = self.administration.get("blocklist",None)
        if str(user) in blocklisted_users:
            return True
        return False

    async def notify_admins(self, ctx, message:str):
        admins:list[str] = self.administration.get("admins", None)
        guild_members:map[str,discord.Member] = dict()
        async for member in ctx.guild.fetch_members():
            guild_members[str(member)] = member
        for a in admins:
            admin_member:discord.Member = guild_members.get(a, None)
            if admin_member:
                await admin_member.create_dm()
                await admin_member.dm_channel.send(message)

    async def cache_audio_files(self,intro_dict):
        self.cache_dir.mkdir(exist_ok=True)
        for user, data in intro_dict.items():
            await self.cache_audio_file(
                    user=user,
                    intro_link=data["intro_link"],
                    time_start=data["time_start"],
                    intro_length=data["intro_length"],
                )
            logger.info("Cached intro for user: "+user)


    async def cache_audio_file(self,**kwargs):
        await self.intro_manager.cache_intro(
            user=kwargs["user"],
            url=kwargs["intro_link"],
            timestamp=kwargs["time_start"],
            duration=kwargs["intro_length"])


    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith('$hello') or True:
            # await message.channel.send("echo: {}".format(message.content))
            pass
        logger.info(str(message.author)+": "+str(message.content))
        if message.content == 'raise-exception':
            raise discord.DiscordException
        await self.process_commands(message)


    async def on_ready(self):
        if self.use_cache:
            await self.cache_audio_files(self.intro_dict)
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')


    async def on_member_join(member):
        logger.info(f'Member {member.id} joined')
        return
        await member.create_dm()
        await member.dm_channel.send(
            f'Hi {member.name}, welcome to my Discord server!'
        )


    async def on_voice_state_update(self, user:discord.member.Member, stateOld:discord.channel.VoiceChannel, stateNew:discord.channel.VoiceChannel):
        if user.bot or not stateNew.channel: # bot or disconnect
            return

        joined_user = None
        joined_channel = None

        user_name = str(user)
        if not stateOld.channel: # join channel
            joined_user = self.intro_dict.get(user_name,None)
            joined_channel = self.intro_dict.get(str(stateNew.channel.id),None)
            joined_channel_id = str(stateNew.channel.id)
        elif stateNew.channel.id is not stateOld.channel.id: # move channels
            joined_user = None
            joined_channel = self.intro_dict.get(str(stateNew.channel.id),None)
            joined_channel_id = str(stateNew.channel.id)

        if joined_user or joined_channel:

            if joined_channel:
                logger.info("play intro song for channel "+joined_channel["channel_name"]+" of guild "+joined_channel["guild"]["name"])
                player = await self.intro_manager.get_intro_from_cache(joined_channel_id)
                player.volume = joined_channel["volume"]

            elif joined_user:
                logger.info("play intro song for user "+user_name)
                player = await self.intro_manager.get_intro_from_cache(user_name)
                player.volume = joined_user["volume"]

            else:
                return

            await stateNew.channel.connect()
            voice_client = self.voice_clients[-1]
            voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

            while voice_client.is_playing():
                time.sleep(0.05)
            voice_client.stop()
            await voice_client.disconnect()


    async def on_command_error(self, error, *args, **kwargs):
        for i in args:
            logger.error(str(i))
        for key, value in kwargs:
            logger.error(key+": "+value)
        if isinstance(error, commands.errors.CheckFailure):
            await self.send('You do not have the correct role for this command.')

    def add_commands(self):
        @self.command(name='create_channel', pass_context=True)
        @commands.has_role('admin')
        async def create_channel(ctx, channel_name='real-python'):
            guild = ctx.guild
            existing_channel = discord.utils.get(guild.channels, name=channel_name)
            if not existing_channel:
                logger.info(f'Creating a new channel: {channel_name}')
                await guild.create_text_channel(channel_name)

        @self.command(name='roll_dice', help='Simulates rolling dice.', pass_context=True)
        async def roll(ctx, number_of_dice:int=1, number_of_sides:int=6):
            dice = [
                str(random.choice(range(1, number_of_sides + 1)))
                for _ in range(number_of_dice)
            ]
            if(number_of_dice > 1):
                sum = 0
                for i in dice:
                    sum += int(i)
                dice.append("sum: "+str(sum))
            await ctx.send(', '.join(dice))


        @self.command(name="newpassword", help="Generate a new random password", pass_context=True)
        async def newpassword(ctx):
            await ctx.send("newpassword command")


        @self.command(name="ping", help="Ping of this bot", pass_context=True)
        async def ping(ctx):
            latency = int(self.latency*1000)
            await ctx.send(str(latency)+" ms")


        @self.command(name="link_intro",help="Link intro to joining voice channels", pass_context=True)
        async def link_intro(ctx, intro_link:str="https://www.youtube.com/watch?v=bluoyN8K_rA", time_start:float=0, intro_length:float=10, volume:float=0.15):
            author_name = str(ctx.author)
            self.intro_dict[author_name] = {"intro_link": intro_link, "time_start": time_start, "intro_length": intro_length,"volume":volume}

            if self.use_cache:
                intro_entry = self.intro_dict.get(author_name,None)
                if intro_entry:
                    await self.intro_manager.delete_intro(author_name)

                await self.intro_manager.cache_intro(
                        user=author_name,
                        url=intro_link,
                        volume=volume,
                        timestamp=time_start,
                        duration=intro_length)
                logger.info("Cached new intro")

            json_tools.dump_into_file("intro_links.json",self.intro_dict)
            await ctx.send("Intro ready!")

        @self.command(name="link_channel_intro",help="Link intro joining a specific voice channels for all users", pass_context=True)
        async def link_channel_intro(ctx, channel_id:int, intro_link:str="https://www.youtube.com/watch?v=bluoyN8K_rA", time_start:float=0, intro_length:float=10, volume:float=0.15):
            intro_length = min(20, intro_length)
            channel = channel = discord.utils.get(ctx.guild.channels, id=channel_id)
            if(not channel):
                await ctx.send("Channel not found!")
                return

            if(self.check_blocklisted(ctx.author)):
                await self.notify_admins(ctx, f"{ctx.author} tried to set channel intro for {ctx.guild.name}.{channel.name} to {intro_link} {time_start} {intro_length} {volume}")
                return

            self.intro_dict[str(channel_id)] = {
                "guild": {
                    "id": ctx.guild.id,
                    "name": ctx.guild.name
                },
                "channel_name": channel.name,
                "intro_link": intro_link,
                "time_start": time_start,
                "intro_length": intro_length,
                "volume": volume
            }

            if self.use_cache:
                intro_entry = self.intro_dict.get(str(channel_id),None)
                if intro_entry:
                    await self.intro_manager.delete_intro(str(channel_id))

                await self.intro_manager.cache_intro(
                        user=str(channel_id),
                        url=intro_link,
                        volume=volume,
                        timestamp=time_start,
                        duration=intro_length)
                logger.info("Cached new intro")

            json_tools.dump_into_file("intro_links.json",self.intro_dict)
            await ctx.send("Intro ready!")

        @self.command(name="delete_channel_intro",help="Delete linked channel intro", pass_context=True)
        async def delete_channel_intro(ctx, channel_id:int):
            intro_entry = self.intro_dict.get(str(ctx.author),None)
            if intro_entry:
                await self.intro_manager.delete_intro(str(channel_id))
                self.intro_dict[str(channel_id)] = None
                json_tools.dump_into_file("intro_links.json",self.intro_dict)
                logger.info("deleted channel intro")

        @self.command(name="delete_intro",help="Delete linked intro to joining voice channels", pass_context=True)
        async def delete_intro(ctx):
            intro_entry = self.intro_dict.get(str(ctx.author),None)
            if intro_entry:
                await self.intro_manager.delete_intro(str(ctx.author))
                self.intro_dict[str(ctx.author)] = None
                json_tools.dump_into_file("intro_links.json",self.intro_dict)
                logger.info("delete intro")


def main():

    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD = os.getenv('DISCORD_GUILD')
    sillyBot = SillyBot(TOKEN,GUILD)


if __name__ == '__main__':
    main()
