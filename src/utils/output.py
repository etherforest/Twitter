import os
from typing import List
from rich.console import Console
from rich.text import Text
from tabulate import tabulate
from rich.table import Table
from rich import box

def show_menu(options: List[str]) -> str:
    """
    Shows numbered menu and returns selected option string.
    """
    print("😎  Select Your Option 😎\n")

    # Выводим пронумерованные опции
    for i, option in enumerate(options, 1):
        print(f"[{i}] {option}")

    while True:
        try:
            print("\n")
            choice = input("Your choice: ")
            choices = choice.split(" ")
            options = [options[int(choice) - 1] for choice in choices]
            return options

        except ValueError:
            print("     ❌ Please enter a valid number")
