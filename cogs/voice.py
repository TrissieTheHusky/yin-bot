"""Handle Voiceroles, channel changes, and status changes."""
import discord
from .utils import checks, embeds
from discord.ext import commands


class Voice(commands.Cog):
    """Handle Voiceroles, channel changes, and status changes."""

    def __init__(self, bot):
        """Init method."""
        super().__init__()
        self.bot = bot

    @commands.group(aliases=['vcrole'])
    @commands.guild_only()
    @checks.has_permissions(manage_roles=True)
    async def voiceroles(self, ctx):
        """Check if voiceroles are enabled."""
        if ctx.invoked_subcommand is None:
            desc = ''
            vcrole_enabled = await\
                self.bot.pg_utils.get_voice_enabled(ctx.guild.id)
            desc = 'Enabled' if vcrole_enabled else 'Disabled'
            local_embed = discord.Embed(
                title=f'Voice channel roles are:',
                description=f'**{desc}**',
                color=0x419400
            )
            await ctx.send(embed=local_embed)

    @voiceroles.command()
    async def add(self, ctx, *, role_name):
        """Enable voiceroles and create the role if it doesn't exist."""
        if ctx.author.voice.channel is None:
            local_embed = discord.Embed(
                title=f'You must be in a voice channel to use this command',
                description=f' ',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        voice_channel = ctx.author.voice.channel
        if not role_name:
            local_embed = discord.Embed(
                title=f'Please input a role name!',
                description=f'`voiceroles add rolename`',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        found_role = None
        for role in ctx.guild.roles:
            if role.name.lower() == role_name.lower():
                found_role = role
        if not found_role:
            local_embed = discord.Embed(
                title=f'Couldn\'t find role {role_name}',
                description=' ',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        try:
            await self.bot.pg_utils.add_role_channel(
                ctx.guild.id, voice_channel.id, found_role.id)
        except Exception as e:
            self.bot.logger.warning(f'Error adding role/channel: {e}')
            local_embed = embeds.InternalErrorEmbed()
            await ctx.send(embed=local_embed)
            return
        vcroles_enabled = await\
            self.bot.pg_utils.get_voice_enabled(ctx.guild.id)
        if not vcroles_enabled:
            await self.bot.pg_utils.set_voice_enabled(
                ctx.guild.id, True)
        local_embed = discord.Embed(
            title=f'Added voice role to channel',
            description=f'**Voice Role:** {found_role .name}\n'
                        f'**Channel:** {voice_channel.name}',
            color=0x419400
        )
        await ctx.send(embed=local_embed)

    @voiceroles.command()
    async def remove(self, ctx, *, role_name):
        """Remove the given role from the voice channel."""
        if ctx.author.voice.channel is None:
            local_embed = discord.Embed(
                title=f'You must be in a voice channel to use this command',
                description=f' ',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        voice_channel = ctx.author.voice.channel
        if not role_name:
            local_embed = discord.Embed(
                title=f'Please input a role name!',
                description=f'`voiceroles remove rolename`',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        found_role = None
        for role in ctx.guild.roles:
            if role.name.lower() == role_name.lower():
                found_role = role
        if not found_role:
            local_embed = discord.Embed(
                title=f'Couldn\'t find role {role_name}',
                description=' ',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        try:
            await self.bot.pg_utils.rem_role_channel(
                ctx.guild.id, voice_channel.id, found_role.id, self.bot.logger)
        except Exception as e:
            self.bot.logger.warning(f'Error removing role/channel: {e}')
            local_embed = embeds.InternalErrorEmbed()
            await ctx.send(embed=local_embed)
            return
        local_embed = discord.Embed(
            title=f'Removed voice role from channel',
            description=f'**Voice Role:** {found_role .name}\n'
                        f'**Channel:** {voice_channel.name}',
            color=0x419400
        )
        await ctx.send(embed=local_embed)

    @voiceroles.command()
    async def disable(self, ctx):
        """Disable all voice roles for server."""
        vcrole_enabled = await\
            self.bot.pg_utils.get_voice_enabled(ctx.guild.id)
        if not vcrole_enabled:
            local_embed = discord.Embed(
                title=f'Voice channel roles are already disabled!',
                description=' ',
                color=0x419400
            )
            await ctx.send(embed=local_embed)
            return
        try:
            await self.bot.pg_utils.set_voice_enabled(
                ctx.guild.id, False
            )
            await self.bot.pg_utils.purge_voice_roles(
                ctx.guild.id
            )
            local_embed = discord.Embed(
                title=f'Voice channel roles are now disabled!',
                description=f' ',
                color=0x419400
            )
            await ctx.send(embed=local_embed)
        except Exception as e:
            self.bot.logger.warning(f'Error deleting voice role: {e}')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Listen for voice channel changes and apply role if applicable."""
        vc_enabled = await self.bot.pg_utils.get_voice_enabled(
            member.guild.id)
        if not vc_enabled:
            return
        users_roles = member.roles.copy()
        if before.channel is None and after.channel:
            vc_roles = await self.bot.pg_utils.get_channel_roles(
                member.guild.id, after.channel.id
            )
            for vc_role in vc_roles:
                found_role = None
                for role in member.guild.roles:
                    if role.id == vc_role:
                        found_role = role
                if not found_role:
                    self.bot.logger.warning(
                        f'Couldn\'t find {vc_role} in guild {member.guild.id}')
                    continue
                users_roles.append(found_role)
            await member.edit(roles=set(users_roles))
        elif after.channel is None and before.channel:
            vc_roles = await self.bot.pg_utils.get_channel_roles(
                member.guild.id, before.channel.id
            )
            for vc_role in vc_roles:
                for role in users_roles:
                    if role.id == vc_role:
                        try:
                            users_roles.remove(role)
                        except ValueError:
                            self.bot.logger.warning(
                                f'{vc_role} not found in {users_roles}')
            await member.edit(roles=set(users_roles))
        else:
            vc_roles = await self.bot.pg_utils.get_server_roles(
                member.guild.id
            )
            for vc_role in vc_roles:
                for role in users_roles:
                    if role.id == vc_role:
                        try:
                            users_roles.remove(role)
                        except ValueError:
                            self.bot.logger.warning(
                                f'{vc_role} not found in {users_roles}')
            vc_roles = await self.bot.pg_utils.get_channel_roles(
                member.guild.id, after.channel.id
            )
            for vc_role in vc_roles:
                found_role = None
                for role in member.guild.roles:
                    if role.id == vc_role:
                        found_role = role
                if not found_role:
                    self.bot.logger.warning(
                        f'Couldn\'t find {vc_role} in guild {member.guild.id}')
                    continue
                users_roles.append(found_role)
            await member.edit(roles=set(users_roles))


def setup(bot):
    """General cog loading."""
    bot.add_cog(Voice(bot))
