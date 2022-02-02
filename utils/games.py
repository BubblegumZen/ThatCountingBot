import asyncio
import discord

class SubclassedButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset(self, r1, c1):
       index = r1*5 + c1
       self.view.children[index].label = "\u200b"
       self.view.children[index].style = discord.ButtonStyle.gray
       self.view.children[index].disabled = False
       self.view.children[index].emoji = None

    def greenify(self, row, column):
       index = (row*5) + column
       self.view.children[index].style = discord.ButtonStyle.green
       self.view.children[index].disabled = True

    def redify(self, row, column):
       index = (row*5) + column
       self.view.children[index].style = discord.ButtonStyle.red
       self.view.children[index].disabled = True

    def retrive_list_elements(self):
        row1, column1 = self.view.check_list[0][1]
        row2, column2 = self.view.check_list[1][1]
        return row1, row2, column1, column2

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.view.counter + 1 > 2:
            return
        if self.view.counter < 2:
            row = self.row
            custom_id = int(self.custom_id)
            column = custom_id - (row*100)
            self.disabled = True
            new_emoji = self.view.alist[row][1][column][1]
            self.emoji = new_emoji
            self.view.counter += 1
            self.view.check_list.append((str(self.emoji), (row, column)))
            await interaction.message.edit(view=self.view)
        if self.view.counter == 2 and self.view.check_list[0][0] != self.view.check_list[1][0]:
            row1, row2, column1, column2 = self.retrive_list_elements()
            self.redify(row1, column1)
            self.redify(row2, column2)
            await interaction.message.edit(view=self.view)
            await asyncio.sleep(0.20)
            self.view.check_list.clear()
            self.view.counter = 0
            self.reset(row1, column1)
            self.reset(row2, column2)
            return await interaction.message.edit(view=self.view)
        elif self.view.counter == 2 and self.view.check_list[0][0] == self.view.check_list[1][0]:
            row1, row2, column1, column2 = self.retrive_list_elements()
            self.greenify(row1, column1)
            self.greenify(row2, column2)
            self.view.counter = 0
            self.view.check_list.clear()
            return await interaction.message.edit(view=self.view)

class BrainGame(discord.ui.View):
    def __init__(self, alist: tuple, **kwargs: dict):
        super().__init__(timeout=600)
        self.counter = 0
        self.alist = alist
        self.check_list = []
        for row, label_list in alist:
            for custom_id, label in label_list:
                custom_id = str(custom_id + (row*100))
                button = SubclassedButton(label="\u200b", custom_id=custom_id, row=row)
                self.add_item(button)