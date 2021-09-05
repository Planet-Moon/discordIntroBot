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

logging.basicConfig(level=logging.INFO,format='%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(filename)s %(lineno)d %(message)s')
logger = logging.getLogger(__name__)

class SillyBot(commands.Bot):
    def __init__(self,TOKEN,GUILD="",command_prefix="!",self_bot=False):
        commands.Bot.__init__(self,command_prefix=command_prefix,self_bot=self_bot)
        self.GUILD = GUILD
        self.add_commands()
        self.intro_dict = json_tools.read_from_file("intro_links.json")
        self.run(TOKEN)


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
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')

    async def on_member_join(member):
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

                player = await ytdl.YTDLSource.from_url(joined_user["intro_link"],stream=True,timestamp=joined_user["time_start"])
                player.volume = joined_user["volume"]
                voice_client.play(player, after=lambda e: logger.error(f'Player error: {e}') if e else None)

                async def disconnect_vc(vc,sleep_time):
                    time.sleep(sleep_time)
                    await vc.disconnect()

                await disconnect_vc(vc=voice_client,sleep_time=joined_user["intro_length"])

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
        async def link_intro(ctx, intro_link:str="https://www.youtube.com/watch?v=bluoyN8K_rA", time_start:int=0, intro_length:float=10, volume:float=0.15):
            self.intro_dict[str(ctx.author)] = {"intro_link": intro_link, "time_start": time_start, "intro_length": intro_length,"volume":volume}
            logger.info("link_intro")
            json_tools.dump_into_file("intro_links.json",self.intro_dict)

        @self.command(name="delete_intro",help="Delete linked intro to joining voice channels", pass_context=True)
        async def delete_intro(ctx, intro_link:str="https://www.youtube.com/watch?v=bluoyN8K_rA", time_start:int=0, intro_length:int=10, volume:float=0.15):
            self.intro_dict[str(ctx.author)] = None
            logger.info("delete intro")
            json_tools.dump_into_file("intro_links.json",self.intro_dict)





def main():

    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD = os.getenv('DISCORD_GUILD')
    sillyBot = SillyBot(TOKEN,GUILD)


if __name__ == '__main__':
    main()
