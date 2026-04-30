import os
import time

WINDOWS = os.name == "nt"
if WINDOWS:
    import msvcrt


def clear_screen(cli_mode=False):
    if cli_mode:
        return
    os.system("cls" if WINDOWS else "clear")


def wait_enter(message="Press Enter to continue...", cli_mode=False):
    if cli_mode:
        return
    input(f"\n{message}")


def countdown_with_skip(seconds=10, cli_mode=False):
    if cli_mode:
        return

    lines = [
        "Tools used for this script:",
        "vgmstream (https://github.com/vgmstream/vgmstream)",
        "crid (https://github.com/kokarare1212/CRID-usm-Decrypter)",
        "ffmpeg (https://www.ffmpeg.org/)",
        "MaiChartConverter (https://github.com/Neskol/MaichartConverter)",
        "AssetStudioCLI (https://github.com/Perfare/AssetStudio)",
        "",
        "Shout out to these dudes! If you wanna skip the countdown, press any key to continue.",
    ]

    if WINDOWS:
        for remaining in range(seconds, 0, -1):
            clear_screen()
            print(f"Starting in {remaining}...\n")
            for line in lines:
                print(line)
            start = time.time()
            while time.time() - start < 1:
                if msvcrt.kbhit():
                    msvcrt.getch()
                    clear_screen()
                    return
                time.sleep(0.05)
    else:
        for remaining in range(seconds, 0, -1):
            clear_screen()
            print(f"Starting in {remaining}...\n")
            for line in lines:
                print(line)
            time.sleep(1)
    clear_screen()


def ask_choice(prompt, valid_choices):
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print("Invalid choice.")


def ask_yes_no(prompt):
    while True:
        value = input(prompt).strip().lower()
        if value in ("y", "n"):
            return value == "y"
        print("Please enter y or n.")
