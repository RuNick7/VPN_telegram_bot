# Button icons

The temporary icon pack for user_bot's buttons: 31 icons from
[Phosphor Icons](https://github.com/phosphor-icons/core) (MIT, see `LICENSE`),
Regular weight, white on transparent, 100×100 PNG. Which file stands for which
button emoji is the `ICONS` table in `user_bot/button_icons.py`.

`python user_bot/make_emoji_pack.py` turns these into a custom emoji set;
`BUTTON_ICONS_SET` in `.env` switches the bot over to it. A pack of your own
replaces this one with the same file names under `--images`.
