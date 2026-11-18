"""CLI for The Operator. Every proposed write requires interactive approval."""
import argparse
import json
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('goal', nargs='*')
    args = parser.parse_args()
    from langgraph.types import Command
    from agent.graph import build_agent
    agent = build_agent()
    config = {'configurable': {'thread_id': str(uuid.uuid4())}, 'recursion_limit': 75}
    payload = {'messages': [{'role': 'user', 'content': ' '.join(args.goal) or 'Triage my inbox.'}]}
    while True:
        result = agent.invoke(payload, config=config)
        interrupts = result.get('__interrupt__', ())
        if not interrupts:
            for message in result.get('messages', [])[-5:]:
                content = getattr(message, 'content', '')
                if content: print(content if isinstance(content, str) else str(content))
            break
        decisions = []
        for interrupt in interrupts:
            detail = interrupt.value
            for action in detail.get('action_requests', []):
                print('\nPROPOSED WRITE:', json.dumps(action, indent=2, default=str))
                choice = input('Approve [a], reject [r], edit [e] (default reject): ').strip().lower()
                if choice == 'a': decisions.append({'type': 'approve'})
                elif choice == 'e':
                    edited = json.loads(input('Replacement args as JSON: '))
                    decisions.append({'type': 'edit', 'edited_action': {'name': action['name'], 'args': edited}})
                else: decisions.append({'type': 'reject', 'message': 'Human rejected this write.'})
        payload = Command(resume={'decisions': decisions})

if __name__ == '__main__':
    main()
