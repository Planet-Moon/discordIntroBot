import asyncio
import os

import discord
import youtube_dl

from pathlib import Path

from discord.ext import commands

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, timestamp:float=0, duration:float=10, setup_cache:bool=False,cache_dir:Path=Path.cwd()):
        _ffmpeg_options = {
            'before_options': " -ss "+str(timestamp),
            'options': ffmpeg_options['options'] +" -t "+str(duration),
        }
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream and False))

        if not stream and setup_cache:
            os.system('ffmpeg -hide_banner -loglevel error -y -ss {} -i \"{}\" -vn -t {} -c copy {}'.format(timestamp,data['url'],duration,cache_dir.joinpath(ytdl.prepare_filename(data))))
            return

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else str(cache_dir.joinpath(ytdl.prepare_filename(data)))
        _ffmpeg_options = {}
        return cls(discord.FFmpegPCMAudio(filename, **_ffmpeg_options), data=data)

class IntroManager:
    def __init__(self, cache_dir:Path=Path.cwd()):
        self.cache_dir = cache_dir
        self.intro_map = dict() # keys: user, value: file, volume

    @staticmethod
    def parse_user_name(user_name:str):
        return user_name.replace('/','_')

    async def cache_intro(self, user:str, url, *, volume:float=0.15, timestamp:float=0, duration:float=10):
        user_name = self.parse_user_name(user)
        _ffmpeg_options = {
            'before_options': " -ss "+str(timestamp),
            'options': ffmpeg_options['options'] +" -t "+str(duration),
        }
        loop=None
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        filename = self.cache_dir.joinpath(f"{user_name}_t{timestamp}_d{duration}_{ytdl.prepare_filename(data)}")

        if not filename.exists():
            # remove duplicates possible lying around from this user
            duplicates = self.cache_dir.glob(f"{user_name}_t*.m4a")
            for i in duplicates:
                i.unlink()

            os.system(f"ffmpeg -hide_banner -loglevel error -y -ss {timestamp} -i \"{data.get('url')}\" -vn -t {duration} -c copy {filename}")

        self.intro_map[user_name] = {"file":filename,"volume":volume}

    async def get_intro_from_cache(self, user:str) -> discord.PCMVolumeTransformer:
        user_name = self.parse_user_name(user)
        filename = self.intro_map[user_name].get("file")
        volume = self.intro_map[user_name].get("volume")
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(str(filename)),volume)

    async def delete_intro(self, user:str):
        user_name = self.parse_user_name(user)
        user_name_entry = self.intro_map.get(user_name,None)
        if user_name_entry:
            try:
                user_name_entry.get("file").unlink()
            except FileNotFoundError:
                pass


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, query):
        """Plays a file from the local filesystem"""

        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
        ctx.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {query}')

    @commands.command()
    async def yt(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title}')

    @commands.command()
    async def stream(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title}')

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @play.before_invoke
    @yt.before_invoke
    @stream.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()
