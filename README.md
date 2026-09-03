# FSD3 Skin Studio

Made by StoicDemon.

A program for building and previewing FreeStyleDash 3 skins on PC. Open any
skin — an extracted folder or a packed .xzp, including retail discs that only
contain compiled .xur files — and look through every scene. Scenes with
source files render fully; compiled scenes show a readable breakdown of
their controls, text, and images, with one-click decompile through XUIHelper
when you need the exact layout.

Everything in this project was written from scratch — no code was taken from
anyone else's work.

## Get it

Easiest: download `Fsd3SkinStudio-1.0-windows.zip` from the Releases page,
unzip it anywhere, and run `Fsd3SkinStudio.exe`. No Python needed.

From source: install Python, run `pip install -r source/requirements.txt`,
then `python source/app.py`. All program files live in `source/`.

## How to use

Viewing skins:

1. `Open folder…` for extracted skin files, or `Open .xzp…` for packed
   skins, including a retail default.xzp.
2. Pick a scene from the list. Full scenes draw on the canvas; scenes marked
   [xur] show a preview instead.
3. For the exact look of an [xur] scene, put XUIHelper.CLI.exe in the CLI
   box and press Decompile, or decompile it yourself in XDK XuiTool.
4. `Extract .xzp…` dumps any package to a folder, the same job XZP Tool does.

Making skins:

1. `New skin…` starts a fresh skin, `New scene…` adds a screen to it.
2. `Add control…` places buttons, text, images, and lists. Click one to
   select it, drag it to move it, change it in the panel on the right.
3. Scrub the timeline or press play to check animations.
4. `Save scene` when it looks right, then `Pack .xzp…` to build the file
   your console reads, and `Validate` to catch mistakes first.

## Found a bug?

Open an issue with what you were doing and what happened. I fix things as
time allows.

## Credits

- XUIHelper by SGCSam — the open converter behind .xur decompile
- XDK XuiTool (Microsoft) — the original XUI toolchain
- FreeStyleDash 3 by Team FSD — the dash these skins are for
- Built with Python, Tkinter, and Pillow

## License

MIT — © 2026 StoicDemon. See LICENSE. The tools listed above are separate
works by their authors; fetch them yourself, they are never bundled here.
