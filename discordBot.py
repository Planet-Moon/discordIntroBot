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

class SillyBot(commands.Bot):
    def __init__(self,TOKEN,GUILD="",command_prefix="!",self_bot=False):
        commands.Bot.__init__(self,command_prefix=command_prefix,self_bot=self_bot)
        self.GUILD = GUILD
        self.add_commands()
        self.intro_dict = json_tools.read_from_file("intro_links.json")
        self.use_cache = True
        self.cache_dir = Path("./cache")
        self.intro_manager = ytdl.IntroManager(self.cache_dir)
        self.run(TOKEN)


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


    async def on_voice_state_update(self, user, stateOld, stateNew):
        joined_user = self.intro_dict.get(str(user),None)
        if joined_user:
            logger.info("play intro song for "+str(user))
            if stateNew.channel and not stateOld.channel:
                await stateNew.channel.connect()
                voice_client = self.voice_clients[-1]

                player = await self.intro_manager.get_intro_from_cache(str(user))
                player.volume = joined_user["volume"]

                voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

                async def disconnect_vc(vc):
                    while vc.is_playing():
                        time.sleep(0.05)
                    vc.stop()
                    await vc.disconnect()

                await disconnect_vc(vc=voice_client)

            return


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
            self.intro_dict[str(ctx.author)] = {"intro_link": intro_link, "time_start": time_start, "intro_length": intro_length,"volume":volume}

            if self.use_cache:
                intro_entry = self.intro_dict.get(str(ctx.author),None)
                if intro_entry:
                    await self.intro_manager.delete_intro(str(ctx.author))

                await self.intro_manager.cache_intro(
                        user=str(ctx.author),
                        url=intro_link,
                        volume=volume,
                        timestamp=time_start,
                        duration=intro_length)
                logger.info("Cached new intro")

            json_tools.dump_into_file("intro_links.json",self.intro_dict)
            await ctx.send("Intro ready!")


        @self.command(name="delete_intro",help="Delete linked intro to joining voice channels", pass_context=True)
        async def delete_intro(ctx, intro_link:str="https://www.youtube.com/watch?v=bluoyN8K_rA", time_start:int=0, intro_length:int=10, volume:float=0.15):
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
