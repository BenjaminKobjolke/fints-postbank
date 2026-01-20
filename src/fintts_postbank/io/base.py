"""Abstract base class for I/O adapters."""

from abc import ABC, abstractmethod


class IOAdapter(ABC):
    """Abstract base class for input/output operations.

    This allows the same business logic to work with different I/O backends
    (console, Telegram, etc.).
    """

    @abstractmethod
    def output(self, message: str) -> None:
        """Display a message to the user.

        Args:
            message: The message to display
        """
        ...

    @abstractmethod
    def input(self, prompt: str) -> str:
        """Get input from the user.

        Args:
            prompt: The prompt to display

        Returns:
            The user's input as a string
        """
        ...

    @abstractmethod
    def get_valid_choice(
        self, prompt: str, max_index: int, default: int | None = None
    ) -> int:
        """Get a valid integer choice from the user.

        Args:
            prompt: The prompt to display
            max_index: Maximum valid choice (0 to max_index inclusive)
            default: Default value if user presses Enter without input

        Returns:
            The user's valid choice as an integer
        """
        ...
