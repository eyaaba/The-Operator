"""Verify OAuth identity and configured test mailbox without modifying messages."""

from dotenv import load_dotenv

load_dotenv()

from agent.gmail_backend import _service


def main():
    _, account = _service()
    print("OAuth connected to test mailbox:", account)
    print("Gmail write operations still require an explicit agent approval.")


if __name__ == "__main__":
    main()