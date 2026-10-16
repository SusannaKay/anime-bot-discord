import discord
from discord import app_commands
from pathlib import Path
from typing import List, Optional

from ui.embed_factory import EmbedFactory

IMAGES_ROOT = Path(__file__).resolve().parent.parent / "images"


def _resolve_image_path(file_path: str) -> Optional[Path]:
    candidate = Path(file_path)
    if candidate.is_file():
        return candidate
    nested = IMAGES_ROOT / file_path
    if nested.is_file():
        return nested
    matches = list(IMAGES_ROOT.rglob(Path(file_path).name))
    if matches:
        return matches[0]
    return None



class InventoryView(discord.ui.View):
    """View with buttons to browse the card gallery."""

    def __init__(self, interaction: discord.Interaction, entries: List[dict], owner_name: str) -> None:
        super().__init__(timeout=180)
        self.interaction = interaction
        self.entries = entries
        self.owner_name = owner_name
        self.index = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.index <= 0
        self.next_button.disabled = self.index >= len(self.entries) - 1

    def _build_embed_and_file(self, entry: dict) -> (discord.Embed, Optional[discord.File]):
        attachment = None
        card_info = dict(entry)
        path = _resolve_image_path(entry.get("file_path", ""))
        if path and path.is_file():
            attachment = discord.File(str(path), filename=path.name)
            card_info["file_path"] = str(path)
        else:
            card_info["file_path"] = ""
        card_info["page_label"] = f"Page {self.index + 1}/{len(self.entries)}"

        embed = EmbedFactory.create_pool_page_embed(self.owner_name, card_info)
        if attachment:
            embed.set_image(url=f"attachment://{attachment.filename}")
        return embed, attachment

    async def _send_page(self, interaction: discord.Interaction) -> None:
        entry = self.entries[self.index]
        embed, attachment = self._build_embed_and_file(entry)
        self._update_buttons()
        if attachment:
            await interaction.response.edit_message(embed=embed, attachments=[attachment], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("Only the owner can use these buttons.", ephemeral=True)
            return
        if self.index > 0:
            self.index -= 1
        await self._send_page(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("Only the owner can use these buttons.", ephemeral=True)
            return
        if self.index < len(self.entries) - 1:
            self.index += 1
        await self._send_page(interaction)


@app_commands.command(name="pool", description="Show an adventurer's card collection.")
@app_commands.describe(user="The user whose collection to show (default: you).")
async def pool(interaction: discord.Interaction, user: Optional[discord.User] = None) -> None:
    target = user or interaction.user
    db = getattr(interaction.client, "db", None)
    if db is None:
        await interaction.response.send_message("Database not available.", ephemeral=True)
        return

    inventory = db.get_inventory(str(target.id))
    if not inventory:
        empty_embed = EmbedFactory.create_status_embed(
            {
                "title": f"📜 {target.name}'s collection",
                "description": "The tome is empty. No cards yet... for now.",
                "status": "warning",
            }
        )
        await interaction.response.send_message(embed=empty_embed, ephemeral=False)
        return

    entries = []
    for item in inventory:
        entries.append(
            {
                "file_path": item.get("file_path", ""),
                "character_name": item.get("character_name", ""),
                "character_anime": item.get("character_anime", ""),
                "rarity": item.get("rarity", ""),
                "obtained_at": item.get("obtained_at", ""),
                "owner_name": target.name,
            }
        )

    view = InventoryView(interaction, entries, owner_name=target.name)
    first_embed, first_attachment = view._build_embed_and_file(entries[0])
    view._update_buttons()
    await interaction.response.send_message(
        embed=first_embed,
        file=first_attachment if first_attachment else None,
        view=view,
    )


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(pool)
