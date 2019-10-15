"""Moderation toolkit this is for tasks such as kicking/banning users."""

import discord
from discord.ext import commands
from .utils import helpers, checks, embeds, enums
from .utils.functions import GeneralMember, MemberID, BannedMember
from .utils.enums import Action


class ActionReason(commands.Converter):
    """Generalized converter to reduce  arguments."""

    async def convert(self, ctx, argument):
        """."""
        ret = argument
        # if len(ret) > 512:
        #     reason_max = 512 - len(ret) - len(argument)
        #     raise commands.BadArgument(
        #         f'reason is too long ({len(argument)}/{reason_max})')
        return ret


class Moderation(commands.Cog):
    """Main cog class for moderation tools (kicking, banning, unbanning)."""

    def __init__(self, bot):
        """Init method."""
        super().__init__()
        self.bot = bot

    @commands.command()
    @checks.has_permissions(ban_members=True)
    @commands.guild_only()
    async def logban(self, ctx, member: BannedMember, *,
                     reason: ActionReason = None):
        """Log a right-click ban to modlog channels."""
        if self.bot.server_settings[ctx.guild.id]['modlog_enabled']:
            try:
                confirm = await helpers.custom_confirm(
                    ctx,
                    f'```\nUser: {member.user}\nReason: {reason}\n```'
                )
                if not confirm:
                    return
                resp_mod = ctx.author
                ban_reason = reason if reason else member.reason
                local_embed = embeds.BanEmbed(
                    member.user, resp_mod, ban_reason)
                mod_logs = await self.bot.pg_utils.get_modlogs(ctx.guild.id)
                for channel_id in mod_logs:
                    try:
                        await self.bot.pg_utils.insert_modaction(
                            ctx.guild.id,
                            resp_mod.id,
                            member.user.id,
                            ban_reason,
                            enums.Action.BAN
                        )
                    except Exception as e:
                        self.bot.logger.warning(f'Error storing modaction: {e}')  # noqa
                    await (self.bot.get_channel(channel_id)).send(
                        embed=local_embed)
            except Exception as e:
                self.bot.logger.warning(f'Issue posting to mod log: {e}')
        else:
            await ctx.send(f'No modlog channels detected', delete_after=3)

    @logban.error
    async def logban_error(self, ctx, error):
        """Logban error catcher."""
        self.bot.logger.warning(f'Banned_user argument not found in ban list.')
        await ctx.send(
            embed=embeds.LogbanErrorEmbed(),
            delete_after=3
        )

    @commands.group(invoke_without_command=True)
    @checks.has_permissions(ban_members=True)
    @commands.guild_only()
    async def moderate(self, ctx, member: GeneralMember, *,
                       reason: ActionReason = None):
        """Moderate a user."""
        if ctx.invoked_subcommand is None:
            if self.bot.server_settings[ctx.guild.id]['modlog_enabled']:
                try:
                    confirm = await helpers.custom_confirm(
                        ctx,
                        f'```\nUser: {member}\nReason: {reason}\n```'
                    )
                    if not confirm:
                        return
                    try:
                        await self.bot.pg_utils.insert_modaction(
                            ctx.guild.id,
                            ctx.author.id,
                            member.id,
                            reason,
                            enums.Action.MISC
                        )
                    except Exception as e:
                        self.bot.logger.warning(f'Error storing modaction: {e}')  # noqa
                    local_embed = embeds.ModerationEmbed(
                        member, ctx.author, reason)
                    mod_logs = await self.bot.pg_utils.get_modlogs(ctx.guild.id)  # noqa
                    for channel_id in mod_logs:
                        await (self.bot.get_channel(channel_id)).send(
                            embed=local_embed)
                except Exception as e:
                    self.bot.logger.warning(f'Issue posting to mod log: {e}')
            else:
                await ctx.send(f'No modlog channels detected', delete_after=3)
        return

    @moderate.command(aliases=['e'])
    async def edit(self, ctx, member: GeneralMember, index: int = None,
                   action_type: str = None, *, reason: str = None):
        """Edit a Moderated actions."""
        if not reason or not index or not action_type:
            await ctx.send(
                "You need to supply the correct parameters <member, index (from 1), action_type, reason>, try again.",  # noqa
                delete_after=5)
            return
        action_type = action_type.upper()
        actions = [str(x).strip("Action.") for x in Action]
        if action_type not in actions:
            await ctx.send(
                f'You need to supply the correct Action parameter. Must be within: {actions}',  # noqa
                delete_after=5)
            return
        else:
            action_type = Action[action_type]
        if len(reason) > 500:
            await ctx.send(
                "Reason must be shorter than 500 char",
                delete_after=5
            )
        try:
            count = await self.bot.pg_utils.set_single_modaction(
                ctx.guild.id,
                member.id,
                ctx.author.id,
                reason,
                action_type,
                index,
                self.bot.logger
            )
            local_embed = embeds.ModEditEmbed(member, ctx.author, action_type, reason, count)  # noqa
            await ctx.send(embed=local_embed)
        except Exception as e:
            await ctx.send(embed=embeds.InternalErrorEmbed())
            self.bot.logger.warning(f'Error trying edit modactions for user: {e}')  # noqa

    @moderate.command(aliases=['rm', 'rem', 'remove', 'delete'])
    async def remove_modaction(self, ctx, member: GeneralMember, index: int=None):  # noqa
        """Remove a modaction from a user at selected index."""
        if member is None or index is None:
            await ctx.send(
                "You need to supply the correct parameters <member, index (from 1)>, try again.",  # noqa
                delete_after=5)
            return
        try:
            status = await self.bot.pg_utils.delete_single_modaction(
                ctx.guild.id,
                member.id,
                index,
                self.bot.logger
            )
            if '0' in status:
                await ctx.send(
                    embed=embeds.CommandErrorEmbed(
                        'User has not recieved any modactions.'),
                    delete_after=3)
                return
            local_embed = embeds.ModRmEmbed(member)
            await ctx.send(embed=local_embed)
        except Exception as e:
            await ctx.send(embed=embeds.InternalErrorEmbed())
            self.bot.logger.warning(f'Error removing modaction for user: {e}')

    @commands.group()
    @commands.guild_only()
    @checks.is_admin()
    async def footer(self, ctx):
        """Ban/kick footer command."""
        """If no subcommand is
        invoked, it will return the current ban/kick footer."""
        ban_footer = await self.bot.pg_utils.get_ban_footer(
            ctx.guild.id,
            self.bot.logger
        )
        kick_footer = await self.bot.pg_utils.get_kick_footer(
            ctx.guild.id,
            self.bot.logger
        )
        footer_msg = f'**Ban Footer**:\n\n{ban_footer}\n\n'\
                     f'**Kick Footer:**\n\n{kick_footer}'
        if ctx.invoked_subcommand is None:
            local_embed = discord.Embed(
                title=f'Current welcome message: ',
                description=footer_msg
            )
            await ctx.send(embed=local_embed)

    @footer.command(name='set_ban')
    async def set_ban_footer(self, ctx, *, footer_string):
        """Set ban footer to string passed in."""
        if not footer_string:
            local_embed = discord.Embed(
                title=f'No string detected, I need a string parameter to work',
                description=' ',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        success = await self.bot.pg_utils.set_ban_footer(
            ctx.guild.id,
            footer_string,
            self.bot.logger
        )
        if success:
            desc = footer_string.replace(
                f'%user%', ctx.message.author.mention)
            local_embed = discord.Embed(
                title=f'Footer message set:',
                description=f'**Preview:**\n{desc}',
                color=0x419400
            )
        else:
            local_embed = discord.Embed(
                title=f'Internal error occured, please contact @dashwav#7785',
                description=' ',
                color=0x651111
            )
        await ctx.send(embed=local_embed)
        return

    @footer.command(name='set_kick')
    async def set_kick_footer(self, ctx, *, footer_string):
        """Set kick footer to string passed in."""
        if not footer_string:
            local_embed = discord.Embed(
                title=f'No string detected, I need a string parameter to work',
                description=' ',
                color=0x651111
            )
            await ctx.send(embed=local_embed)
            return
        success = await self.bot.pg_utils.set_kick_footer(
            ctx.guild.id,
            footer_string,
            self.bot.logger
        )
        if success:
            desc = footer_string.replace(
                f'%user%', ctx.message.author.mention)
            local_embed = discord.Embed(
                title=f'Footer message set:',
                description=f'**Preview:**\n{desc}',
                color=0x419400
            )
        else:
            local_embed = discord.Embed(
                title=f'Internal error occured, please contact @dashwav#7785',
                description=' ',
                color=0x651111
            )
        await ctx.send(embed=local_embed)
        return

    @commands.command()
    @checks.has_permissions(manage_messages=True)
    async def purge(self, ctx, *args, mentions=None):
        """Purge a set number of messages."""
        deleted = []
        try:
            count = int(next(iter(args or []), 'fugg'))
        except ValueError:
            count = 100
        mentions = ctx.message.mentions
        await ctx.message.delete()
        if mentions:
            for user in mentions:
                try:
                    deleted += await ctx.channel.purge(
                        limit=count,
                        check=lambda x: x.author == user
                    )
                except discord.Forbidden:
                    return await ctx.send(
                        'I do not have sufficient permissions to purge.')
                except Exception as e:
                    self.bot.logger.warning(f'Error purging messages: {e}')
        else:
            try:
                deleted += await ctx.channel.purge(limit=count)
            except discord.Forbidden:
                return await ctx.send(
                    'I do not have sufficient permissions to purge.')
            except Exception as e:
                self.bot.logger.warning(f'Error purging messages: {e}')

    @commands.command()
    @checks.has_permissions(kick_members=True)
    async def kick(self, ctx, member: MemberID, *,
                   reason: ActionReason = None):
        """Kick a user."""
        if reason is None:
            await ctx.send(
                "You need to supply a reason, try again.",
                delete_after=5)
            return
        confirm = await helpers.confirm(ctx, member, reason)
        if confirm:
            embed = await self.create_embed(
                'Kick', ctx.guild, ctx.guild.id, reason)
            try:
                try:
                    await member.create_dm()
                    await member.dm_channel.send(embed=embed)
                except Exception as e:
                    self.bot.logger.warning(f'Error messaging user!: {e}')
                await member.kick(reason=f'by: {ctx.author} for: {reason[0:480]}')  # noqa
                await ctx.send('\N{OK HAND SIGN}', delete_after=3)
                try:
                    await self.bot.pg_utils.insert_modaction(
                        ctx.guild.id,
                        ctx.author.id,
                        member.id,
                        reason,
                        enums.Action.KICK
                    )
                except Exception as e:
                    self.bot.logger.warning(f'Error storing modaction: {e}')
            except Exception as e:
                self.bot.logger.warning(f'Error kicking user!: {e}')
                await ctx.send('❌', delete_after=3)
                return
            if self.bot.server_settings[ctx.guild.id]['modlog_enabled']:
                try:
                    local_embed = embeds.KickEmbed(member, ctx.author, reason)
                    mod_logs = await self.bot.pg_utils.get_modlogs(ctx.guild.id)  # noqa
                    for channel_id in mod_logs:
                        await (self.bot.get_channel(channel_id)).send(
                            embed=local_embed)
                except Exception as e:
                    self.bot.logger.warning(f'Issue posting to mod log: {e}')
        else:
            await ctx.send("Cancelled kick", delete_after=3)

    @commands.command()
    @checks.has_permissions(ban_members=True)
    async def ban(self, ctx, member: MemberID, *,
                  reason: ActionReason = None):
        """Ban a user."""
        if reason is None:
            await ctx.send(
                "You need to supply a reason, try again.",
                delete_after=5)
            return
        confirm = await helpers.confirm(ctx, member, reason)
        if confirm:
            embed = await self.create_embed(
                'Ban', ctx.guild, ctx.guild.id, reason)
            try:
                try:
                    await member.create_dm()
                    await member.dm_channel.send(embed=embed)
                except Exception as e:
                    self.bot.logger.warning(f'Error messaging user!: {e}')
                await ctx.guild.ban(
                    discord.Object(id=member.id),
                    delete_message_days=0,
                    reason=f'by: {ctx.author} for: {reason[0:480]}')
                await ctx.send('\N{OK HAND SIGN}', delete_after=3)
                try:
                    await self.bot.pg_utils.insert_modaction(
                        ctx.guild.id,
                        ctx.author.id,
                        member.id,
                        reason,
                        enums.Action.BAN
                    )
                except Exception as e:
                    self.bot.logger.warning(f'Error storing modaction: {e}')
            except Exception as e:
                self.bot.logger.warning(f'Error banning user!: {e}')
                await ctx.send('❌', delete_after=3)
                return
            if self.bot.server_settings[ctx.guild.id]['modlog_enabled']:
                try:
                    local_embed = embeds.BanEmbed(member, ctx.author, reason)
                    mod_logs = await self.bot.pg_utils.get_modlogs(ctx.guild.id)  # noqa
                    for channel_id in mod_logs:
                        await (self.bot.get_channel(channel_id)).send(
                            embed=local_embed)
                except Exception as e:
                    self.bot.logger.warning(f'Issue posting to mod log: {e}')
        else:
            await ctx.send("Cancelled ban", delete_after=3)

    @commands.command()
    @checks.has_permissions(ban_members=True)
    async def unban(self, ctx, member: BannedMember, *,
                    reason: ActionReason = None):
        """Unban a user.."""
        if reason is None:
            await ctx.send(
                "You need to supply a reason, try again.",
                delete_after=5)
            return
        confirm = await helpers.confirm(ctx, member.user, reason)
        if confirm:
            try:
                await ctx.guild.unban(
                    member.user,
                    reason=f'by: {ctx.author} for: {reason[0:480]}')
                await ctx.send('\N{OK HAND SIGN}', delete_after=3)
            except Exception as e:
                self.bot.logger.warning(f'Error unbanning user!: {e}')
                await ctx.send('❌', delete_after=3)
                return
            self.bot.logger.info(f'Successfully unbanning {member}')
            try:
                await self.bot.pg_utils.insert_modaction(
                    ctx.guild.id,
                    ctx.author.id,
                    member.user.id,
                    reason,
                    enums.Action.UNBAN
                )
            except Exception as e:
                self.bot.logger.warning(f'Error storing modaction: {e}')
            if self.bot.server_settings[ctx.guild.id]['modlog_enabled']:
                try:
                    local_embed = embeds.UnBanEmbed(
                        member.user, ctx.author, reason)
                    mod_logs = await self.bot.pg_utils.get_modlogs(ctx.guild.id)  # noqa
                    for channel_id in mod_logs:
                        await (self.bot.get_channel(channel_id)).send(
                            embed=local_embed)
                except Exception as e:
                    self.bot.logger.warning(f'Issue posting to mod log: {e}')
        else:
            await ctx.send("Cancelled unban", delete_after=3)

    async def create_embed(self, command_type, server_name,
                           server_id, reason):
        """Generalized embed method."""
        try:
            embed = discord.Embed(
                title=f'❗ {command_type} Reason ❗', type='rich')
            footer = 'This is an automated message'
            custom_footer = footer
            if command_type.lower() == 'ban':
                command_type = 'bann'
                custom_footer = await self.bot.pg_utils.get_ban_footer(
                    server_id,
                    self.bot.logger)
            elif command_type.lower() == 'kick':
                custom_footer = await self.bot.pg_utils.get_kick_footer(
                    server_id,
                    self.bot.logger)
            elif command_type.lower() == 'unban':
                command_type = 'unbann'
            embed.description = f'\nYou were {command_type.lower()}ed '\
                                f'from **{server_name}**.'
            if custom_footer != footer:
                embed.add_field(name='Reason:', value=reason +
                                f'\n\n{custom_footer}')
            else:
                embed.add_field(name='Reason:', value=reason)
            embed.set_footer(text=footer)
            return embed
        except Exception as e:
            self.bot.logger.warning(
                f'Error creating embed for {command_type.lower()}: {e}')


def setup(bot):
    """General cog loading."""
    bot.add_cog(Moderation(bot))
