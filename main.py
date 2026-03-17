"""
main.py — CLI entry point with dialog and iterative editing.

Usage:
    python main.py "A 30mm cube"
    python main.py "a box"         # Interpreter asks for dimensions
    
After a successful run you can type modifications:
    > Make the hole 2mm bigger
    > Add a 1mm chamfer on all top edges
    > quit
"""

import sys
import structlog

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])


def ask_user(question: str) -> str:
    print(f"\n🤖 {question}")
    return input("   Your answer: ").strip()


def print_result(state: dict, attempts: int = 0):
    print("\n" + "=" * 50)
    if state.get("stl_path") and not state.get("validator_feedback"):
        print(f"✅ Success!")
        print(f"   STL: {state['stl_path']}")
        if attempts:
            print(f"   (Fixed after {attempts} attempt(s))")
    else:
        error = (state.get("execution_error")
                 or state.get("validation_error")
                 or state.get("validator_feedback")
                 or "Unknown error")
        print(f"❌ Failed after {state.get('attempts', 0)} attempt(s)")
        print(f"   Error: {error[:200]}")
    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py \"<model description>\"")
        sys.exit(1)

    description = " ".join(sys.argv[1:])
    print(f"\n🔧 Request: {description}\n")

    from src.graph.pipeline import PipelineRunner
    runner = PipelineRunner()

    # Initial run
    state = runner.run(description, ask_user=ask_user)
    print_result(state)

    if not state.get("stl_path"):
        sys.exit(1)

    # Iterative modification loop
    print("\nType a modification or 'quit' to exit.")
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        print(f"\n🔧 Modifying: {user_input}\n")
        state = runner.modify(user_input, previous_state=state, ask_user=ask_user)
        print_result(state)


if __name__ == "__main__":
    main()
