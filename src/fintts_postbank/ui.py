"""User interface helpers for input handling."""


def get_valid_choice(prompt: str, max_index: int, default: int | None = None) -> int:
    """Get a valid integer choice from user within range.

    Args:
        prompt: The prompt to display.
        max_index: Maximum valid index (inclusive).
        default: Default value to return on empty input (optional).

    Returns:
        Valid integer choice.
    """
    while True:
        try:
            user_input = input(prompt).strip()
            if user_input == "" and default is not None:
                return default
            choice = int(user_input)
            if 0 <= choice <= max_index:
                return choice
            print(f"Please enter a number between 0 and {max_index}")
        except ValueError:
            print("Please enter a valid number")
