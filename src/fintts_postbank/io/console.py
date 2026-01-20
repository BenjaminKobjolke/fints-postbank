"""Console I/O adapter implementation."""

from .base import IOAdapter


class ConsoleAdapter(IOAdapter):
    """Console-based I/O adapter using standard print/input."""

    def output(self, message: str) -> None:
        """Print message to console."""
        print(message)

    def input(self, prompt: str) -> str:
        """Get input from console."""
        return input(prompt)

    def get_valid_choice(
        self, prompt: str, max_index: int, default: int | None = None
    ) -> int:
        """Get a valid integer choice from console input.

        Args:
            prompt: The prompt to display
            max_index: Maximum valid choice (0 to max_index inclusive)
            default: Default value if user presses Enter without input

        Returns:
            The user's valid choice as an integer
        """
        while True:
            try:
                user_input = input(prompt).strip()

                if not user_input and default is not None:
                    return default

                choice = int(user_input)
                if 0 <= choice <= max_index:
                    return choice
                print(f"Please enter a number between 0 and {max_index}")
            except ValueError:
                print("Please enter a valid number")
