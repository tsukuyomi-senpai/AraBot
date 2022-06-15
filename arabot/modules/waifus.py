from __future__ import annotations

import random
from itertools import chain

from arabot.core import Ara, Category, Cog, Context
from arabot.utils import AnyMember, humanjoin
from disnake import Embed
from disnake.ext.commands import Command
from waifu import WaifuAioClient
from waifu.utils import ImageCategories, ImageTypes

REACTION_MAPPING: dict[str, tuple[str, str]] = {
    "bite": ("{author} wants to bite someone", "{author} bites {target}"),
    "blowjob": ("{author} wants to give someone a blowjob", "{author} gives {target} a blowjob"),
    "blush": ("{author} is blushing", "{author} make{s} {target} blush"),
    "bonk": ("{author} wants to bonk someone", "{author} bonks {target}"),
    "bully": ("{author} wants to bully someone", "{author} bullies {target}"),
    "cringe": ("{author} is cringing", "{target} make{s} {author} cringe"),
    "cry": ("{author} is crying", "{target} make{s} {author} cry"),
    "cuddle": ("{author} wants to cuddle someone", "{author} cuddles {target}"),
    "dance": ("{author} is dancing", "{author} is dancing with {target}"),
    "glomp": ("{author} wants to glomp someone", "{author} glomps {target}"),
    "handhold": ("{author} wants to hold someone's hand", "{author} holds {target}'s hand"),
    "happy": ("{author} is happy", "{target} make{s} {author} happy"),
    "highfive": ("{author} wants to highfive someone", "{author} gives {target} a highfive"),
    "hug": ("{author} wants to hug someone", "{author} hugs {target}"),
    "kick": ("{author} wants to kick someone", "{author} kicks {target}"),
    "kill": ("{author} wants to kill someone", "{author} kills {target}"),
    "kiss": ("{author} wants to kiss someone", "{author} kisses {target}"),
    "lick": ("{author} wants to lick someone", "{author} licks {target}"),
    "nom": ("{author} is eating", "{author} eats {target}"),
    "pat": ("{author} wants to pat someone", "{author} pats {target}"),
    "poke": ("{author} wants to poke someone", "{author} pokes {target}"),
    "slap": ("{author} wants to slap someone", "{author} slaps {target}"),
    "smile": ("{author} is smiling", "{target} make{s} {author} smile"),
    "smug": ("( ͡° ͜ʖ ͡°)", "( ͡° ͜ʖ ͡°)"),
    "wave": ("{author} waves at someone", "{author} waves at {author}"),
    "wink": ("{author} is winking", "{author} winks at {target}"),
    "yeet": ("{author} wants to yeet someone", "{author} yeets {target}"),
}


class Waifus(Cog, category=Category.WAIFUS):
    def __new__(cls, *args, **kwargs):
        for reaction_type in set(chain(*ImageCategories.values())):
            command = Command(
                cls.__reaction,
                name=reaction_type,
                usage="[members...]" if reaction_type in REACTION_MAPPING else "",
            )
            setattr(cls, reaction_type, command)

        return super().__new__(cls, *args, **kwargs)

    def __init__(self, waifu_client: WaifuAioClient):
        self.wclient = waifu_client

    async def _get_category_image(self, reaction: str, is_nsfw_channel: bool) -> str:
        if all(reaction in category for category in ImageCategories.values()):
            if is_nsfw_channel:
                category = random.choice((self.wclient.sfw, self.wclient.nsfw))
            else:
                category = self.wclient.sfw
        elif reaction in ImageCategories[ImageTypes.nsfw]:
            category = self.wclient.nsfw
        else:
            category = self.wclient.sfw

        return await category(reaction)

    async def __reaction(self, ctx: Context, *targets: AnyMember):
        targets = [t for t in targets if t]
        reaction_type = ctx.command.name
        image_url = await self._get_category_image(reaction_type, ctx.channel.is_nsfw())
        embed = Embed(title=reaction_type.title()).set_image(url=image_url)
        if reaction_type in REACTION_MAPPING:
            embed.description = REACTION_MAPPING[reaction_type][len(targets) > 0].format(
                author=ctx.author.mention,
                target=humanjoin(t.mention for t in targets),
                s="s" if len(targets) == 1 else "",
                ve="s" if len(targets) == 1 else "ve",
            )
        await ctx.send(embed=embed)


def setup(ara: Ara):
    waifu_client = WaifuAioClient(ara.session)
    ara.add_cog(Waifus(waifu_client))
